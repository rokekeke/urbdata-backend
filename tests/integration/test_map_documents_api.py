"""HTTP-layer tests for MapDocument CRUD (item 4.7, ADR 014 Decisao 8).

The business logic (contextual validation, optimistic concurrency,
integrity-warning diagnostics) is already exhaustively covered at the
repository level in `test_map_document_repository.py` - this file proves
only that the HTTP wiring is correct: status codes, the unified error
envelope, response shapes matching what the repository returns. Reuses
the canonical fixture `tests/fixtures/map_documents/v1_example.json` and
the same real-upload-through-the-API pattern (no hand-rolled PostGIS
geometry).
"""

import json
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.main import create_app

FIXTURE = Path(__file__).parent.parent / "fixtures" / "map_documents" / "v1_example.json"


def _fixture_payload() -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return payload


def _single_layer_payload(layer_id: str) -> dict[str, Any]:
    """One layer exercising both a property field (quadra_id) and a
    per-feature indicator (lots.frontage_length) - same slice of the
    fixture `_single_layer_config` uses at the repository level."""
    payload = _fixture_payload()
    payload["layers"] = [payload["layers"][0]]
    payload["layers"][0]["layer_id"] = layer_id
    return payload


def _create_project(client: TestClient, name: str) -> str:
    response = client.post("/v1/projects", json={"name": name})
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


def _current_version_id(client: TestClient, project_id: str) -> str:
    response = client.get(f"/v1/projects/{project_id}/versions")
    assert response.status_code == 200, response.text
    (current,) = [row for row in response.json() if row["is_current"]]
    return str(current["id"])


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


def _create_document(
    client: TestClient, project_id: str, version_id: str, name: str, config: dict[str, Any]
) -> dict[str, Any]:
    response = client.post(
        f"/v1/projects/{project_id}/versions/{version_id}/documents",
        json={"name": name, "config": config},
    )
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


def test_create_list_and_get_round_trip() -> None:
    with TestClient(create_app()) as client:
        project_id = _create_project(client, "Documentos - CRUD basico")
        version_id = _current_version_id(client, project_id)

        empty_list = client.get(f"/v1/projects/{project_id}/versions/{version_id}/documents")
        assert empty_list.status_code == 200, empty_list.text
        assert empty_list.json() == []

        layer_id = _upload_territorio_layer_with_quadra_id(client, project_id)
        config = _single_layer_payload(layer_id)
        created = _create_document(client, project_id, version_id, "Composicao 1", config)

        assert created["name"] == "Composicao 1"
        assert created["revision"] == 1
        assert created["schema_version"] == "1"
        assert created["config"]["layers"][0]["layer_id"] == layer_id
        document_id = created["id"]

        listed = client.get(f"/v1/projects/{project_id}/versions/{version_id}/documents")
        assert listed.status_code == 200, listed.text
        assert [row["id"] for row in listed.json()] == [document_id]

        item = client.get(f"/v1/projects/{project_id}/documents/{document_id}")
        assert item.status_code == 200, item.text
        item_body = item.json()
        assert item_body["id"] == document_id
        assert item_body["integrity_warnings"] == []


def test_put_updates_and_increments_revision() -> None:
    with TestClient(create_app()) as client:
        project_id = _create_project(client, "Documentos - update")
        version_id = _current_version_id(client, project_id)
        layer_id = _upload_territorio_layer_with_quadra_id(client, project_id)
        config = _single_layer_payload(layer_id)
        created = _create_document(client, project_id, version_id, "Original", config)

        update_response = client.put(
            f"/v1/projects/{project_id}/documents/{created['id']}",
            json={"name": "Renomeado", "config": config, "expected_revision": 1},
        )
        assert update_response.status_code == 200, update_response.text
        updated = update_response.json()
        assert updated["name"] == "Renomeado"
        assert updated["revision"] == 2


def test_put_with_stale_revision_returns_409_with_current_document_in_context() -> None:
    """ADR 014 Decisao 4 says the conflict response carries "o documento
    atual no corpo" - resolved this session as `context.current_document`
    inside the project's single error envelope, so the OpenAPI contract
    guard (every declared 4xx uses ErrorEnvelopeOut) needs no exception
    for this route."""
    with TestClient(create_app()) as client:
        project_id = _create_project(client, "Documentos - conflito")
        version_id = _current_version_id(client, project_id)
        layer_id = _upload_territorio_layer_with_quadra_id(client, project_id)
        config = _single_layer_payload(layer_id)
        created = _create_document(client, project_id, version_id, "Original", config)
        document_id = created["id"]

        first = client.put(
            f"/v1/projects/{project_id}/documents/{document_id}",
            json={"name": "Vencedor", "config": config, "expected_revision": 1},
        )
        assert first.status_code == 200, first.text

        conflict = client.put(
            f"/v1/projects/{project_id}/documents/{document_id}",
            json={"name": "Perdedor", "config": config, "expected_revision": 1},
        )
        assert conflict.status_code == 409, conflict.text
        detail = conflict.json()["detail"]
        assert set(detail) == {"error", "message", "context"}
        assert detail["error"] == "map_document_revision_conflict"
        assert detail["context"]["expected_revision"] == 1
        assert detail["context"]["current_revision"] == 2
        current_document = detail["context"]["current_document"]
        assert current_document["id"] == document_id
        assert current_document["revision"] == 2
        assert current_document["name"] == "Vencedor"


def test_delete_then_get_returns_404() -> None:
    with TestClient(create_app()) as client:
        project_id = _create_project(client, "Documentos - delete")
        version_id = _current_version_id(client, project_id)
        layer_id = _upload_territorio_layer_with_quadra_id(client, project_id)
        config = _single_layer_payload(layer_id)
        document_id = _create_document(client, project_id, version_id, "Para apagar", config)["id"]

        delete_response = client.delete(f"/v1/projects/{project_id}/documents/{document_id}")
        assert delete_response.status_code == 204
        assert delete_response.content == b""

        get_after = client.get(f"/v1/projects/{project_id}/documents/{document_id}")
        assert get_after.status_code == 404
        assert get_after.json()["detail"]["error"] == "map_document_not_found"


def test_404_when_project_does_not_own_the_resource() -> None:
    with TestClient(create_app()) as client:
        project_id = _create_project(client, "Documentos - dono")
        version_id = _current_version_id(client, project_id)
        other_project_id = _create_project(client, "Outro dono")

        layer_id = _upload_territorio_layer_with_quadra_id(client, project_id)
        config = _single_layer_payload(layer_id)
        document_id = _create_document(client, project_id, version_id, "Documento", config)["id"]

        # version_id belongs to `project_id`, not `other_project_id`.
        create_wrong_owner = client.post(
            f"/v1/projects/{other_project_id}/versions/{version_id}/documents",
            json={"name": "Nao deveria criar", "config": config},
        )
        assert create_wrong_owner.status_code == 404
        assert create_wrong_owner.json()["detail"]["error"] == "project_version_not_found"

        get_wrong_owner = client.get(f"/v1/projects/{other_project_id}/documents/{document_id}")
        assert get_wrong_owner.status_code == 404
        assert get_wrong_owner.json()["detail"]["error"] == "map_document_not_found"

        put_wrong_owner = client.put(
            f"/v1/projects/{other_project_id}/documents/{document_id}",
            json={"name": "Nao deveria atualizar", "config": config, "expected_revision": 1},
        )
        assert put_wrong_owner.status_code == 404
        assert put_wrong_owner.json()["detail"]["error"] == "map_document_not_found"

        delete_wrong_owner = client.delete(
            f"/v1/projects/{other_project_id}/documents/{document_id}"
        )
        assert delete_wrong_owner.status_code == 404
        assert delete_wrong_owner.json()["detail"]["error"] == "map_document_not_found"


def test_create_with_contextually_invalid_config_returns_422() -> None:
    with TestClient(create_app()) as client:
        project_id = _create_project(client, "Documentos - 422")
        version_id = _current_version_id(client, project_id)
        # No layer uploaded at all - the fixture's layer_ids can't resolve
        # against this version, so both layers violate layer_not_in_version.
        config = _fixture_payload()

        response = client.post(
            f"/v1/projects/{project_id}/versions/{version_id}/documents",
            json={"name": "Invalido", "config": config},
        )
        assert response.status_code == 422, response.text
        detail = response.json()["detail"]
        assert detail["error"] == "map_document_context_invalid"
        assert len(detail["context"]["violations"]) == 2


def test_get_surfaces_integrity_warning_after_quadras_re_derivation() -> None:
    """The quadras orphaning trap (ADR 009, ADR 014 Decisao 8) is already
    proven end-to-end at the repository level
    (test_map_document_repository.TestGetWithIntegrityWarnings.
    test_quadras_re_derivation_orphans_the_reference_without_breaking_the_read)
    - this only confirms the same diagnostic reaches the client through the
    real GET route, not just the repository method."""
    with TestClient(create_app()) as client:
        project_id = _create_project(client, "Documentos - armadilha quadras")
        square_a = [[
            [-52.002, -27.001], [-52.000, -27.001], [-52.000, -26.999],
            [-52.002, -26.999], [-52.002, -27.001],
        ]]
        square_b = [[
            [-52.000, -27.001], [-51.998, -27.001], [-51.998, -26.999],
            [-52.000, -26.999], [-52.000, -27.001],
        ]]
        upload = client.post(
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
        assert upload.status_code == 201, upload.text
        layer_id = str(upload.json()["id"])
        mapping = client.patch(
            f"/v1/projects/{project_id}/layers/{layer_id}/attributes",
            json={"mappings": {"macroarea": "macro", "quadra_id": "quadra"}},
        )
        assert mapping.status_code == 200, mapping.text

        version_id = _current_version_id(client, project_id)
        first_derive = client.post(f"/v1/projects/{project_id}/layers/quadras/derive")
        assert first_derive.status_code == 200, first_derive.text
        first_quadras_layer_id = str(first_derive.json()["layer_id"])

        # The fixture's second layer is source=none/mode=single - just
        # enough to prove layer_id membership on its own.
        minimal_config = _fixture_payload()
        minimal_config["layers"] = [minimal_config["layers"][1]]
        minimal_config["layers"][0]["layer_id"] = first_quadras_layer_id
        document_id = _create_document(
            client, project_id, version_id, "Referencia a quadra", minimal_config
        )["id"]

        second_derive = client.post(f"/v1/projects/{project_id}/layers/quadras/derive")
        assert second_derive.status_code == 200, second_derive.text
        assert str(second_derive.json()["layer_id"]) != first_quadras_layer_id

        item = client.get(f"/v1/projects/{project_id}/documents/{document_id}")
        assert item.status_code == 200, item.text
        item_body = item.json()
        # GET never fails and never rewrites the stale reference.
        assert item_body["config"]["layers"][0]["layer_id"] == first_quadras_layer_id
        warnings = item_body["integrity_warnings"]
        assert len(warnings) == 1
        assert warnings[0]["layer_id"] == first_quadras_layer_id
        assert warnings[0]["code"] == "layer_not_in_version"
