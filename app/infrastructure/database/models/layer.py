import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base, pg_enum


class LayerType(StrEnum):
    PERIMETRO = "perimetro"
    QUADRAS = "quadras"
    LOTES = "lotes"
    SISTEMA_VIARIO = "sistema_viario"
    USO_SOLO = "uso_solo"
    AREAS_VERDES = "areas_verdes"
    EQUIPAMENTOS = "equipamentos"
    EDIFICACOES = "edificacoes"
    # Space-syntax unlink points: planar crossings that must not become
    # graph connections (e.g. viaducts, tunnels and grade separations).
    DESCONEXOES_VIARIAS = "desconexoes_viarias"
    # Single upload containing every territorial subdivision (lote, sistema
    # viario, avl, app, aci), tagged per-feature via the `macroarea`
    # attribute (ADR 008) - distinct from PERIMETRO, which stays the single
    # matricula boundary geometry.
    TERRITORIO = "territorio"


class LayerStatus(StrEnum):
    UPLOADED = "uploaded"
    MAPPED = "mapped"
    VALIDATED = "validated"
    ERROR = "error"


class ProjectLayer(Base):
    __tablename__ = "project_layers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("project_versions.id"), nullable=False
    )
    layer_type: Mapped[LayerType] = mapped_column(
        pg_enum(LayerType, name="layer_type"), nullable=False
    )
    source_filename: Mapped[str | None] = mapped_column(String)
    geometry_type: Mapped[str | None] = mapped_column(String)
    feature_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[LayerStatus] = mapped_column(
        pg_enum(LayerStatus, name="layer_status"), default=LayerStatus.UPLOADED
    )
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class LayerAttributeMapping(Base):
    __tablename__ = "layer_attribute_mappings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    layer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("project_layers.id"), nullable=False
    )
    internal_field: Mapped[str] = mapped_column(String, nullable=False)
    source_field: Mapped[str] = mapped_column(String, nullable=False)
