# Processes uploaded bookshelf images through OCR, normalization, metadata matching, and cached enrichment.

import uuid
from datetime import datetime, timezone

from app.celery_app import celery_app
from app.db import SessionLocal
from app.models.scan_job import ScanJob
from ml.match_books import (
    match_book_candidates,
)
from ml.normalize import (
    build_book_candidates,
)
from ml.ocr import run_ocr
from ml.preprocessing import (
    preprocess_image,
)


@celery_app.task(
    name="bookfiend.process_scan"
)
def process_scan(
    job_id: str,
) -> None:
    job_uuid = uuid.UUID(
        job_id
    )

    db = SessionLocal()

    try:
        job = db.get(
            ScanJob,
            job_uuid,
        )

        if job is None:
            return

        if not job.image_url:
            raise ValueError(
                "Scan job does not have an uploaded image."
            )

        job.status = "processing"
        job.progress = 10
        db.commit()

        job.status = "preprocessing"
        job.progress = 25
        db.commit()

        (
            processed_image,
            image_metrics,
        ) = preprocess_image(
            job.image_url
        )

        job.status = "ocr"
        job.progress = 50
        db.commit()

        ocr_result = run_ocr(
            processed_image
        )

        job.status = "normalizing"
        job.progress = 70
        db.commit()

        candidates = (
            build_book_candidates(
                ocr_result,
                image_width=(
                    image_metrics[
                        "processed_width"
                    ]
                ),
            )
        )

        job.status = (
            "matching_metadata"
        )
        job.progress = 80
        db.commit()

        matching_result = (
            match_book_candidates(
                candidates,
                ocr_result,
            )
        )

        job.status = "completed"
        job.progress = 100

        job.result_json = {
            "simulated": False,
            "pipeline_stage": (
                "metadata_matching"
            ),
            "image_metrics": (
                image_metrics
            ),
            "ocr": ocr_result,
            "candidate_count": len(
                candidates
            ),
            "candidates": candidates,
            "books": (
                matching_result[
                    "books"
                ]
            ),
            "unmatched_candidates": (
                matching_result[
                    "unmatched_candidates"
                ]
            ),
            "metadata_cache": (
                matching_result[
                    "cache"
                ]
            ),
        }

        job.completed_at = (
            datetime.now(
                timezone.utc
            )
        )

        db.commit()

    except Exception as exc:
        db.rollback()

        job = db.get(
            ScanJob,
            job_uuid,
        )

        if job is not None:
            job.status = "failed"
            job.error_message = str(
                exc
            )

            db.commit()

        raise

    finally:
        db.close()