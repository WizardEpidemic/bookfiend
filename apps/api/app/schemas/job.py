# Defines API request and response schemas for BookFiend scan-job operations.

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class ScanJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: str
    progress: int
    result_json: dict[str, Any] | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None