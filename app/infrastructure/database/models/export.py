import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base, pg_enum


class ExportStatus(StrEnum):
    """Mirrors AnalysisStatus's vocabulary (checkpoint 5.1, ADR 014 Decisao
    6) for consistency, even though no code path sets RUNNING in v1 - the
    backend never renders, it only freezes the snapshot (PENDING) and
    later archives the client-rendered artifact (COMPLETED/FAILED)."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class Export(Base):
    __tablename__ = "exports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("project_versions.id"), nullable=False
    )
    analysis_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("analysis_runs.id")
    )
    format: Mapped[str] = mapped_column(String, nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    file_path: Mapped[str | None] = mapped_column(String)
    status: Mapped[ExportStatus] = mapped_column(
        pg_enum(ExportStatus, name="export_status"), default=ExportStatus.PENDING
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
