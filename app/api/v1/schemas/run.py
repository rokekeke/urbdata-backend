import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.infrastructure.database.models.analysis import AnalysisStatus


class AnalysisRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_version_id: uuid.UUID
    status: AnalysisStatus
    run_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    duration_ms: int | None
    config: dict[str, Any]
    error: dict[str, Any] | None
