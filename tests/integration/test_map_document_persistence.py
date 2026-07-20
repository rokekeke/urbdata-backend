"""ORM-level persistence of MapDocument (item 3.4, ADR 014).

Scope boundary: this only proves the storage shape works - JSONB
round-trip, FK enforcement, revision default. No HTTP route, no
revision-conflict/409 business logic (that is item 4, the CRUD).

Uses its own engine/session against URBDATA_TEST_DATABASE_URL, independent
of the app's cached settings/session module - same isolation pattern as
test_migrations.py, so this file has no cross-test cache risk.
"""

import json
import os
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.domain.cartography.document import MapDocumentConfig
from app.infrastructure.database.models import MapDocument, Project, ProjectVersion

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


def _new_project_version(session: Session) -> uuid.UUID:
    project = Project(name="Persistencia MapDocument (teste)")
    session.add(project)
    session.flush()
    version = ProjectVersion(project_id=project.id, name="Versao 1", number=1)
    session.add(version)
    session.commit()
    return version.id


class TestJsonbRoundTrip:
    def test_validated_config_survives_storage_without_loss(self) -> None:
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        config = MapDocumentConfig.model_validate(payload)
        dumped = json.loads(config.model_dump_json())

        Session = _session_factory()
        with Session() as session:
            version_id = _new_project_version(session)
            document = MapDocument(
                project_version_id=version_id,
                name="Composicao de teste",
                config=dumped,
                schema_version=config.schema_version,
            )
            session.add(document)
            session.commit()
            document_id = document.id

        # Fresh session/query - not the same in-memory object, forces a
        # real read back from PostGIS.
        with Session() as session:
            reloaded = session.get(MapDocument, document_id)
            assert reloaded is not None
            assert reloaded.config == dumped
            # The stored JSONB re-validates cleanly through the same
            # Pydantic contract used to build it (item 2).
            reloaded_config = MapDocumentConfig.model_validate(reloaded.config)
            assert reloaded_config == config


class TestForeignKeyEnforcement:
    def test_nonexistent_project_version_id_is_rejected(self) -> None:
        Session = _session_factory()
        with Session() as session:
            document = MapDocument(
                project_version_id=uuid.uuid4(),
                name="Documento orfao",
                config={"schema_version": "1"},
                schema_version="1",
            )
            session.add(document)
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()


class TestRevisionDefault:
    def test_revision_defaults_to_one(self) -> None:
        Session = _session_factory()
        with Session() as session:
            version_id = _new_project_version(session)
            document = MapDocument(
                project_version_id=version_id,
                name="Documento sem revision explicita",
                config={"schema_version": "1"},
                schema_version="1",
            )
            session.add(document)
            session.commit()
            session.refresh(document)
            assert document.revision == 1
