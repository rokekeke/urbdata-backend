import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.v1.errors import error_detail
from app.api.v1.schemas.error import NOT_FOUND
from app.api.v1.schemas.project import ProjectCreate, ProjectOut, ProjectVersionOut
from app.domain.analysis.exceptions import ProjectNotFoundError
from app.infrastructure.database.repositories.project_repository import ProjectRepository
from app.infrastructure.database.session import get_db

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectOut, status_code=201)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)) -> object:
    repository = ProjectRepository(db)
    return repository.create(**payload.model_dump())


@router.get("", response_model=list[ProjectOut])
def list_projects(db: Session = Depends(get_db)) -> object:
    return ProjectRepository(db).list_all()


@router.get("/{project_id}", response_model=ProjectOut, responses={**NOT_FOUND})
def get_project(project_id: uuid.UUID, db: Session = Depends(get_db)) -> object:
    try:
        return ProjectRepository(db).get(project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=404, detail=error_detail(exc.code, exc.message, exc.context)
        ) from exc


@router.get(
    "/{project_id}/versions", response_model=list[ProjectVersionOut], responses={**NOT_FOUND}
)
def list_versions(project_id: uuid.UUID, db: Session = Depends(get_db)) -> object:
    """Newest-first; the first entry carries `is_current=True` - the same
    rule every other endpoint applies internally via `current_version_id`."""
    try:
        versions = ProjectRepository(db).list_versions(project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=404, detail=error_detail(exc.code, exc.message, exc.context)
        ) from exc
    return [
        ProjectVersionOut(
            id=version.id,
            project_id=version.project_id,
            name=version.name,
            number=version.number,
            description=version.description,
            parent_version_id=version.parent_version_id,
            status=version.status,
            created_at=version.created_at,
            is_current=(index == 0),
        )
        for index, version in enumerate(versions)
    ]
