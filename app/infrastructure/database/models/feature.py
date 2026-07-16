import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from geoalchemy2 import Geometry
from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base, pg_enum


class RelationMethod(StrEnum):
    ATTRIBUTE = "attribute"
    SPATIAL = "spatial"
    UNRESOLVED = "unresolved"
    NOT_APPLICABLE = "not_applicable"


class Feature(Base):
    __tablename__ = "features"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    layer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("project_layers.id"), nullable=False
    )
    project_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("project_versions.id"), nullable=False
    )
    # Preserves the original GeoJSON Feature.id (or a stable source key), separate
    # from this row's own primary key. The analysis engine's feature_id (see
    # app.domain.geospatial.layers.LoadedFeatureLayer) is always this table's `id`,
    # never `external_id` and never a GeoDataFrame positional index (ADR 005).
    external_id: Mapped[str | None] = mapped_column(String)
    geom: Mapped[Any] = mapped_column(Geometry(geometry_type="GEOMETRY", srid=4326), nullable=False)
    source_properties: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    mapped_properties: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    land_use: Mapped[str | None] = mapped_column(String, index=True)
    parent_quadra_feature_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("features.id")
    )
    parent_lote_feature_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("features.id")
    )
    relation_method: Mapped[RelationMethod] = mapped_column(
        pg_enum(RelationMethod, name="relation_method"), default=RelationMethod.NOT_APPLICABLE
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
