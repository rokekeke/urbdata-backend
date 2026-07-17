import json
import os
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

TEST_DATABASE_URL = os.getenv("URBDATA_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="URBDATA_TEST_DATABASE_URL is required for database integration tests",
)


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
