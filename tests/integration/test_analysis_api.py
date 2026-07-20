import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

# tests/integration/conftest.py guarantees URBDATA_TEST_DATABASE_URL is set
# and mirrored into URBDATA_DATABASE_URL before this module is even
# imported - aborting the whole session otherwise (Obsidian nota 37).


def _feature_collection(features: list[dict[str, Any]]) -> bytes:
    return json.dumps({"type": "FeatureCollection", "features": features}).encode()


def _feature(geometry_type: str, coordinates: Any, **properties: object) -> dict[str, Any]:
    return {
        "type": "Feature",
        "geometry": {"type": geometry_type, "coordinates": coordinates},
        "properties": properties,
    }


def _upload(
    client: TestClient,
    project_id: str,
    *,
    layer_type: str,
    features: list[dict[str, Any]],
) -> str:
    response = client.post(
        f"/v1/projects/{project_id}/layers",
        data={"layer_type": layer_type},
        files={
            "file": (
                f"{layer_type}.geojson",
                _feature_collection(features),
                "application/geo+json",
            )
        },
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


def _map_attributes(
    client: TestClient,
    project_id: str,
    layer_id: str,
    mappings: dict[str, str],
) -> None:
    response = client.patch(
        f"/v1/projects/{project_id}/layers/{layer_id}/attributes",
        json={"mappings": mappings},
    )
    assert response.status_code == 200, response.text


def _results_by_code(payload: dict[str, Any] | list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    rows = payload["results"] if isinstance(payload, dict) else payload
    return {row["indicator_code"]: row for row in rows}


def test_density_and_road_network_round_trip_through_the_real_api() -> None:
    with TestClient(create_app()) as client:
        project_response = client.post(
            "/v1/projects",
            json={"name": "Validacao automatizada", "municipality": "Florianopolis"},
        )
        assert project_response.status_code == 201, project_response.text
        project_id = str(project_response.json()["id"])

        _upload(
            client,
            project_id,
            layer_type="perimetro",
            features=[
                _feature(
                    "Polygon",
                    [[
                        [-52.001, -27.001],
                        [-51.999, -27.001],
                        [-51.999, -26.999],
                        [-52.001, -26.999],
                        [-52.001, -27.001],
                    ]],
                )
            ],
        )
        territorio_id = _upload(
            client,
            project_id,
            layer_type="territorio",
            features=[
                _feature(
                    "Polygon",
                    [[
                        [-52.0008, -27.0008],
                        [-52.0001, -27.0008],
                        [-52.0001, -27.0001],
                        [-52.0008, -27.0001],
                        [-52.0008, -27.0008],
                    ]],
                    macro="Lote",
                    ca="2.0",
                    parcelavel="sim",
                ),
                _feature(
                    "Polygon",
                    [[
                        [-51.9999, -27.0008],
                        [-51.9992, -27.0008],
                        [-51.9992, -27.0001],
                        [-51.9999, -27.0001],
                        [-51.9999, -27.0008],
                    ]],
                    macro="Lote",
                    ca="0",
                    parcelavel="sim",
                ),
            ],
        )
        _map_attributes(
            client,
            project_id,
            territorio_id,
            {"macroarea": "macro", "ca_max": "ca", "parcelavel": "parcelavel"},
        )

        roads_id = _upload(
            client,
            project_id,
            layer_type="sistema_viario",
            features=[
                _feature(
                    "LineString",
                    [[-52.0015, -27.0002], [-51.9985, -27.0002]],
                    situacao="existente",
                ),
                _feature(
                    "LineString",
                    [[-52.0015, -26.9996], [-51.9985, -26.9996]],
                    situacao="existente",
                ),
                _feature(
                    "LineString",
                    [[-52.0, -27.0008], [-52.0, -26.9992]],
                    situacao="proposta",
                ),
            ],
        )
        _map_attributes(
            client,
            project_id,
            roads_id,
            {"road_status": "situacao"},
        )
        _upload(
            client,
            project_id,
            layer_type="desconexoes_viarias",
            features=[_feature("Point", [-52.0, -26.9996])],
        )

        density_response = client.post(
            f"/v1/projects/{project_id}/analyze", json={"themes": ["density"]}
        )
        assert density_response.status_code == 201, density_response.text
        density = _results_by_code(density_response.json())
        assert density["density.max_computable_area"]["value"] > 0
        assert density["density.lot_count_with_ca"]["value"] == 2
        assert density["density.ca_coverage"]["value"] == pytest.approx(1.0)

        persisted_density = client.get(f"/v1/projects/{project_id}/results")
        assert persisted_density.status_code == 200, persisted_density.text
        persisted_density_by_code = _results_by_code(persisted_density.json())
        assert persisted_density_by_code["density.max_computable_area"]["value"] == pytest.approx(
            density["density.max_computable_area"]["value"]
        )

        territorial_response = client.post(
            f"/v1/projects/{project_id}/analyze", json={"themes": ["territorial"]}
        )
        assert territorial_response.status_code == 201, territorial_response.text
        territorial = _results_by_code(territorial_response.json())
        assert territorial["territorial.area_by_category"]["value"]["lote"] > 0

        persisted_territorial = client.get(f"/v1/projects/{project_id}/results")
        assert persisted_territorial.status_code == 200, persisted_territorial.text
        persisted_territorial_by_code = _results_by_code(persisted_territorial.json())
        persisted_area_by_category = persisted_territorial_by_code[
            "territorial.area_by_category"
        ]["value"]
        assert persisted_area_by_category == pytest.approx(
            territorial["territorial.area_by_category"]["value"]
        )

        road_response = client.post(
            f"/v1/projects/{project_id}/analyze", json={"themes": ["road_network"]}
        )
        assert road_response.status_code == 201, road_response.text
        roads = _results_by_code(road_response.json())
        assert roads["road_network.total_length"]["value"] > 0
        assert roads["road_network.intersection_count"]["value"] == 1
        assert roads["road_network.proposed_connection_count"]["value"] == 1
        assert "desconexoes_viarias" in roads["road_network.total_length"]["source_layers"]

        persisted_roads = client.get(f"/v1/projects/{project_id}/results")
        assert persisted_roads.status_code == 200, persisted_roads.text
        persisted_roads_by_code = _results_by_code(persisted_roads.json())
        assert persisted_roads_by_code["road_network.total_length"]["value"] == pytest.approx(
            roads["road_network.total_length"]["value"]
        )


def test_versions_runs_and_error_shape_round_trip() -> None:
    """Fase 0 endpoints (nota Obsidian 28/29): explicit versions, run
    history including a failed run's structured error, and the unified
    `{error, message, context}` detail shape."""
    with TestClient(create_app()) as client:
        project_id = str(
            client.post("/v1/projects", json={"name": "Fase 0"}).json()["id"]
        )

        versions = client.get(f"/v1/projects/{project_id}/versions")
        assert versions.status_code == 200, versions.text
        version_rows = versions.json()
        assert len(version_rows) == 1
        assert version_rows[0]["is_current"] is True
        assert version_rows[0]["number"] == 1
        assert version_rows[0]["status"] == "active"

        # No perimeter uploaded: the run must fail, be listed, and carry
        # the context saying WHICH layer is missing.
        failed = client.post(f"/v1/projects/{project_id}/analyze", json={"themes": ["density"]})
        assert failed.status_code == 422
        detail = failed.json()["detail"]
        assert detail["error"] == "required_layer_missing"
        assert detail["context"]["layer_type"] == "perimetro"

        runs = client.get(f"/v1/projects/{project_id}/runs")
        assert runs.status_code == 200, runs.text
        run_rows = runs.json()
        assert len(run_rows) == 1
        assert run_rows[0]["status"] == "failed"
        assert run_rows[0]["error"]["code"] == "required_layer_missing"
        assert run_rows[0]["error"]["context"]["layer_type"] == "perimetro"

        single = client.get(f"/v1/projects/{project_id}/runs/{run_rows[0]['id']}")
        assert single.status_code == 200
        assert single.json()["id"] == run_rows[0]["id"]

        other_project_id = str(
            client.post("/v1/projects", json={"name": "Outro"}).json()["id"]
        )
        cross = client.get(f"/v1/projects/{other_project_id}/runs/{run_rows[0]['id']}")
        assert cross.status_code == 404
        cross_detail = cross.json()["detail"]
        assert cross_detail["error"] == "analysis_run_not_found"
        assert set(cross_detail) == {"error", "message", "context"}

        missing = client.get("/v1/projects/00000000-0000-0000-0000-000000000000")
        assert missing.status_code == 404
        missing_detail = missing.json()["detail"]
        assert set(missing_detail) == {"error", "message", "context"}
        assert missing_detail["error"] == "project_not_found"


def test_representation_options_aggregate_in_the_database() -> None:
    """DOC-BE-004 (ADR 014): the attributes endpoint returns per-field
    aggregates, recommendations and compatible indicators - computed by
    SQL over the real PostGIS instance."""
    with TestClient(create_app()) as client:
        project_id = str(client.post("/v1/projects", json={"name": "Rep opts"}).json()["id"])
        square = [[
            [-52.001, -27.001], [-51.999, -27.001], [-51.999, -26.999],
            [-52.001, -26.999], [-52.001, -27.001],
        ]]
        layer_id = _upload(
            client,
            project_id,
            layer_type="territorio",
            features=[
                _feature("Polygon", square, macro="Lote", uso="Residencial", area="100.5"),
                _feature("Polygon", square, macro="Lote", uso="Comercial", area="220"),
                _feature("Polygon", square, macro="AVL", uso="", area="abc"),
            ],
        )
        _map_attributes(client, project_id, layer_id, {"macroarea": "macro"})

        response = client.get(f"/v1/projects/{project_id}/layers/{layer_id}/attributes")
        assert response.status_code == 200, response.text
        body = response.json()

        assert body["feature_count"] == 3
        assert body["compatible_indicators"] == ["lots.frontage_length"]
        fields = {entry["field"]: entry for entry in body["fields"]}

        macro_source = fields["macro"]
        assert macro_source["origin"] == "source"
        assert macro_source["detected_type"] == "text"
        assert macro_source["recommended_mode"] == "categorical"
        assert macro_source["distinct_values"] == ["AVL", "Lote"]

        area = fields["area"]
        # "abc" mixed in with numbers -> honestly unsuitable, not coerced.
        assert area["detected_type"] == "mixed"
        assert area["recommended_mode"] is None
        assert area["unsuitable_reason"] == "mixed_types"

        uso = fields["uso"]
        assert uso["empty_count"] == 1
        assert uso["cardinality"] == 2

        macro_mapped = fields["macroarea"]
        assert macro_mapped["origin"] == "mapped"
        assert macro_mapped["recommended_mode"] == "categorical"
        assert sorted(macro_mapped["distinct_values"]) == ["avl", "lote"]
