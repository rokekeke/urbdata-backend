import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.v1.schemas.analysis import IndicatorResultOut, indicator_result_to_out
from app.application.analysis.get_results import GetResults
from app.domain.analysis.exceptions import ProjectNotFoundError
from app.infrastructure.database.repositories.indicator_repository import IndicatorRepository
from app.infrastructure.database.repositories.project_repository import ProjectRepository
from app.infrastructure.database.session import get_db

router = APIRouter(prefix="/projects", tags=["results"])


@router.get("/{project_id}/results", response_model=list[IndicatorResultOut])
def get_results(project_id: uuid.UUID, db: Session = Depends(get_db)) -> list[IndicatorResultOut]:
    try:
        ProjectRepository(db).get(project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc

    results = GetResults(repository=IndicatorRepository(db)).execute(project_id)
    return [indicator_result_to_out(result) for result in results]
