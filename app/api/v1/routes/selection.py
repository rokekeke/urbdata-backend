import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.v1.errors import error_detail
from app.api.v1.schemas.error import NOT_FOUND, UNPROCESSABLE
from app.api.v1.schemas.selection import SelectionRequest, SelectionResponse
from app.application.selection.select_related_features import (
    SelectRelatedFeatures,
    SelectRelatedFeaturesCommand,
)
from app.domain.analysis.exceptions import AnalysisError
from app.infrastructure.database.repositories.feature_repository import FeatureRepository
from app.infrastructure.database.repositories.project_repository import ProjectRepository
from app.infrastructure.database.session import get_db

router = APIRouter(prefix="/projects", tags=["selection"])

_STATUS_BY_ERROR_CODE: dict[str, int] = {
    "project_not_found": 404,
    "project_version_not_found": 404,
    "invalid_selection": 422,
    "duplicate_layer": 422,
}


@router.post(
    "/{project_id}/selection",
    response_model=SelectionResponse,
    responses={**NOT_FOUND, **UNPROCESSABLE},
)
def select_related_features(
    project_id: uuid.UUID, payload: SelectionRequest, db: Session = Depends(get_db)
) -> SelectionResponse:
    use_case = SelectRelatedFeatures(
        project_versions=ProjectRepository(db), selector=FeatureRepository(db)
    )
    command = SelectRelatedFeaturesCommand(
        project_id=project_id,
        target_layer_type=payload.target_layer_type,
        relation=payload.relation,
        source_feature_ids=(
            tuple(payload.source_feature_ids) if payload.source_feature_ids else None
        ),
        distance_m=payload.distance_m,
        attribute_filters=payload.attribute_filters,
    )
    try:
        feature_ids = use_case.execute(command)
    except AnalysisError as exc:
        status_code = _STATUS_BY_ERROR_CODE.get(exc.code, 500)
        raise HTTPException(
            status_code=status_code, detail=error_detail(exc.code, exc.message, exc.context)
        ) from exc

    return SelectionResponse(feature_ids=list(feature_ids), count=len(feature_ids))
