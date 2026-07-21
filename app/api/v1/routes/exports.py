"""Export HTTP routes (item 5.5, ADR 014 Decisao 6 + checkpoint 5.1).

Two-call lifecycle locked in the 5.1 checkpoint: `POST .../exports`
creates and freezes the snapshot (status=pending, item 5.3's
`build_export_snapshot`); a second `POST .../exports/{id}/file` receives
the client-rendered PNG and completes it (item 5.4's `ExportRepository`).
No listing endpoint in v1 (5.1 decision #3) - only create, deliver, and
`GET` one item.

Deliberate v1 simplification, not yet flagged as a gap anywhere else:
delivering a file to an export that is already `completed`/`failed`
simply overwrites it - no transition guard. No product requirement calls
for rejecting a second delivery, and the two-call design already accepts
that a client can retry.
"""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.v1.errors import error_detail
from app.api.v1.schemas.error import NOT_FOUND, UNPROCESSABLE
from app.api.v1.schemas.export import ExportCreateIn, ExportOut
from app.domain.analysis.exceptions import AnalysisError
from app.domain.cartography.document import MapDocumentConfig, upcast_document
from app.domain.cartography.export_snapshot import (
    ExportImageSpec,
    ExportRendererInfo,
    build_export_snapshot,
)
from app.infrastructure.database.repositories.analysis_repository import AnalysisRepository
from app.infrastructure.database.repositories.export_repository import ExportRepository
from app.infrastructure.database.repositories.map_document_repository import (
    MapDocumentRepository,
)
from app.infrastructure.database.session import get_db
from app.infrastructure.storage.local import LocalStorage

router = APIRouter(prefix="/projects/{project_id}", tags=["exports"])

# Formato v1 (ADR 014 Decisao 6) - presets de prancha/DPI aguardam o urbanista.
_EXPORT_FORMAT = "png"
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

_STATUS_BY_ERROR_CODE: dict[str, int] = {
    "basemap_not_exportable": 422,
}


def _document_not_found(document_id: uuid.UUID) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail=error_detail(
            "map_document_not_found",
            "Documento cartografico nao encontrado neste projeto.",
            {"document_id": str(document_id)},
        ),
    )


def _export_not_found(export_id: uuid.UUID) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail=error_detail(
            "export_not_found",
            "Exportacao nao encontrada neste projeto.",
            {"export_id": str(export_id)},
        ),
    )


def _analysis_run_not_found(analysis_run_id: uuid.UUID) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail=error_detail(
            "analysis_run_not_found",
            "Execucao de analise nao encontrada neste projeto.",
            {"analysis_run_id": str(analysis_run_id)},
        ),
    )


@router.post(
    "/documents/{document_id}/exports",
    response_model=ExportOut,
    status_code=201,
    responses={**NOT_FOUND, **UNPROCESSABLE},
)
def create_export(
    project_id: uuid.UUID,
    document_id: uuid.UUID,
    payload: ExportCreateIn,
    db: Session = Depends(get_db),
) -> object:
    document = MapDocumentRepository(db).get_for_project(project_id, document_id)
    if document is None:
        raise _document_not_found(document_id)

    if payload.analysis_run_id is not None:
        run = AnalysisRepository(db).get_run_for_project(project_id, payload.analysis_run_id)
        if run is None:
            raise _analysis_run_not_found(payload.analysis_run_id)

    document_config = MapDocumentConfig.model_validate(upcast_document(document.config))
    try:
        snapshot = build_export_snapshot(
            document_id=document.id,
            document_revision=document.revision,
            document_config=document_config,
            project_version_id=document.project_version_id,
            analysis_run_id=payload.analysis_run_id,
            legend=payload.legend,
            image=ExportImageSpec(
                ratio_id=payload.image.ratio_id,
                resolution_id=payload.image.resolution_id,
                width_px=payload.image.width_px,
                height_px=payload.image.height_px,
            ),
            renderer=ExportRendererInfo(
                maplibre_version=payload.renderer.maplibre_version,
                frontend_version=payload.renderer.frontend_version,
            ),
            requested_at=datetime.now(UTC),
        )
    except AnalysisError as exc:
        status_code = _STATUS_BY_ERROR_CODE.get(exc.code, 500)
        raise HTTPException(
            status_code=status_code, detail=error_detail(exc.code, exc.message, exc.context)
        ) from exc

    return ExportRepository(db).create_pending(
        project_version_id=document.project_version_id,
        analysis_run_id=payload.analysis_run_id,
        format=_EXPORT_FORMAT,
        config=snapshot,
    )


@router.post(
    "/exports/{export_id}/file",
    response_model=ExportOut,
    responses={**NOT_FOUND, **UNPROCESSABLE},
)
def deliver_export_file(
    project_id: uuid.UUID,
    export_id: uuid.UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> object:
    repository = ExportRepository(db)
    export = repository.get_for_project(project_id, export_id)
    if export is None:
        raise _export_not_found(export_id)

    data = file.file.read()
    if not data.startswith(_PNG_MAGIC):
        repository.mark_failed(
            export_id,
            error=error_detail("invalid_png", "Arquivo enviado nao e um PNG valido."),
        )
        raise HTTPException(
            status_code=422,
            detail=error_detail(
                "invalid_png",
                "Arquivo enviado nao e um PNG valido.",
                {"export_id": str(export_id)},
            ),
        )

    file.file.seek(0)
    stored_path = LocalStorage().save(
        file.file, filename=f"{export_id}.png", subpath=str(project_id)
    )
    completed = repository.mark_completed(export_id, file_path=stored_path)
    assert completed is not None  # existence already confirmed above, same session
    return completed


@router.get("/exports/{export_id}", response_model=ExportOut, responses={**NOT_FOUND})
def get_export(
    project_id: uuid.UUID, export_id: uuid.UUID, db: Session = Depends(get_db)
) -> object:
    export = ExportRepository(db).get_for_project(project_id, export_id)
    if export is None:
        raise _export_not_found(export_id)
    return export
