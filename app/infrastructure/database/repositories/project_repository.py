"""Project and active-version persistence adapter."""

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.domain.analysis.exceptions import ProjectNotFoundError, ProjectVersionNotFoundError
from app.infrastructure.database.models.project import Project
from app.infrastructure.database.models.version import ProjectVersion


class ProjectRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, **fields: Any) -> Project:
        project = Project(**fields)
        self._session.add(project)
        self._session.flush()
        # Every project is born with an initial version; layers, runs and
        # results always attach to a version, never to the project directly.
        self._session.add(ProjectVersion(project_id=project.id, name="Versao 1", number=1))
        self._session.commit()
        self._session.refresh(project)
        return project

    def list_all(self) -> list[Project]:
        return list(self._session.query(Project).order_by(Project.created_at.desc()).all())

    def get(self, project_id: uuid.UUID) -> Project:
        project = self._session.get(Project, project_id)
        if project is None:
            raise ProjectNotFoundError(
                "Project not found.", context={"project_id": str(project_id)}
            )
        return project

    def current_version_id(self, project_id: uuid.UUID) -> uuid.UUID:
        version = (
            self._session.query(ProjectVersion)
            .filter(ProjectVersion.project_id == project_id)
            .order_by(ProjectVersion.created_at.desc())
            .first()
        )
        if version is None:
            raise ProjectVersionNotFoundError(
                "Project has no active version.", context={"project_id": str(project_id)}
            )
        return version.id

    def list_versions(self, project_id: uuid.UUID) -> list[ProjectVersion]:
        """Newest-first versions of a project (Fase 0, nota 28: the frontend
        must not have to assume "latest created == active"). The first entry
        is the current one - the exact rule `current_version_id` applies."""
        self.get(project_id)
        return list(
            self._session.query(ProjectVersion)
            .filter(ProjectVersion.project_id == project_id)
            .order_by(ProjectVersion.created_at.desc())
            .all()
        )

    def get_version_for_project(
        self, project_id: uuid.UUID, version_id: uuid.UUID
    ) -> ProjectVersion:
        """Resolve one version scoped to a project - raises the same 404
        whether the version doesn't exist at all or belongs to a different
        project (never confirms cross-project existence). MapDocument
        routes need this: unlike `/analyze`/`/runs`, they take an explicit
        `version_id` in the URL rather than resolving "current" (ADR 014,
        Decisao 8)."""
        version = (
            self._session.query(ProjectVersion)
            .filter(ProjectVersion.id == version_id, ProjectVersion.project_id == project_id)
            .first()
        )
        if version is None:
            raise ProjectVersionNotFoundError(
                "Project version not found for this project.",
                context={"project_id": str(project_id), "version_id": str(version_id)},
            )
        return version
