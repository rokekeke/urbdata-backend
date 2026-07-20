"""ExportRepository lifecycle (item 5.4, ADR 014 Decisao 6) against real
PostGIS. Uses the real `build_export_snapshot` (5.3) to produce the
`config` payload persisted here - proves the JSONB round-trips the full
nested structure (UUIDs as strings, enums as their values) correctly
through Postgres, not just an arbitrary stub dict.
"""

import json
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.domain.cartography.document import MapDocumentConfig
from app.domain.cartography.export_snapshot import (
    ExportImageSpec,
    ExportRendererInfo,
    ImageRatio,
    ImageResolution,
    build_export_snapshot,
)
from app.infrastructure.database.models import AnalysisRun, Project, ProjectVersion
from app.infrastructure.database.models.export import Export, ExportStatus
from app.infrastructure.database.repositories.export_repository import ExportRepository

TEST_DATABASE_URL = os.getenv("URBDATA_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="URBDATA_TEST_DATABASE_URL is required for database integration tests",
)

FIXTURE = Path(__file__).parent.parent / "fixtures" / "map_documents" / "v1_example.json"


def _session_factory() -> sessionmaker[Session]:
    assert TEST_DATABASE_URL is not None
    engine = create_engine(TEST_DATABASE_URL)
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def _new_project_with_version(session: Session) -> tuple[uuid.UUID, uuid.UUID]:
    project = Project(name="Repositorio Export (teste)")
    session.add(project)
    session.flush()
    version = ProjectVersion(project_id=project.id, name="Versao 1", number=1)
    session.add(version)
    session.commit()
    return project.id, version.id


def _new_analysis_run(session: Session, version_id: uuid.UUID) -> uuid.UUID:
    run = AnalysisRun(project_version_id=version_id)
    session.add(run)
    session.commit()
    return run.id


def _sample_config() -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(FIXTURE.read_text(encoding="utf-8"))
    document_config = MapDocumentConfig.model_validate(payload)
    return build_export_snapshot(
        document_id=uuid.uuid4(),
        document_revision=1,
        document_config=document_config,
        project_version_id=uuid.uuid4(),
        analysis_run_id=None,
        legend=True,
        image=ExportImageSpec(
            ratio_id=ImageRatio.SCREEN,
            resolution_id=ImageResolution.TWO_X,
            width_px=1600,
            height_px=900,
        ),
        renderer=ExportRendererInfo(maplibre_version="4.7.1", frontend_version="0.1.0"),
        requested_at=datetime(2026, 7, 20, 12, 0, 0, tzinfo=UTC),
    )


class TestCreatePending:
    def test_persists_config_and_defaults(self) -> None:
        Session = _session_factory()
        with Session() as session:
            _, version_id = _new_project_with_version(session)
            analysis_run_id = _new_analysis_run(session, version_id)
            config = _sample_config()

            export = ExportRepository(session).create_pending(
                project_version_id=version_id,
                analysis_run_id=analysis_run_id,
                format="png",
                config=config,
            )

            assert export.id is not None
            assert export.project_version_id == version_id
            assert export.analysis_run_id == analysis_run_id
            assert export.format == "png"
            assert export.status == ExportStatus.PENDING
            assert export.file_path is None
            assert export.completed_at is None
            assert export.error is None
            assert export.config == config

    def test_analysis_run_id_is_optional(self) -> None:
        Session = _session_factory()
        with Session() as session:
            _, version_id = _new_project_with_version(session)

            export = ExportRepository(session).create_pending(
                project_version_id=version_id,
                analysis_run_id=None,
                format="png",
                config=_sample_config(),
            )

            assert export.analysis_run_id is None


class TestMarkCompleted:
    def test_sets_file_path_status_and_completed_at(self) -> None:
        Session = _session_factory()
        with Session() as session:
            _, version_id = _new_project_with_version(session)
            repo = ExportRepository(session)
            export = repo.create_pending(
                project_version_id=version_id,
                analysis_run_id=None,
                format="png",
                config=_sample_config(),
            )

            repo.mark_completed(export.id, file_path="exports/abc123.png")

            reloaded = session.get(Export, export.id)
            assert reloaded is not None
            assert reloaded.status == ExportStatus.COMPLETED
            assert reloaded.file_path == "exports/abc123.png"
            assert reloaded.completed_at is not None

    def test_noop_when_export_does_not_exist(self) -> None:
        Session = _session_factory()
        with Session() as session:
            ExportRepository(session).mark_completed(uuid.uuid4(), file_path="x.png")


class TestMarkFailed:
    def test_sets_error_status_and_completed_at(self) -> None:
        Session = _session_factory()
        with Session() as session:
            _, version_id = _new_project_with_version(session)
            repo = ExportRepository(session)
            export = repo.create_pending(
                project_version_id=version_id,
                analysis_run_id=None,
                format="png",
                config=_sample_config(),
            )

            error = {
                "error": "invalid_png",
                "message": "Arquivo nao e um PNG valido.",
                "context": {},
            }
            repo.mark_failed(export.id, error=error)

            reloaded = session.get(Export, export.id)
            assert reloaded is not None
            assert reloaded.status == ExportStatus.FAILED
            assert reloaded.error == error
            assert reloaded.completed_at is not None
            assert reloaded.file_path is None

    def test_noop_when_export_does_not_exist(self) -> None:
        Session = _session_factory()
        with Session() as session:
            ExportRepository(session).mark_failed(uuid.uuid4(), error={"error": "x"})


class TestGetForProject:
    def test_returns_the_export_when_owned(self) -> None:
        Session = _session_factory()
        with Session() as session:
            project_id, version_id = _new_project_with_version(session)
            repo = ExportRepository(session)
            export = repo.create_pending(
                project_version_id=version_id,
                analysis_run_id=None,
                format="png",
                config=_sample_config(),
            )

            found = repo.get_for_project(project_id, export.id)

            assert found is not None
            assert found.id == export.id

    def test_returns_none_for_a_different_project(self) -> None:
        Session = _session_factory()
        with Session() as session:
            _, version_id = _new_project_with_version(session)
            other_project_id, _ = _new_project_with_version(session)
            repo = ExportRepository(session)
            export = repo.create_pending(
                project_version_id=version_id,
                analysis_run_id=None,
                format="png",
                config=_sample_config(),
            )

            assert repo.get_for_project(other_project_id, export.id) is None

    def test_returns_none_for_a_nonexistent_export(self) -> None:
        Session = _session_factory()
        with Session() as session:
            project_id, _ = _new_project_with_version(session)

            assert ExportRepository(session).get_for_project(project_id, uuid.uuid4()) is None
