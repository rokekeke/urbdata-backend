import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.infrastructure.database.models.version import ProjectVersionStatus


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


class ProjectVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    number: int
    description: str | None
    parent_version_id: uuid.UUID | None
    status: ProjectVersionStatus
    created_at: datetime
    # Not a column: computed at the API edge from the same newest-first rule
    # `ProjectRepository.current_version_id` applies (nota 28 - the frontend
    # must never have to guess which version is active).
    is_current: bool
