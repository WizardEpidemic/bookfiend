# Implements HTTP endpoints for creating, queuing, and retrieving BookFiend scan jobs.

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.scan_job import ScanJob
from app.schemas.job import ScanJobResponse
from app.tasks.process_scan import process_scan


router = APIRouter(
    prefix="/jobs",
    tags=["jobs"],
)


@router.post(
    "",
    response_model=ScanJobResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_job(db: Session = Depends(get_db)) -> ScanJob:
    job = ScanJob(
        status="queued",
        progress=0,
    )

    db.add(job)
    db.commit()
    db.refresh(job)

    process_scan.delay(str(job.id))

    return job


@router.get(
    "/{job_id}",
    response_model=ScanJobResponse,
    responses={
        404: {
            "description": "Scan job not found.",
        }
    },
)
def get_job(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> ScanJob:
    job = db.get(ScanJob, job_id)

    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scan job not found.",
        )

    return job