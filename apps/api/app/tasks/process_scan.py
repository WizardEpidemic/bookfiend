# Processes BookFiend scan jobs asynchronously and persists job lifecycle updates.

import time
import uuid
from datetime import datetime, timezone

from app.celery_app import celery_app
from app.db import SessionLocal
from app.models.scan_job import ScanJob


@celery_app.task(name="bookfiend.process_scan")
def process_scan(job_id: str) -> None:
    job_uuid = uuid.UUID(job_id)
    db = SessionLocal()

    try:
        job = db.get(ScanJob, job_uuid)

        if job is None:
            return

        job.status = "processing"
        job.progress = 25
        db.commit()

        # Temporary Phase-2 workload. Real OCR replaces this simulated delay.
        time.sleep(4)

        job.status = "completed"
        job.progress = 100
        job.result_json = {
            "simulated": True,
            "books": [
                {
                    "title": "Atomic Habits",
                    "author": "James Clear",
                    "confidence": 0.98,
                    "source": "phase_2_fixture",
                }
            ],
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