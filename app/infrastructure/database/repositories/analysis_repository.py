"""Analysis-run lifecycle persistence adapter (ADR 004)."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.infrastructure.database.models.analysis import AnalysisRun, AnalysisStatus
from app.infrastructure.database.models.version import ProjectVersion


class AnalysisRepository:
    """Each transition below commits on its own: a run created before the
    calculation, or marked `failed` after it, must survive even if the
    indicator persistence step that follows is rolled back.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def create_pending(
        self, project_version_id: uuid.UUID, *, config: dict[str, Any]
    ) -> uuid.UUID:
        run = AnalysisRun(
            project_version_id=project_version_id, status=AnalysisStatus.PENDING, config=config
        )
        self._session.add(run)
        self._session.commit()
        self._session.refresh(run)
        return run.id

    def mark_running(self, run_id: uuid.UUID) -> None:
        run = self._session.get(AnalysisRun, run_id)
        if run is None:
            return
        run.status = AnalysisStatus.RUNNING
        run.started_at = datetime.now(UTC)
        self._session.commit()

    def mark_completed(self, run_id: uuid.UUID, *, duration_ms: int) -> None:
        run = self._session.get(AnalysisRun, run_id)
        if run is None:
            return
        run.status = AnalysisStatus.COMPLETED
        run.completed_at = datetime.now(UTC)
        run.duration_ms = duration_ms
        self._session.commit()

    def list_runs(self, project_version_id: uuid.UUID) -> list[AnalysisRun]:
        """Newest-first history of runs for one version (Fase 0, nota 28)."""
        return list(
            self._session.query(AnalysisRun)
            .filter(AnalysisRun.project_version_id == project_version_id)
            .order_by(AnalysisRun.run_at.desc())
            .all()
        )

    def get_run_for_project(
        self, project_id: uuid.UUID, run_id: uuid.UUID
    ) -> AnalysisRun | None:
        """Fetch one run, scoped to the project across all its versions -
        `None` when the run doesn't exist or belongs to another project."""
        return (
            self._session.query(AnalysisRun)
            .join(ProjectVersion, AnalysisRun.project_version_id == ProjectVersion.id)
            .filter(AnalysisRun.id == run_id, ProjectVersion.project_id == project_id)
            .first()
        )

    def mark_failed(
        self, run_id: uuid.UUID, *, error: dict[str, Any], duration_ms: int
    ) -> None:
        run = self._session.get(AnalysisRun, run_id)
        if run is None:
            return
        run.status = AnalysisStatus.FAILED
        run.completed_at = datetime.now(UTC)
        run.duration_ms = duration_ms
        run.error = error
        self._session.commit()
