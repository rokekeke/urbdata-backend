import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.domain.cartography.export_snapshot import ImageRatio, ImageResolution
from app.infrastructure.database.models.export import ExportStatus


class ExportImageSpecIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ratio_id: ImageRatio
    resolution_id: ImageResolution
    width_px: int = Field(gt=0)
    height_px: int = Field(gt=0)


class ExportRendererInfoIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    maplibre_version: str = Field(min_length=1)
    frontend_version: str = Field(min_length=1)


class ExportCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    legend: bool
    image: ExportImageSpecIn
    renderer: ExportRendererInfoIn
    analysis_run_id: uuid.UUID | None = None


class ExportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_version_id: uuid.UUID
    analysis_run_id: uuid.UUID | None
    format: str
    status: ExportStatus
    config: dict[str, Any]
    file_path: str | None
    error: dict[str, Any] | None
    created_at: datetime
    completed_at: datetime | None
