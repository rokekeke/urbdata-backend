"""HTTP-layer tests for the export lifecycle (item 5.7 partial, ADR 014
Decisao 6 + checkpoint 5.1). Business logic (snapshot assembly, repository
transitions) is already covered in `test_export_snapshot.py` and
`test_export_repository.py` - this file proves the HTTP wiring: the
two-call lifecycle, status codes, the unified error envelope.
"""

import json
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.main import create_app

FIXTURE = Path(__file__).parent.parent / "fixtures" / "map_documents" / "v1_example.json"
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

_EXPORT_PAYLOAD: dict[str, Any] = {
    "legend": True,
    "image": {
        "ratio_id": "screen",
        "resolution_id": "2x",
        "width_px": 1600,
        "height_px": 900,
    },
    "renderer": {"maplibre_version": "4.7.1", "frontend_version": "0.1.0"},
}


def _fixture_payload() -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return payload


def _single_layer_payload(layer_id: str) -> dict[str, Any]:
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


def _create_document(client: TestClient, project_id: str, version_id: str) -> str:
    layer_id = _upload_territorio_layer_with_quadra_id(client, project_id)
    response = client.post(
        f"/v1/projects/{project_id}/versions/{version_id}/documents",
        json={"name": "Composicao para export", "config": _single_layer_payload(layer_id)},
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


def _create_export(client: TestClient, project_id: str, document_id: str) -> dict[str, Any]:
    response = client.post(
        f"/v1/projects/{project_id}/documents/{document_id}/exports", json=_EXPORT_PAYLOAD
    )
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


def test_create_deliver_and_get_round_trip() -> None:
    with TestClient(create_app()) as client:
        project_id = _create_project(client, "Exports - round trip")
        version_id = _current_version_id(client, project_id)
        document_id = _create_document(client, project_id, version_id)

        created = _create_export(client, project_id, document_id)
        export_id = created["id"]
        assert created["status"] == "pending"
        assert created["file_path"] is None
        assert created["format"] == "png"
        assert created["config"]["document_id"] == document_id
        assert created["config"]["legend"] is True
        assert created["config"]["image"]["scale"] == 2
        assert "checksum" in created["config"]

        delivered = client.post(
            f"/v1/projects/{project_id}/exports/{export_id}/file",
            files={"file": ("map.png", _PNG_MAGIC + b"fake-png-bytes", "image/png")},
        )
        assert delivered.status_code == 200, delivered.text
        delivered_body = delivered.json()
        assert delivered_body["status"] == "completed"
        assert delivered_body["file_path"] is not None
        assert delivered_body["completed_at"] is not None

        fetched = client.get(f"/v1/projects/{project_id}/exports/{export_id}")
        assert fetched.status_code == 200, fetched.text
        assert fetched.json()["status"] == "completed"
        assert fetched.json()["file_path"] == delivered_body["file_path"]


def test_invalid_png_marks_the_export_failed() -> None:
    with TestClient(create_app()) as client:
        project_id = _create_project(client, "Exports - PNG invalido")
        version_id = _current_version_id(client, project_id)
        document_id = _create_document(client, project_id, version_id)
        export_id = _create_export(client, project_id, document_id)["id"]

        response = client.post(
            f"/v1/projects/{project_id}/exports/{export_id}/file",
            files={"file": ("map.png", b"not-a-real-png", "image/png")},
        )
        assert response.status_code == 422, response.text
        detail = response.json()["detail"]
        assert detail["error"] == "invalid_png"

        fetched = client.get(f"/v1/projects/{project_id}/exports/{export_id}")
        assert fetched.status_code == 200, fetched.text
        fetched_body = fetched.json()
        assert fetched_body["status"] == "failed"
        assert fetched_body["error"]["error"] == "invalid_png"


def test_create_404_when_document_not_found() -> None:
    with TestClient(create_app()) as client:
        project_id = _create_project(client, "Exports - documento inexistente")

        response = client.post(
            f"/v1/projects/{project_id}/documents/00000000-0000-0000-0000-000000000000/exports",
            json=_EXPORT_PAYLOAD,
        )
        assert response.status_code == 404, response.text
        assert response.json()["detail"]["error"] == "map_document_not_found"


def test_create_404_when_analysis_run_not_found() -> None:
    with TestClient(create_app()) as client:
        project_id = _create_project(client, "Exports - run inexistente")
        version_id = _current_version_id(client, project_id)
        document_id = _create_document(client, project_id, version_id)

        payload = {
            **_EXPORT_PAYLOAD,
            "analysis_run_id": "00000000-0000-0000-0000-000000000000",
        }
        response = client.post(
            f"/v1/projects/{project_id}/documents/{document_id}/exports", json=payload
        )
        assert response.status_code == 404, response.text
        assert response.json()["detail"]["error"] == "analysis_run_not_found"


def test_404_when_project_does_not_own_the_export() -> None:
    with TestClient(create_app()) as client:
        project_id = _create_project(client, "Exports - dono")
        version_id = _current_version_id(client, project_id)
        document_id = _create_document(client, project_id, version_id)
        export_id = _create_export(client, project_id, document_id)["id"]
        other_project_id = _create_project(client, "Exports - outro dono")

        get_wrong_owner = client.get(f"/v1/projects/{other_project_id}/exports/{export_id}")
        assert get_wrong_owner.status_code == 404
        assert get_wrong_owner.json()["detail"]["error"] == "export_not_found"

        deliver_wrong_owner = client.post(
            f"/v1/projects/{other_project_id}/exports/{export_id}/file",
            files={"file": ("map.png", _PNG_MAGIC + b"x", "image/png")},
        )
        assert deliver_wrong_owner.status_code == 404
        assert deliver_wrong_owner.json()["detail"]["error"] == "export_not_found"
