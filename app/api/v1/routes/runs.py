"""Analysis-run history endpoints (Fase 0, nota Obsidian 28/29).

Closes the gap where a failed run's id and error only existed in the
database: the frontend can now list executions and inspect one, including
the structured `error` payload with its context.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.v1.errors import error_detail
from app.api.v1.schemas.run import AnalysisRunOut
from app.domain.analysis.exceptions import ProjectNotFoundError, ProjectVersionNotFoundError
from app.infrastructure.database.repositories.analysis_repository import AnalysisRepository
from app.infrastructure.database.repositories.project_repository import ProjectRepository
from app.infrastructure.database.session import get_db

router = APIRouter(prefix="/projects", tags=["runs"])


@router.get("/{project_id}/runs", response_model=list[AnalysisRunOut])
def list_runs(project_id: uuid.UUID, db: Session = Depends(get_db)) -> object:
    try:
        version_id = ProjectRepository(db).current_version_id(project_id)
    except (ProjectNotFoundError, ProjectVersionNotFoundError) as exc:
        raise HTTPException(
            status_code=404, detail=error_detail(exc.code, exc.message, exc.context)
        ) from exc
    return AnalysisRepository(db).list_runs(version_id)


@router.get("/{project_id}/runs/{run_id}", response_model=AnalysisRunOut)
def get_run(project_id: uuid.UUID, run_id: uuid.UUID, db: Session = Depends(get_db)) -> object:
    try:
        ProjectRepository(db).get(project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=404, detail=error_detail(exc.code, exc.message, exc.context)
        ) from exc

    run = AnalysisRepository(db).get_run_for_project(project_id, run_id)
    if run is None:
        raise HTTPException(
            status_code=404,
            detail=error_detail(
                "analysis_run_not_found",
                "Execucao de analise nao encontrada neste projeto.",
                {"project_id": str(project_id), "run_id": str(run_id)},
            ),
        )
    return run
