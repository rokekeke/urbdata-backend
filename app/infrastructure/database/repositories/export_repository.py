"""Export lifecycle persistence adapter (Fase 5, ADR 014 Decisao 6, item
5.4). Mirrors AnalysisRepository's pending -> completed/failed pattern
(ADR 004): each transition commits on its own, so a row created before
the client renders survives even if a later step fails.

`create_pending` does not build the snapshot itself - it persists
whatever `app.domain.cartography.export_snapshot.build_export_snapshot`
(item 5.3) already assembled. Keeps this module a plain persistence
adapter, no snapshot-construction knowledge duplicated here.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.infrastructure.database.models.export import Export, ExportStatus
from app.infrastructure.database.models.version import ProjectVersion


class ExportRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_pending(
        self,
        *,
        project_version_id: uuid.UUID,
        analysis_run_id: uuid.UUID | None,
        format: str,
        config: dict[str, Any],
    ) -> Export:
        export = Export(
            project_version_id=project_version_id,
            analysis_run_id=analysis_run_id,
            format=format,
            config=config,
            status=ExportStatus.PENDING,
        )
        self._session.add(export)
        self._session.commit()
        self._session.refresh(export)
        return export

    def mark_completed(self, export_id: uuid.UUID, *, file_path: str) -> Export | None:
        export = self._session.get(Export, export_id)
        if export is None:
            return None
        export.file_path = file_path
        export.status = ExportStatus.COMPLETED
        export.completed_at = datetime.now(UTC)
        self._session.commit()
        self._session.refresh(export)
        return export

    def mark_failed(self, export_id: uuid.UUID, *, error: dict[str, Any]) -> Export | None:
        export = self._session.get(Export, export_id)
        if export is None:
            return None
        export.status = ExportStatus.FAILED
        export.completed_at = datetime.now(UTC)
        export.error = error
        self._session.commit()
        self._session.refresh(export)
        return export

    def get_for_project(self, project_id: uuid.UUID, export_id: uuid.UUID) -> Export | None:
        """`None` when the export doesn't exist or belongs to a different
        project - the future route (5.5) turns that into a 404 without
        distinguishing the two (same pattern as
        `MapDocumentRepository.get_for_project`)."""
        return (
            self._session.query(Export)
            .join(ProjectVersion, Export.project_version_id == ProjectVersion.id)
            .filter(Export.id == export_id, ProjectVersion.project_id == project_id)
            .first()
        )
