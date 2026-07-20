"""Layer routes: suggested_mapping (attribute_suggestions.py) and DELETE
(Frente 3, nota 52).

Uses the real Revit/Masterplan fixture (tests/Geosjon_basico_teste.json,
already exercised by the mojibake fix) to prove the suggestion survives the
same upload pipeline a real delivery goes through - mojibake fix first,
then field-name matching against the known aliases.
"""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app

FIXTURE = Path(__file__).parent.parent / "Geosjon_basico_teste.json"


def test_suggests_the_known_aliases_from_a_real_export_file() -> None:
    with TestClient(create_app()) as client:
        project_id = str(
            client.post("/v1/projects", json={"name": "Sugestao de atributos"}).json()["id"]
        )

        upload = client.post(
            f"/v1/projects/{project_id}/layers",
            data={"layer_type": "territorio"},
            files={
                "file": (
                    "PROJETO.geojson",
                    FIXTURE.read_bytes(),
                    "application/geo+json",
                )
            },
        )
        assert upload.status_code == 201, upload.text
        layer_id = str(upload.json()["id"])

        response = client.get(f"/v1/projects/{project_id}/layers/{layer_id}/attributes")
        assert response.status_code == 200, response.text
        suggested = response.json()["suggested_mapping"]

        assert suggested["macroarea"] == "Comments"
        assert suggested["quadra_id"] == "QUADRA"
        assert suggested["parcelavel"] == "P_Área de Projeto"
        assert suggested["reference_area_m2"] == "Area"


def _upload_territorio_with_quadra(client: TestClient, project_id: str) -> str:
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
                json.dumps({
                    "type": "FeatureCollection",
                    "features": [
                        {
                            "type": "Feature",
                            "geometry": {"type": "Polygon", "coordinates": coordinates},
                            "properties": {"macro": "Lote", "quadra": "Q1"},
                        }
                        for coordinates in (square_a, square_b)
                    ],
                }).encode(),
                "application/geo+json",
            )
        },
    )
    assert response.status_code == 201, response.text
    layer_id = str(response.json()["id"])
    mapping = client.patch(
        f"/v1/projects/{project_id}/layers/{layer_id}/attributes",
        json={"mappings": {"macroarea": "macro", "quadra_id": "quadra"}},
    )
    assert mapping.status_code == 200, mapping.text
    return layer_id


class TestDeleteLayer:
    def test_deleting_quadras_unlinks_lots_without_removing_them(self) -> None:
        """The hard case: the derived QUADRAS layer's features are the
        TARGET of parent_quadra_feature_id links from the territorio lots.
        Deleting quadras must unlink the lots, never cascade into them."""
        with TestClient(create_app()) as client:
            project_id = str(
                client.post("/v1/projects", json={"name": "Delete quadras"}).json()["id"]
            )
            territorio_id = _upload_territorio_with_quadra(client, project_id)
            derive = client.post(f"/v1/projects/{project_id}/layers/quadras/derive")
            assert derive.status_code == 200, derive.text
            quadras_id = str(derive.json()["layer_id"])

            response = client.delete(f"/v1/projects/{project_id}/layers/{quadras_id}")
            assert response.status_code == 204

            remaining = client.get(f"/v1/projects/{project_id}/layers").json()
            assert [layer["id"] for layer in remaining] == [territorio_id]
            geojson = client.get(
                f"/v1/projects/{project_id}/layers/{territorio_id}/geojson"
            ).json()
            assert len(geojson["features"]) == 2  # lots survived the unlink

    def test_delete_then_reads_return_404_and_list_shrinks(self) -> None:
        with TestClient(create_app()) as client:
            project_id = str(
                client.post("/v1/projects", json={"name": "Delete camada"}).json()["id"]
            )
            layer_id = _upload_territorio_with_quadra(client, project_id)

            assert client.delete(
                f"/v1/projects/{project_id}/layers/{layer_id}"
            ).status_code == 204
            assert client.get(f"/v1/projects/{project_id}/layers").json() == []
            attributes = client.get(
                f"/v1/projects/{project_id}/layers/{layer_id}/attributes"
            )
            assert attributes.status_code == 404

    def test_delete_is_project_scoped(self) -> None:
        with TestClient(create_app()) as client:
            project_id = str(
                client.post("/v1/projects", json={"name": "Dono da camada"}).json()["id"]
            )
            other_project_id = str(
                client.post("/v1/projects", json={"name": "Outro dono"}).json()["id"]
            )
            layer_id = _upload_territorio_with_quadra(client, project_id)

            cross = client.delete(f"/v1/projects/{other_project_id}/layers/{layer_id}")
            assert cross.status_code == 404
            assert cross.json()["detail"]["error"] == "layer_not_found"
            still_there = client.get(f"/v1/projects/{project_id}/layers").json()
            assert [layer["id"] for layer in still_there] == [layer_id]
