import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base, pg_enum


class AnalysisStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class IndicatorClassification(StrEnum):
    ABAIXO = "abaixo"
    DENTRO = "dentro"
    ACIMA = "acima"


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("project_versions.id"), nullable=False
    )
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    status: Mapped[AnalysisStatus] = mapped_column(
        pg_enum(AnalysisStatus, name="analysis_status"), default=AnalysisStatus.PENDING
    )
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column()
    error: Mapped[dict[str, Any] | None] = mapped_column(JSONB)


class IndicatorResult(Base):
    __tablename__ = "indicator_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    analysis_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("analysis_runs.id"), nullable=False
    )
    theme: Mapped[str] = mapped_column(String, nullable=False)
    indicator_code: Mapped[str] = mapped_column(String, nullable=False)
    formula_version: Mapped[str] = mapped_column(String, nullable=False)
    value: Mapped[Decimal | None] = mapped_column(Numeric)
    value_json: Mapped[Any | None] = mapped_column(JSONB)
    unit: Mapped[str | None] = mapped_column(String)
    metric_crs: Mapped[str | None] = mapped_column(String)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    source_layers: Mapped[list[str]] = mapped_column(JSONB, default=list)
    warnings: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    reference_min: Mapped[Decimal | None] = mapped_column(Numeric)
    reference_max: Mapped[Decimal | None] = mapped_column(Numeric)
    classification: Mapped[IndicatorClassification | None] = mapped_column(
        pg_enum(IndicatorClassification, name="indicator_classification")
    )
    contributing_feature_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)


class ReferenceParameter(Base):
    __tablename__ = "reference_parameters"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    indicator_code: Mapped[str] = mapped_column(String, nullable=False)
    theme: Mapped[str] = mapped_column(String, nullable=False)
    value_min: Mapped[Decimal | None] = mapped_column(Numeric)
    value_max: Mapped[Decimal | None] = mapped_column(Numeric)
    unit: Mapped[str | None] = mapped_column(String)
    source: Mapped[str | None] = mapped_column(String)
    typology_scope: Mapped[str | None] = mapped_column(String)
    is_default: Mapped[bool] = mapped_column(Boolean, default=True)
