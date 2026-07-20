"""MapDocumentRepository create/get/list + contextual validation wiring
(items 4.2/4.3, ADR 014 Decisao 3/8).

Exercises the repository directly (no HTTP route yet - that's 4.6) against
real PostGIS, with its own engine/session independent of the app's cached
settings module (same isolation pattern as test_migrations.py and
test_map_document_persistence.py). `TestBuildLayerContexts` and the
contextual-violation cases in `TestCreate` go through the real upload API
(`TestClient`) to get a genuine `ProjectLayer` + `Feature` - hand-rolling
a valid PostGIS geometry via raw ORM would be more brittle than reusing
the already-tested upload pipeline; everything else stays direct-session.
"""

import json
import os
import uuid
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.domain.analysis.exceptions import ProjectVersionNotFoundError
from app.domain.cartography.contextual_validation import LayerContext
from app.domain.cartography.document import MapDocumentConfig
from app.domain.cartography.exceptions import (
    MapDocumentContextError,
    MapDocumentRevisionConflictError,
)
from app.domain.cartography.representation_options import FieldOrigin, FieldStats
from app.infrastructure.database.models import MapDocument, Project, ProjectVersion
from app.infrastructure.database.repositories.feature_repository import FeatureRepository
from app.infrastructure.database.repositories.map_document_repository import (
    MapDocumentRepository,
    build_layer_contexts,
)
from app.infrastructure.database.repositories.project_repository import ProjectRepository
from app.main import create_app

TEST_DATABASE_URL = os.getenv("URBDATA_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="URBDATA_TEST_DATABASE_URL is required for database integration tests",
)

FIXTURE = Path(__file__).parent.parent / "fixtures" / "map_documents" / "v1_example.json"
LAYER_0_ID = "0b2f6d0e-49f2-4a11-9f2d-6a5f5b7f2c01"
LAYER_1_ID = "3c9a1f7b-2d64-4e08-8a4e-9d1c0b3e5f02"


def _session_factory() -> sessionmaker[Session]:
    assert TEST_DATABASE_URL is not None
    engine = create_engine(TEST_DATABASE_URL)
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def _new_project_with_version(session: Session) -> tuple[uuid.UUID, uuid.UUID]:
    project = Project(name="Repositorio MapDocument (teste)")
    session.add(project)
    session.flush()
    version = ProjectVersion(project_id=project.id, name="Versao 1", number=1)
    session.add(version)
    session.commit()
    return project.id, version.id


def _fixture_payload() -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return payload


def _sample_config() -> MapDocumentConfig:
    return MapDocumentConfig.model_validate(_fixture_payload())


def _quadra_id_stats() -> FieldStats:
    return FieldStats(
        field="quadra_id",
        origin=FieldOrigin.SOURCE,
        present_count=1,
        empty_count=0,
        cardinality=1,
        numeric_count=0,
        min_value=None,
        max_value=None,
        distinct_values=("Q1",),
    )


def _permissive_contexts() -> dict[uuid.UUID, LayerContext]:
    """Everything the fixture references resolves - used by tests that
    only care about create/list/get plumbing, not contextual validation
    itself (that is TestBuildLayerContextsAndCreateEndToEnd + the
    violation cases below)."""
    return {
        uuid.UUID(LAYER_0_ID): LayerContext(
            layer_type="territorio", fields={"quadra_id": _quadra_id_stats()}
        ),
        uuid.UUID(LAYER_1_ID): LayerContext(layer_type="territorio", fields={}),
    }


def _upload_territorio_layer_with_quadra_id(client: TestClient, project_id: str) -> str:
    square = [[
        [-52.001, -27.001], [-51.999, -27.001], [-51.999, -26.999],
        [-52.001, -26.999], [-52.001, -27.001],
    ]]
    response = client.post(
        f"/v1/projects/{project_id}/layers",
        data={"layer_type": "territorio"},
        files={
            "file": (
                "territorio.geojson",
                json.dumps(
                    {
                        "type": "FeatureCollection",
                        "features": [
                            {
                                "type": "Feature",
                                "geometry": {"type": "Polygon", "coordinates": square},
                                "properties": {"quadra_id": "Q1"},
                            }
                        ],
                    }
                ).encode(),
                "application/geo+json",
            )
        },
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


def _single_layer_config(layer_id: str) -> MapDocumentConfig:
    """One-layer document exercising both a property field (quadra_id,
    title_field + text block + table field) and a per-feature indicator
    (lots.frontage_length, representation + table field) - matches what
    `_upload_territorio_layer_with_quadra_id` provides."""
    payload = _fixture_payload()
    payload["layers"] = [payload["layers"][0]]
    payload["layers"][0]["layer_id"] = layer_id
    return MapDocumentConfig.model_validate(payload)


class TestCreate:
    def test_persists_config_and_defaults(self) -> None:
        Session = _session_factory()
        with Session() as session:
            _, version_id = _new_project_with_version(session)
            config = _sample_config()

            document = MapDocumentRepository(session).create(
                project_version_id=version_id,
                name="Composicao 1",
                config=config,
                layer_contexts=_permissive_contexts(),
            )

            assert document.id is not None
            assert document.revision == 1
            assert document.schema_version == "1"
            assert document.config == config.model_dump(mode="json")

    def test_rejects_when_contextual_violations_exist(self) -> None:
        Session = _session_factory()
        with Session() as session:
            _, version_id = _new_project_with_version(session)
            config = _sample_config()
            contexts = _permissive_contexts()
            del contexts[uuid.UUID(LAYER_1_ID)]  # simulate a missing layer

            with pytest.raises(MapDocumentContextError) as excinfo:
                MapDocumentRepository(session).create(
                    project_version_id=version_id,
                    name="Composicao invalida",
                    config=config,
                    layer_contexts=contexts,
                )

            violations = excinfo.value.context["violations"]
            assert violations == [
                {
                    "path": "layers[1].layer_id",
                    "code": "layer_not_in_version",
                    "message": (
                        f"Camada {LAYER_1_ID} nao pertence a esta versao do projeto."
                    ),
                }
            ]

    def test_rejected_document_is_not_persisted(self) -> None:
        Session = _session_factory()
        with Session() as session:
            _, version_id = _new_project_with_version(session)
            contexts = _permissive_contexts()
            del contexts[uuid.UUID(LAYER_1_ID)]

            with pytest.raises(MapDocumentContextError):
                MapDocumentRepository(session).create(
                    project_version_id=version_id,
                    name="Composicao invalida",
                    config=_sample_config(),
                    layer_contexts=contexts,
                )

            assert MapDocumentRepository(session).list_for_version(version_id) == []


class TestUpdate:
    def test_successful_update_increments_revision_and_persists_changes(self) -> None:
        Session = _session_factory()
        with Session() as session:
            _, version_id = _new_project_with_version(session)
            repo = MapDocumentRepository(session)
            document = repo.create(
                project_version_id=version_id,
                name="Original",
                config=_sample_config(),
                layer_contexts=_permissive_contexts(),
            )
            new_payload = _fixture_payload()
            new_payload["title"] = "Titulo atualizado"
            new_config = MapDocumentConfig.model_validate(new_payload)

            updated = repo.update(
                document,
                expected_revision=1,
                name="Renomeado",
                config=new_config,
                layer_contexts=_permissive_contexts(),
            )

            assert updated.revision == 2
            assert updated.name == "Renomeado"
            assert updated.config["title"] == "Titulo atualizado"

        # Fresh session/query - proves the write really committed.
        with Session() as session:
            reloaded = session.get(type(document), document.id)
            assert reloaded is not None
            assert reloaded.revision == 2
            assert reloaded.name == "Renomeado"

    def test_stale_revision_is_rejected_and_row_is_untouched(self) -> None:
        Session = _session_factory()
        with Session() as session:
            _, version_id = _new_project_with_version(session)
            repo = MapDocumentRepository(session)
            document = repo.create(
                project_version_id=version_id,
                name="Original",
                config=_sample_config(),
                layer_contexts=_permissive_contexts(),
            )

            with pytest.raises(MapDocumentRevisionConflictError) as excinfo:
                repo.update(
                    document,
                    expected_revision=999,
                    name="Nao deveria aplicar",
                    config=_sample_config(),
                    layer_contexts=_permissive_contexts(),
                )

            assert excinfo.value.context == {
                "document_id": str(document.id),
                "expected_revision": 999,
                "current_revision": 1,
            }
            # `document` was refreshed in place to the true current state -
            # the caller (route, 4.6) already holds what belongs in the
            # 409 body without a second query.
            assert document.revision == 1
            assert document.name == "Original"

        with Session() as session:
            reloaded = session.get(type(document), document.id)
            assert reloaded is not None
            assert reloaded.revision == 1
            assert reloaded.name == "Original"

    def test_contextual_violation_is_rejected_and_row_is_untouched(self) -> None:
        Session = _session_factory()
        with Session() as session:
            _, version_id = _new_project_with_version(session)
            repo = MapDocumentRepository(session)
            document = repo.create(
                project_version_id=version_id,
                name="Original",
                config=_sample_config(),
                layer_contexts=_permissive_contexts(),
            )
            broken_contexts = _permissive_contexts()
            del broken_contexts[uuid.UUID(LAYER_1_ID)]

            with pytest.raises(MapDocumentContextError):
                repo.update(
                    document,
                    expected_revision=1,
                    name="Nao deveria aplicar",
                    config=_sample_config(),
                    layer_contexts=broken_contexts,
                )

        with Session() as session:
            reloaded = session.get(type(document), document.id)
            assert reloaded is not None
            assert reloaded.revision == 1
            assert reloaded.name == "Original"

    def test_concurrent_writers_only_one_wins(self) -> None:
        """Two independent sessions both start from revision=1 - the real
        hazard optimistic concurrency exists to prevent (a Python-side
        read-then-compare would let both "pass"). The atomic
        `UPDATE ... WHERE revision = ...` must let exactly one through."""
        Session = _session_factory()
        with Session() as setup_session:
            _, version_id = _new_project_with_version(setup_session)
            document_id = MapDocumentRepository(setup_session).create(
                project_version_id=version_id,
                name="Original",
                config=_sample_config(),
                layer_contexts=_permissive_contexts(),
            ).id

        with Session() as session_a, Session() as session_b:
            document_a = session_a.get(MapDocument, document_id)
            document_b = session_b.get(MapDocument, document_id)
            assert document_a is not None and document_b is not None

            MapDocumentRepository(session_a).update(
                document_a,
                expected_revision=1,
                name="Vencedor",
                config=_sample_config(),
                layer_contexts=_permissive_contexts(),
            )

            with pytest.raises(MapDocumentRevisionConflictError) as excinfo:
                MapDocumentRepository(session_b).update(
                    document_b,
                    expected_revision=1,
                    name="Perdedor",
                    config=_sample_config(),
                    layer_contexts=_permissive_contexts(),
                )
            assert excinfo.value.context["current_revision"] == 2

        with Session() as session:
            final = session.get(MapDocument, document_id)
            assert final is not None
            assert final.revision == 2
            assert final.name == "Vencedor"


class TestListForVersion:
    def test_lists_only_documents_of_that_version_newest_first(self) -> None:
        Session = _session_factory()
        with Session() as session:
            _, version_a = _new_project_with_version(session)
            _, version_b = _new_project_with_version(session)
            repo = MapDocumentRepository(session)
            config = _sample_config()
            contexts = _permissive_contexts()

            first = repo.create(
                project_version_id=version_a,
                name="Primeiro",
                config=config,
                layer_contexts=contexts,
            )
            second = repo.create(
                project_version_id=version_a,
                name="Segundo",
                config=config,
                layer_contexts=contexts,
            )
            repo.create(
                project_version_id=version_b,
                name="Outra versao",
                config=config,
                layer_contexts=contexts,
            )

            result = repo.list_for_version(version_a)

            assert [document.id for document in result] == [second.id, first.id]

    def test_empty_when_version_has_no_documents(self) -> None:
        Session = _session_factory()
        with Session() as session:
            _, version_id = _new_project_with_version(session)

            assert MapDocumentRepository(session).list_for_version(version_id) == []


class TestGetForProject:
    def test_finds_document_scoped_to_its_project(self) -> None:
        Session = _session_factory()
        with Session() as session:
            project_id, version_id = _new_project_with_version(session)
            document = MapDocumentRepository(session).create(
                project_version_id=version_id,
                name="Composicao",
                config=_sample_config(),
                layer_contexts=_permissive_contexts(),
            )

            found = MapDocumentRepository(session).get_for_project(project_id, document.id)

            assert found is not None
            assert found.id == document.id

    def test_none_when_document_belongs_to_a_different_project(self) -> None:
        Session = _session_factory()
        with Session() as session:
            _, version_id = _new_project_with_version(session)
            other_project_id, _ = _new_project_with_version(session)
            document = MapDocumentRepository(session).create(
                project_version_id=version_id,
                name="Composicao",
                config=_sample_config(),
                layer_contexts=_permissive_contexts(),
            )

            found = MapDocumentRepository(session).get_for_project(
                other_project_id, document.id
            )

            assert found is None

    def test_none_when_document_does_not_exist(self) -> None:
        Session = _session_factory()
        with Session() as session:
            project_id, _ = _new_project_with_version(session)

            found = MapDocumentRepository(session).get_for_project(project_id, uuid.uuid4())

            assert found is None


class TestGetVersionForProject:
    def test_resolves_version_owned_by_the_project(self) -> None:
        Session = _session_factory()
        with Session() as session:
            project_id, version_id = _new_project_with_version(session)

            version = ProjectRepository(session).get_version_for_project(
                project_id, version_id
            )

            assert version.id == version_id

    def test_raises_for_version_owned_by_another_project(self) -> None:
        Session = _session_factory()
        with Session() as session:
            _, version_id = _new_project_with_version(session)
            other_project_id, _ = _new_project_with_version(session)

            with pytest.raises(ProjectVersionNotFoundError):
                ProjectRepository(session).get_version_for_project(
                    other_project_id, version_id
                )

    def test_raises_for_nonexistent_version(self) -> None:
        Session = _session_factory()
        with Session() as session:
            project_id, _ = _new_project_with_version(session)

            with pytest.raises(ProjectVersionNotFoundError):
                ProjectRepository(session).get_version_for_project(project_id, uuid.uuid4())


class TestBuildLayerContextsAndCreateEndToEnd:
    """Real layer, real feature, real property - proves
    `build_layer_contexts` + `MapDocumentRepository.create` together
    against genuine PostGIS/JSONB data, not a synthetic LayerContext."""

    def test_valid_document_against_a_real_uploaded_layer(self) -> None:
        with TestClient(create_app()) as client:
            project_id = str(
                client.post("/v1/projects", json={"name": "Contexto real"}).json()["id"]
            )
            layer_id = _upload_territorio_layer_with_quadra_id(client, project_id)

        Session = _session_factory()
        with Session() as session:
            version_id = ProjectRepository(session).current_version_id(uuid.UUID(project_id))
            config = _single_layer_config(layer_id)

            contexts = build_layer_contexts(FeatureRepository(session), version_id, config)

            assert contexts[uuid.UUID(layer_id)].layer_type == "territorio"
            assert "quadra_id" in contexts[uuid.UUID(layer_id)].fields

            document = MapDocumentRepository(session).create(
                project_version_id=version_id,
                name="Documento real",
                config=config,
                layer_contexts=contexts,
            )

            assert document.id is not None

    def test_property_field_absent_from_real_data_is_rejected(self) -> None:
        with TestClient(create_app()) as client:
            project_id = str(
                client.post("/v1/projects", json={"name": "Campo ausente"}).json()["id"]
            )
            layer_id = _upload_territorio_layer_with_quadra_id(client, project_id)

        Session = _session_factory()
        with Session() as session:
            version_id = ProjectRepository(session).current_version_id(uuid.UUID(project_id))
            payload = _fixture_payload()
            payload["layers"] = [payload["layers"][0]]
            payload["layers"][0]["layer_id"] = layer_id
            payload["layers"][0]["interaction"]["feature_panel"]["title_field"] = (
                "campo_que_nao_existe"
            )
            config = MapDocumentConfig.model_validate(payload)
            contexts = build_layer_contexts(FeatureRepository(session), version_id, config)

            with pytest.raises(MapDocumentContextError) as excinfo:
                MapDocumentRepository(session).create(
                    project_version_id=version_id,
                    name="Documento invalido",
                    config=config,
                    layer_contexts=contexts,
                )

            violation_paths = [v["path"] for v in excinfo.value.context["violations"]]
            assert "layers[0].interaction.feature_panel.title_field" in violation_paths


def _upload_lote_layer_for_quadras(client: TestClient, project_id: str) -> str:
    """Two adjacent Lote features sharing quadra_id='Q1' - the minimum
    input `derive_quadras_layer` needs to dissolve one quadra polygon."""
    square_a = [[
        [-52.002, -27.001], [-52.000, -27.001], [-52.000, -26.999],
        [-52.002, -26.999], [-52.002, -27.001],
    ]]
    square_b = [[
        [-52.000, -27.001], [-51.998, -27.001], [-51.998, -26.999],
        [-52.000, -26.999], [-52.000, -27.001],
    ]]
    response = client.post(
        f"/v1/projects/{project_id}/layers",
        data={"layer_type": "territorio"},
        files={
            "file": (
                "territorio.geojson",
                json.dumps(
                    {
                        "type": "FeatureCollection",
                        "features": [
                            {
                                "type": "Feature",
                                "geometry": {"type": "Polygon", "coordinates": square_a},
                                "properties": {"macro": "Lote", "quadra": "Q1"},
                            },
                            {
                                "type": "Feature",
                                "geometry": {"type": "Polygon", "coordinates": square_b},
                                "properties": {"macro": "Lote", "quadra": "Q1"},
                            },
                        ],
                    }
                ).encode(),
                "application/geo+json",
            )
        },
    )
    assert response.status_code == 201, response.text
    layer_id = str(response.json()["id"])

    mapping_response = client.patch(
        f"/v1/projects/{project_id}/layers/{layer_id}/attributes",
        json={"mappings": {"macroarea": "macro", "quadra_id": "quadra"}},
    )
    assert mapping_response.status_code == 200, mapping_response.text
    return layer_id


def _derive_quadras(client: TestClient, project_id: str) -> str:
    response = client.post(f"/v1/projects/{project_id}/layers/quadras/derive")
    assert response.status_code == 200, response.text
    return str(response.json()["layer_id"])


def _minimal_single_layer_config(layer_id: str) -> MapDocumentConfig:
    """The simplest possible valid document: one layer, source=none, no
    field or indicator reference at all - just enough to prove layer_id
    membership on its own (used by the quadras re-derivation trap
    scenario, 4.5). Reuses the fixture's second layer, already
    source=none/mode=single with the feature_panel disabled."""
    payload = _fixture_payload()
    layer = payload["layers"][1]
    layer["layer_id"] = layer_id
    payload["layers"] = [layer]
    return MapDocumentConfig.model_validate(payload)


class TestDelete:
    def test_deletes_the_row(self) -> None:
        Session = _session_factory()
        with Session() as session:
            _, version_id = _new_project_with_version(session)
            repo = MapDocumentRepository(session)
            document = repo.create(
                project_version_id=version_id,
                name="Para apagar",
                config=_sample_config(),
                layer_contexts=_permissive_contexts(),
            )
            document_id = document.id

            repo.delete(document)

            assert repo.list_for_version(version_id) == []

        with Session() as session:
            assert session.get(MapDocument, document_id) is None

    def test_delete_does_not_affect_other_documents_of_the_same_version(self) -> None:
        Session = _session_factory()
        with Session() as session:
            _, version_id = _new_project_with_version(session)
            repo = MapDocumentRepository(session)
            keep = repo.create(
                project_version_id=version_id,
                name="Mantido",
                config=_sample_config(),
                layer_contexts=_permissive_contexts(),
            )
            remove = repo.create(
                project_version_id=version_id,
                name="Removido",
                config=_sample_config(),
                layer_contexts=_permissive_contexts(),
            )

            repo.delete(remove)

            remaining = repo.list_for_version(version_id)
            assert [document.id for document in remaining] == [keep.id]


class TestGetWithIntegrityWarnings:
    def test_healthy_document_has_no_warnings(self) -> None:
        with TestClient(create_app()) as client:
            project_id = str(
                client.post("/v1/projects", json={"name": "Diagnostico saudavel"}).json()["id"]
            )
            layer_id = _upload_territorio_layer_with_quadra_id(client, project_id)

        Session = _session_factory()
        with Session() as session:
            version_id = ProjectRepository(session).current_version_id(uuid.UUID(project_id))
            config = _single_layer_config(layer_id)
            contexts = build_layer_contexts(FeatureRepository(session), version_id, config)
            document = MapDocumentRepository(session).create(
                project_version_id=version_id,
                name="Documento saudavel",
                config=config,
                layer_contexts=contexts,
            )

            result = MapDocumentRepository(session).get_with_integrity_warnings(
                uuid.UUID(project_id), document.id, FeatureRepository(session)
            )

            assert result is not None
            found_document, warnings = result
            assert found_document.id == document.id
            assert warnings == []

    def test_returns_none_for_a_document_that_does_not_exist(self) -> None:
        Session = _session_factory()
        with Session() as session:
            project_id, _ = _new_project_with_version(session)

            result = MapDocumentRepository(session).get_with_integrity_warnings(
                project_id, uuid.uuid4(), FeatureRepository(session)
            )

            assert result is None

    def test_quadras_re_derivation_orphans_the_reference_without_breaking_the_read(
        self,
    ) -> None:
        """The concrete trap ADR 014 Decisao 8 decided NOT to fix at the
        source: `POST /layers/quadras/derive` deletes and recreates the
        QUADRAS layer with a brand-new id every call (ADR 009). A document
        saved against the first derivation is orphaned by the second -
        this proves the read-time diagnostic catches it generically,
        without any quadras-specific code."""
        with TestClient(create_app()) as client:
            project_id = str(
                client.post(
                    "/v1/projects", json={"name": "Armadilha de quadras"}
                ).json()["id"]
            )
            _upload_lote_layer_for_quadras(client, project_id)
            first_quadras_layer_id = _derive_quadras(client, project_id)

        Session = _session_factory()
        with Session() as session:
            version_id = ProjectRepository(session).current_version_id(uuid.UUID(project_id))
            config = _minimal_single_layer_config(first_quadras_layer_id)
            contexts = build_layer_contexts(FeatureRepository(session), version_id, config)
            assert uuid.UUID(first_quadras_layer_id) in contexts  # resolves before re-derive

            document = MapDocumentRepository(session).create(
                project_version_id=version_id,
                name="Referencia a quadra",
                config=config,
                layer_contexts=contexts,
            )
            document_id = document.id

        with TestClient(create_app()) as client:
            second_quadras_layer_id = _derive_quadras(client, project_id)
        assert second_quadras_layer_id != first_quadras_layer_id

        with Session() as session:
            result = MapDocumentRepository(session).get_with_integrity_warnings(
                uuid.UUID(project_id), document_id, FeatureRepository(session)
            )

            assert result is not None
            found_document, warnings = result
            # GET never fails and never rewrites the stale reference.
            assert found_document.id == document_id
            assert found_document.config["layers"][0]["layer_id"] == first_quadras_layer_id
            assert len(warnings) == 1
            assert warnings[0].layer_id == uuid.UUID(first_quadras_layer_id)
            assert warnings[0].code == "layer_not_in_version"
