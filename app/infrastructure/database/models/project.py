import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False)
    municipality: Mapped[str | None] = mapped_column(String)
    state: Mapped[str | None] = mapped_column(String)
    typology: Mapped[str | None] = mapped_column(String)
    approx_area_m2: Mapped[Decimal | None] = mapped_column(Numeric)
    description: Mapped[str | None] = mapped_column(Text)
    team: Mapped[str | None] = mapped_column(String)
    crs_hint: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
