"""Analysis-run history endpoints (Fase 0, nota Obsidian 28/29).

Closes the gap where a failed run's id and error only existed in the
database: the frontend can now list executions and inspect one, including
the structured `error` payload with its context.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.v1.errors import error_detail
from app.api.v1.schemas.analysis import IndicatorResultOut, indicator_result_to_out
from app.api.v1.schemas.error import NOT_FOUND
from app.api.v1.schemas.run import AnalysisRunOut
from app.application.analysis.get_results import GetResults
from app.domain.analysis.exceptions import ProjectNotFoundError, ProjectVersionNotFoundError
from app.infrastructure.database.repositories.analysis_repository import AnalysisRepository
from app.infrastructure.database.repositories.indicator_repository import IndicatorRepository
from app.infrastructure.database.repositories.project_repository import ProjectRepository
from app.infrastructure.database.session import get_db

router = APIRouter(prefix="/projects", tags=["runs"])


@router.get("/{project_id}/runs", response_model=list[AnalysisRunOut], responses={**NOT_FOUND})
def list_runs(project_id: uuid.UUID, db: Session = Depends(get_db)) -> object:
    try:
        version_id = ProjectRepository(db).current_version_id(project_id)
    except (ProjectNotFoundError, ProjectVersionNotFoundError) as exc:
        raise HTTPException(
            status_code=404, detail=error_detail(exc.code, exc.message, exc.context)
        ) from exc
    return AnalysisRepository(db).list_runs(version_id)


def _run_or_404(db: Session, project_id: uuid.UUID, run_id: uuid.UUID) -> object:
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


@router.get(
    "/{project_id}/runs/{run_id}", response_model=AnalysisRunOut, responses={**NOT_FOUND}
)
def get_run(project_id: uuid.UUID, run_id: uuid.UUID, db: Session = Depends(get_db)) -> object:
    return _run_or_404(db, project_id, run_id)


@router.get(
    "/{project_id}/runs/{run_id}/results",
    response_model=list[IndicatorResultOut],
    responses={**NOT_FOUND},
)
def get_run_results(
    project_id: uuid.UUID, run_id: uuid.UUID, db: Session = Depends(get_db)
) -> list[IndicatorResultOut]:
    """Results for one specific run, regardless of recency (closes the gap
    where `GET /results` only ever returned the latest completed run -
    Obsidian notes 87/97)."""
    _run_or_404(db, project_id, run_id)
    results = GetResults(repository=IndicatorRepository(db)).execute_for_run(run_id)
    return [indicator_result_to_out(result) for result in results]
