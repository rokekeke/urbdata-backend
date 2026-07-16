import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.v1.schemas.project import ProjectCreate, ProjectOut
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


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: uuid.UUID, db: Session = Depends(get_db)) -> object:
    try:
        return ProjectRepository(db).get(project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc
