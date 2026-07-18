import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.v1.schemas.analysis import AnalyzeRequest, AnalyzeResponse, indicator_result_to_out
from app.application.analysis.analyze_project import AnalyzeProject, AnalyzeProjectCommand
from app.application.analysis.orchestrator import SynchronousAnalysisOrchestrator
from app.config.settings import get_indicator_defaults
from app.domain.analysis.exceptions import AnalysisError
from app.domain.indicators.catalog import build_registry
from app.infrastructure.database.repositories.analysis_repository import AnalysisRepository
from app.infrastructure.database.repositories.feature_repository import FeatureRepository
from app.infrastructure.database.repositories.indicator_repository import IndicatorRepository
from app.infrastructure.database.repositories.project_repository import ProjectRepository
from app.infrastructure.database.session import get_db

router = APIRouter(prefix="/projects", tags=["analysis"])

# The route only translates AnalysisError.code into an HTTP status; unlisted
# codes (unexpected failures included) fall back to 500.
_STATUS_BY_ERROR_CODE: dict[str, int] = {
    "project_not_found": 404,
    "project_version_not_found": 404,
    "required_layer_missing": 422,
    "duplicate_layer": 422,
    "invalid_geometry": 422,
    "metric_crs_selection_failed": 422,
    "indicator_calculation_failed": 422,
    "indicator_dependency_failed": 422,
}


@router.post("/{project_id}/analyze", response_model=AnalyzeResponse, status_code=201)
def analyze_project(
    project_id: uuid.UUID, payload: AnalyzeRequest, db: Session = Depends(get_db)
) -> AnalyzeResponse:
    defaults = get_indicator_defaults()
    orchestrator = SynchronousAnalysisOrchestrator(
        project_versions=ProjectRepository(db),
        layers=FeatureRepository(db),
        runs=AnalysisRepository(db),
        results=IndicatorRepository(db),
        registry=build_registry(),
        default_metric_crs=defaults.default_metric_crs,
        indicator_parameters={
            "road_snapping_tolerance_m": defaults.road_snapping_tolerance_m,
        },
    )
    command = AnalyzeProjectCommand(project_id=project_id, themes=tuple(payload.themes))
    try:
        outcome = AnalyzeProject(orchestrator).execute(command)
    except AnalysisError as exc:
        status_code = _STATUS_BY_ERROR_CODE.get(exc.code, 500)
        # exc.context carries the actionable detail (e.g. WHICH layer_type is
        # missing) - without it the client only sees a generic message.
        raise HTTPException(
            status_code=status_code,
            detail={"error": exc.code, "message": exc.message, "context": exc.context},
        ) from exc

    return AnalyzeResponse(
        analysis_run_id=outcome.run_id,
        status="completed",
        results=[indicator_result_to_out(result) for result in outcome.results],
    )
