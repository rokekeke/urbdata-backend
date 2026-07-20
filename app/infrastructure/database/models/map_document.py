import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base


class MapDocument(Base):
    """Editable cartographic composition (ADR 014). `config` holds the
    payload validated by `app.domain.cartography.document.MapDocumentConfig`
    - this model does not re-validate structure, only persists it.
    Distinct from `StylePreset` (reusable style, not tied to a version) and
    `Export` (immutable snapshot + artifact) - see ADR 014, Decisao 1.
    """

    __tablename__ = "map_documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("project_versions.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    # Optimistic concurrency (ADR 014, Decisao 4): the server increments this
    # on every successful write; a PUT with a stale revision is rejected.
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    schema_version: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
