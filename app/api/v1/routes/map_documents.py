"""MapDocument CRUD HTTP routes (item 4.6, ADR 014 Decisao 8).

Thin wiring only: every actual rule already lives one layer down -
structural validation in Pydantic (`MapDocumentConfig`, item 2),
contextual validation and optimistic concurrency in
`MapDocumentRepository` (items 4.2-4.5). This module just resolves the
URL-scoped project/version, builds `LayerContext` via
`build_layer_contexts`, and maps `AnalysisError.code` to an HTTP status
(same `_STATUS_BY_ERROR_CODE` convention as `analysis.py`/`selection.py`).

409 body: ADR 014 Decisao 4 says the response carries "o documento atual
no corpo" - resolved this session as `context.current_document` inside the
project's single `{detail: {error, message, context}}` envelope (not a
bare `MapDocumentOut`), so `test_openapi_contract.py`'s guard that every
declared 4xx uses `ErrorEnvelopeOut` needs no route-specific exception.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.v1.errors import error_detail
from app.api.v1.schemas.error import CONFLICT, NOT_FOUND, UNPROCESSABLE
from app.api.v1.schemas.map_document import (
    MapDocumentCreateIn,
    MapDocumentOut,
    MapDocumentUpdateIn,
    MapDocumentWithWarningsOut,
    map_document_to_out,
    map_document_with_warnings_to_out,
)
from app.domain.analysis.exceptions import AnalysisError
from app.domain.cartography.exceptions import MapDocumentRevisionConflictError
from app.infrastructure.database.repositories.feature_repository import FeatureRepository
from app.infrastructure.database.repositories.map_document_repository import (
    MapDocumentRepository,
    build_layer_contexts,
)
from app.infrastructure.database.repositories.project_repository import ProjectRepository
from app.infrastructure.database.session import get_db

router = APIRouter(prefix="/projects/{project_id}", tags=["map-documents"])

_STATUS_BY_ERROR_CODE: dict[str, int] = {
    "project_not_found": 404,
    "project_version_not_found": 404,
    "map_document_context_invalid": 422,
}


def _raise_mapped(exc: AnalysisError) -> None:
    status_code = _STATUS_BY_ERROR_CODE.get(exc.code, 500)
    raise HTTPException(
        status_code=status_code, detail=error_detail(exc.code, exc.message, exc.context)
    ) from exc


def _not_found(document_id: uuid.UUID) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail=error_detail(
            "map_document_not_found",
            "Documento cartografico nao encontrado neste projeto.",
            {"document_id": str(document_id)},
        ),
    )


@router.post(
    "/versions/{version_id}/documents",
    response_model=MapDocumentOut,
    status_code=201,
    responses={**NOT_FOUND, **UNPROCESSABLE},
)
def create_map_document(
    project_id: uuid.UUID,
    version_id: uuid.UUID,
    payload: MapDocumentCreateIn,
    db: Session = Depends(get_db),
) -> MapDocumentOut:
    try:
        ProjectRepository(db).get_version_for_project(project_id, version_id)
        layer_contexts = build_layer_contexts(FeatureRepository(db), version_id, payload.config)
        document = MapDocumentRepository(db).create(
            project_version_id=version_id,
            name=payload.name,
            config=payload.config,
            layer_contexts=layer_contexts,
        )
    except AnalysisError as exc:
        _raise_mapped(exc)
        raise  # unreachable, satisfies mypy's control-flow analysis
    return map_document_to_out(document)


@router.get(
    "/versions/{version_id}/documents",
    response_model=list[MapDocumentOut],
    responses={**NOT_FOUND},
)
def list_map_documents(
    project_id: uuid.UUID, version_id: uuid.UUID, db: Session = Depends(get_db)
) -> list[MapDocumentOut]:
    try:
        ProjectRepository(db).get_version_for_project(project_id, version_id)
    except AnalysisError as exc:
        _raise_mapped(exc)
        raise
    documents = MapDocumentRepository(db).list_for_version(version_id)
    return [map_document_to_out(document) for document in documents]


@router.get(
    "/documents/{document_id}",
    response_model=MapDocumentWithWarningsOut,
    responses={**NOT_FOUND},
)
def get_map_document(
    project_id: uuid.UUID, document_id: uuid.UUID, db: Session = Depends(get_db)
) -> MapDocumentWithWarningsOut:
    result = MapDocumentRepository(db).get_with_integrity_warnings(
        project_id, document_id, FeatureRepository(db)
    )
    if result is None:
        raise _not_found(document_id)
    document, warnings = result
    return map_document_with_warnings_to_out(document, warnings)


@router.put(
    "/documents/{document_id}",
    response_model=MapDocumentOut,
    responses={**NOT_FOUND, **UNPROCESSABLE, **CONFLICT},
)
def update_map_document(
    project_id: uuid.UUID,
    document_id: uuid.UUID,
    payload: MapDocumentUpdateIn,
    db: Session = Depends(get_db),
) -> MapDocumentOut:
    document = MapDocumentRepository(db).get_for_project(project_id, document_id)
    if document is None:
        raise _not_found(document_id)

    layer_contexts = build_layer_contexts(
        FeatureRepository(db), document.project_version_id, payload.config
    )
    try:
        updated = MapDocumentRepository(db).update(
            document,
            expected_revision=payload.expected_revision,
            name=payload.name,
            config=payload.config,
            layer_contexts=layer_contexts,
        )
    except MapDocumentRevisionConflictError as exc:
        # `document` was refreshed in place by the repository to the true
        # current row state before this was raised - reuse it instead of a
        # second query (ADR 014 Decisao 4/8).
        current_document = map_document_to_out(document).model_dump(mode="json")
        context = {**exc.context, "current_document": current_document}
        raise HTTPException(
            status_code=409, detail=error_detail(exc.code, exc.message, context)
        ) from exc
    except AnalysisError as exc:
        _raise_mapped(exc)
        raise
    return map_document_to_out(updated)


@router.delete("/documents/{document_id}", status_code=204, responses={**NOT_FOUND})
def delete_map_document(
    project_id: uuid.UUID, document_id: uuid.UUID, db: Session = Depends(get_db)
) -> None:
    document = MapDocumentRepository(db).get_for_project(project_id, document_id)
    if document is None:
        raise _not_found(document_id)
    MapDocumentRepository(db).delete(document)
