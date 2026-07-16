import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ProjectCreate(BaseModel):
    name: str
    municipality: str | None = None
    state: str | None = None
    typology: str | None = None
    approx_area_m2: float | None = None
    description: str | None = None
    team: str | None = None
    crs_hint: str | None = None


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    municipality: str | None
    state: str | None
    typology: str | None
    approx_area_m2: float | None
    description: str | None
    team: str | None
    created_at: datetime
