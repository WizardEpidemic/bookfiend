# Processes uploaded bookshelf images through BookFiend's asynchronous OCR pipeline.

import uuid
from datetime import datetime, timezone

from app.celery_app import celery_app
from app.db import SessionLocal
from app.models.scan_job import ScanJob
from ml.ocr import run_ocr
from ml.preprocessing import preprocess_image


@celery_app.task(name="bookfiend.process_scan")
def process_scan(job_id: str) -> None:
    job_uuid = uuid.UUID(job_id)
    db = SessionLocal()

    try:
        job = db.get(ScanJob, job_uuid)

        if job is None:
            return

        if not job.image_url:
            raise ValueError("Scan job does not have an uploaded image.")

        job.status = "processing"
        job.progress = 10
        db.commit()

        job.status = "preprocessing"
        job.progress = 25
        db.commit()

        processed_image, image_metrics = preprocess_image(job.image_url)

        job.status = "ocr"
        job.progress = 55
        db.commit()

        ocr_result = run_ocr(processed_image)

        job.status = "completed"
        job.progress = 100

        job.result_json = {
            "simulated": False,
            "pipeline_stage": "raw_ocr",
            "image_metrics": image_metrics,
            "ocr": ocr_result,
            "books": [],
            "unmatched_candidates": [],
        }

        job.completed_at = datetime.now(timezone.utc)

        db.commit()

    except Exception as exc:
        db.rollback()

        job = db.get(ScanJob, job_uuid)

        if job is not None:
            job.status = "failed"
            job.error_message = str(exc)
            db.commit()

        raise

    finally:
        db.close()