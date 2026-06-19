# Processes bookshelf scans asynchronously with bounded retries, stage timing, and structured logging.

import logging
import time
import uuid
from datetime import datetime, timezone

import requests
from redis.exceptions import RedisError
from sqlalchemy.exc import OperationalError

from app.celery_app import celery_app
from app.db import SessionLocal
from app.models.scan_job import ScanJob
from app.services.structured_logging import log_event
from ml.match_books import match_book_candidates
from ml.normalize import build_book_candidates
from ml.ocr import run_ocr
from ml.preprocessing import preprocess_image


MAX_TASK_RETRIES = 3
RETRY_BACKOFF_BASE_SECONDS = 10
RETRY_BACKOFF_MAX_SECONDS = 40

TRANSIENT_SCAN_EXCEPTIONS = (
    OperationalError,
    RedisError,
    requests.RequestException,
)


def _retry_countdown(retry_number: int) -> int:
    return min(
        RETRY_BACKOFF_BASE_SECONDS * (2 ** retry_number),
        RETRY_BACKOFF_MAX_SECONDS,
    )


def _update_retry_state(
    job_uuid: uuid.UUID,
    retry_number: int,
    countdown: int,
) -> None:
    db = SessionLocal()

    try:
        job = db.get(ScanJob, job_uuid)

        if job is None:
            return

        job.status = "retrying"
        job.error_message = (
            "Transient processing error. "
            f"Retry {retry_number} of {MAX_TASK_RETRIES} "
            f"scheduled in {countdown} seconds."
        )
        db.commit()

    except Exception:
        db.rollback()

    finally:
        db.close()


def _mark_job_failed(
    job_uuid: uuid.UUID,
    error_message: str,
) -> None:
    db = SessionLocal()

    try:
        job = db.get(ScanJob, job_uuid)

        if job is None:
            return

        job.status = "failed"
        job.error_message = error_message
        db.commit()

    except Exception:
        db.rollback()

    finally:
        db.close()


@celery_app.task(
    bind=True,
    name="bookfiend.process_scan",
)
def process_scan(
    self,
    job_id: str,
) -> None:
    job_uuid = uuid.UUID(job_id)
    db = SessionLocal()
    task_started = time.perf_counter()

    log_event(
        "scan_started",
        job_id=job_id,
        retry_number=self.request.retries,
    )

    try:
        job = db.get(ScanJob, job_uuid)

        if job is None:
            log_event(
                "scan_job_missing",
                level=logging.WARNING,
                job_id=job_id,
            )
            return

        if not job.image_url:
            raise ValueError(
                "Scan job does not have an uploaded image."
            )

        job.status = "processing"
        job.progress = 10
        job.error_message = None
        db.commit()

        preprocessing_started = time.perf_counter()

        job.status = "preprocessing"
        job.progress = 25
        db.commit()

        processed_image, image_metrics = preprocess_image(
            job.image_url
        )

        preprocessing_ms = round(
            (time.perf_counter() - preprocessing_started) * 1000,
            2,
        )

        log_event(
            "scan_stage_completed",
            job_id=job_id,
            stage="preprocessing",
            duration_ms=preprocessing_ms,
        )

        ocr_started = time.perf_counter()

        job.status = "ocr"
        job.progress = 50
        db.commit()

        ocr_result = run_ocr(processed_image)

        ocr_ms = round(
            (time.perf_counter() - ocr_started) * 1000,
            2,
        )

        log_event(
            "scan_stage_completed",
            job_id=job_id,
            stage="ocr",
            duration_ms=ocr_ms,
        )

        normalization_started = time.perf_counter()

        job.status = "normalizing"
        job.progress = 70
        db.commit()

        candidates = build_book_candidates(
            ocr_result,
            image_width=image_metrics["processed_width"],
        )

        normalization_ms = round(
            (time.perf_counter() - normalization_started) * 1000,
            2,
        )

        log_event(
            "scan_stage_completed",
            job_id=job_id,
            stage="normalization",
            duration_ms=normalization_ms,
            candidate_count=len(candidates),
        )

        matching_started = time.perf_counter()

        job.status = "matching_metadata"
        job.progress = 80
        db.commit()

        matching_result = match_book_candidates(
            candidates,
            ocr_result,
        )

        matching_ms = round(
            (time.perf_counter() - matching_started) * 1000,
            2,
        )

        matched_book_count = len(
            matching_result["books"]
        )

        unmatched_count = len(
            matching_result["unmatched_candidates"]
        )

        log_event(
            "scan_stage_completed",
            job_id=job_id,
            stage="metadata_matching",
            duration_ms=matching_ms,
            matched_book_count=matched_book_count,
            unmatched_candidate_count=unmatched_count,
            metadata_cache=matching_result["cache"],
        )

        job.status = "completed"
        job.progress = 100
        job.error_message = None
        job.result_json = {
            "simulated": False,
            "pipeline_stage": "metadata_matching",
            "image_metrics": image_metrics,
            "ocr": ocr_result,
            "candidate_count": len(candidates),
            "candidates": candidates,
            "books": matching_result["books"],
            "unmatched_candidates": matching_result[
                "unmatched_candidates"
            ],
            "metadata_cache": matching_result["cache"],
        }
        job.completed_at = datetime.now(timezone.utc)
        db.commit()

        total_ms = round(
            (time.perf_counter() - task_started) * 1000,
            2,
        )

        log_event(
            "scan_completed",
            job_id=job_id,
            duration_ms=total_ms,
            matched_book_count=matched_book_count,
            candidate_count=len(candidates),
        )

    except TRANSIENT_SCAN_EXCEPTIONS as exc:
        db.rollback()

        current_retry = self.request.retries

        if current_retry >= MAX_TASK_RETRIES:
            _mark_job_failed(
                job_uuid,
                (
                    "Scan failed after bounded retries: "
                    f"{exc}"
                ),
            )

            log_event(
                "scan_retry_exhausted",
                level=logging.ERROR,
                job_id=job_id,
                retries=current_retry,
                error_type=type(exc).__name__,
                error_message=str(exc),
            )

            raise

        countdown = _retry_countdown(current_retry)
        retry_number = current_retry + 1

        _update_retry_state(
            job_uuid,
            retry_number,
            countdown,
        )

        log_event(
            "scan_retry_scheduled",
            level=logging.WARNING,
            job_id=job_id,
            retry_number=retry_number,
            max_retries=MAX_TASK_RETRIES,
            countdown_seconds=countdown,
            error_type=type(exc).__name__,
            error_message=str(exc),
        )

        raise self.retry(
            exc=exc,
            countdown=countdown,
            max_retries=MAX_TASK_RETRIES,
        )

    except Exception as exc:
        db.rollback()

        _mark_job_failed(
            job_uuid,
            str(exc),
        )

        log_event(
            "scan_failed",
            level=logging.ERROR,
            job_id=job_id,
            error_type=type(exc).__name__,
            error_message=str(exc),
        )

        raise

    finally:
        db.close()