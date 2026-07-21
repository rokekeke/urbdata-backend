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
REAL_SPLIT_GEOMETRY_FIXTURE = Path(__file__).parent.parent / "PROJETO_R01_GEOMETRIA.json"
REAL_SPLIT_ATTRIBUTES_FIXTURE = Path(__file__).parent.parent / "DATA_EXPORT_PROJETO_01.csv"


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


def _minimal_territorio_geojson() -> bytes:
    return json.dumps({
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [[
                [-52.002, -27.001], [-52.000, -27.001], [-52.000, -26.999],
                [-52.002, -26.999], [-52.002, -27.001],
            ]]},
            "properties": {},
        }],
    }).encode()


class TestSplitImportProfileValidation:
    """b6.1 (nota 53/54): request-shape validation for the combined/split
    import profile - runs before any CSV parsing or join logic exists."""

    def test_rejects_attributes_file_with_combined_profile(self) -> None:
        with TestClient(create_app()) as client:
            project_id = str(
                client.post("/v1/projects", json={"name": "Perfil combined"}).json()["id"]
            )
            response = client.post(
                f"/v1/projects/{project_id}/layers",
                data={"layer_type": "territorio", "import_profile": "combined"},
                files={
                    "file": ("t.geojson", _minimal_territorio_geojson(), "application/geo+json"),
                    "attributes_file": ("a.csv", b"Name;Area\nL01;100\n", "text/csv"),
                },
            )
            assert response.status_code == 400, response.text
            assert response.json()["detail"]["error"] == "invalid_import_profile"

    def test_rejects_split_profile_without_attributes_file(self) -> None:
        with TestClient(create_app()) as client:
            project_id = str(
                client.post("/v1/projects", json={"name": "Perfil split sem CSV"}).json()["id"]
            )
            response = client.post(
                f"/v1/projects/{project_id}/layers",
                data={"layer_type": "territorio", "import_profile": "split"},
                files={
                    "file": ("t.geojson", _minimal_territorio_geojson(), "application/geo+json")
                },
            )
            assert response.status_code == 400, response.text
            assert response.json()["detail"]["error"] == "invalid_import_profile"

    def test_rejects_split_profile_without_attributes_join_key(self) -> None:
        with TestClient(create_app()) as client:
            project_id = str(
                client.post("/v1/projects", json={"name": "Perfil split sem chave"}).json()["id"]
            )
            response = client.post(
                f"/v1/projects/{project_id}/layers",
                data={"layer_type": "territorio", "import_profile": "split"},
                files={
                    "file": ("t.geojson", _minimal_territorio_geojson(), "application/geo+json"),
                    "attributes_file": ("a.csv", b"Name;Area\nL01;100\n", "text/csv"),
                },
            )
            assert response.status_code == 400, response.text
            assert response.json()["detail"]["error"] == "invalid_import_profile"

    def test_combined_profile_without_attributes_file_still_works(self) -> None:
        """The default (today's only behavior) must stay unaffected."""
        with TestClient(create_app()) as client:
            project_id = str(
                client.post("/v1/projects", json={"name": "Perfil combined padrao"}).json()["id"]
            )
            response = client.post(
                f"/v1/projects/{project_id}/layers",
                data={"layer_type": "territorio"},
                files={
                    "file": ("t.geojson", _minimal_territorio_geojson(), "application/geo+json")
                },
            )
            assert response.status_code == 201, response.text


def _minimal_territorio_geojson_with_id(feature_id: str) -> bytes:
    return json.dumps({
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "id": feature_id,
            "geometry": {"type": "Polygon", "coordinates": [[
                [-52.002, -27.001], [-52.000, -27.001], [-52.000, -26.999],
                [-52.002, -26.999], [-52.002, -27.001],
            ]]},
            "properties": {},
        }],
    }).encode()


class TestSplitImportJoin:
    """b6.3-b6.5: CSV parsing and join errors surface as their own 400
    error codes; a valid split upload merges CSV attributes into feature
    properties and persists traceability fields on the layer."""

    def test_rejects_malformed_csv_with_its_own_error_code(self) -> None:
        with TestClient(create_app()) as client:
            project_id = str(
                client.post("/v1/projects", json={"name": "CSV malformado"}).json()["id"]
            )
            response = client.post(
                f"/v1/projects/{project_id}/layers",
                data={
                    "layer_type": "territorio",
                    "import_profile": "split",
                    "attributes_join_key": "Name",
                },
                files={
                    "file": (
                        "t.geojson",
                        _minimal_territorio_geojson_with_id("L01"),
                        "application/geo+json",
                    ),
                    "attributes_file": ("a.csv", b"", "text/csv"),
                },
            )
            assert response.status_code == 400, response.text
            assert response.json()["detail"]["error"] == "csv_malformed"

    def test_rejects_join_mismatch_with_its_own_error_code(self) -> None:
        with TestClient(create_app()) as client:
            project_id = str(
                client.post("/v1/projects", json={"name": "Join sem par"}).json()["id"]
            )
            response = client.post(
                f"/v1/projects/{project_id}/layers",
                data={
                    "layer_type": "territorio",
                    "import_profile": "split",
                    "attributes_join_key": "Name",
                },
                files={
                    "file": (
                        "t.geojson",
                        _minimal_territorio_geojson_with_id("L01"),
                        "application/geo+json",
                    ),
                    "attributes_file": ("a.csv", b"Name;Area\nL02;100\n", "text/csv"),
                },
            )
            assert response.status_code == 400, response.text
            assert response.json()["detail"]["error"] == "attribute_join_mismatch"

    def test_valid_split_upload_merges_csv_attributes_into_the_feature(self) -> None:
        with TestClient(create_app()) as client:
            project_id = str(
                client.post("/v1/projects", json={"name": "Split valido"}).json()["id"]
            )
            response = client.post(
                f"/v1/projects/{project_id}/layers",
                data={
                    "layer_type": "territorio",
                    "import_profile": "split",
                    "attributes_join_key": "Name",
                },
                files={
                    "file": (
                        "t.geojson",
                        _minimal_territorio_geojson_with_id("L01"),
                        "application/geo+json",
                    ),
                    "attributes_file": ("a.csv", b"Name;Area\nL01;100\n", "text/csv"),
                },
            )
            assert response.status_code == 201, response.text

            layer = response.json()
            layer_id = str(layer["id"])

            assert layer["import_profile"] == "split"
            assert layer["attributes_filename"] == "a.csv"
            assert layer["attributes_join_key"] == "Name"
            assert layer["geometry_join_key"] is None
            assert layer["join_summary"] == {
                "geometry_count": 1,
                "attribute_count": 1,
                "matched": 1,
                "missing_geometry_keys": [],
                "missing_attribute_keys": [],
                "duplicate_geometry_keys": [],
                "duplicate_attribute_keys": [],
            }

            geojson = client.get(
                f"/v1/projects/{project_id}/layers/{layer_id}/geojson"
            ).json()
            assert len(geojson["features"]) == 1
            assert geojson["features"][0]["properties"] == {"Name": "L01", "Area": "100"}

    def test_combined_upload_leaves_traceability_fields_at_defaults(self) -> None:
        with TestClient(create_app()) as client:
            project_id = str(
                client.post("/v1/projects", json={"name": "Combined padrao"}).json()["id"]
            )
            response = client.post(
                f"/v1/projects/{project_id}/layers",
                data={"layer_type": "territorio"},
                files={
                    "file": ("t.geojson", _minimal_territorio_geojson(), "application/geo+json")
                },
            )
            assert response.status_code == 201, response.text
            layer = response.json()
            assert layer["import_profile"] == "combined"
            assert layer["attributes_filename"] is None
            assert layer["attributes_join_key"] is None
            assert layer["geometry_join_key"] is None
            assert layer["join_summary"] is None


def _two_feature_territorio_geojson(id_a: str, id_b: str) -> bytes:
    square_a = [[
        [-52.002, -27.001], [-52.000, -27.001], [-52.000, -26.999],
        [-52.002, -26.999], [-52.002, -27.001],
    ]]
    square_b = [[
        [-52.000, -27.001], [-51.998, -27.001], [-51.998, -26.999],
        [-52.000, -26.999], [-52.000, -27.001],
    ]]
    return json.dumps({
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "id": feature_id,
                "geometry": {"type": "Polygon", "coordinates": coordinates},
                "properties": {},
            }
            for feature_id, coordinates in ((id_a, square_a), (id_b, square_b))
        ],
    }).encode()


class TestSplitImportBlockingRules:
    """b7.1: one HTTP-level test per blocking rule not already exercised in
    TestSplitImportJoin - empty and duplicate keys on both sides."""

    def test_rejects_empty_key_on_geometry_side(self) -> None:
        with TestClient(create_app()) as client:
            project_id = str(
                client.post("/v1/projects", json={"name": "Chave vazia geometria"}).json()["id"]
            )
            response = client.post(
                f"/v1/projects/{project_id}/layers",
                data={
                    "layer_type": "territorio",
                    "import_profile": "split",
                    "attributes_join_key": "Name",
                    "geometry_join_key": "URBDATA_ID",
                },
                files={
                    "file": (
                        "t.geojson",
                        _minimal_territorio_geojson_with_id("L01"),
                        "application/geo+json",
                    ),
                    "attributes_file": ("a.csv", b"Name;Area\nL01;100\n", "text/csv"),
                },
            )
            assert response.status_code == 400, response.text
            body = response.json()["detail"]
            assert body["error"] == "attribute_join_mismatch"
            assert body["context"]["empty_geometry_feature_indices"] == [0]

    def test_rejects_empty_key_on_attribute_side(self) -> None:
        with TestClient(create_app()) as client:
            project_id = str(
                client.post("/v1/projects", json={"name": "Chave vazia CSV"}).json()["id"]
            )
            response = client.post(
                f"/v1/projects/{project_id}/layers",
                data={
                    "layer_type": "territorio",
                    "import_profile": "split",
                    "attributes_join_key": "Name",
                },
                files={
                    "file": (
                        "t.geojson",
                        _minimal_territorio_geojson_with_id("L01"),
                        "application/geo+json",
                    ),
                    "attributes_file": ("a.csv", b"Name;Area\n;100\n", "text/csv"),
                },
            )
            assert response.status_code == 400, response.text
            body = response.json()["detail"]
            assert body["error"] == "attribute_join_mismatch"
            assert body["context"]["empty_attribute_row_indices"] == [0]

    def test_rejects_duplicate_key_on_geometry_side(self) -> None:
        with TestClient(create_app()) as client:
            project_id = str(
                client.post("/v1/projects", json={"name": "Chave duplicada geometria"}).json()[
                    "id"
                ]
            )
            response = client.post(
                f"/v1/projects/{project_id}/layers",
                data={
                    "layer_type": "territorio",
                    "import_profile": "split",
                    "attributes_join_key": "Name",
                },
                files={
                    "file": (
                        "t.geojson",
                        _two_feature_territorio_geojson("L01", "L01"),
                        "application/geo+json",
                    ),
                    "attributes_file": ("a.csv", b"Name;Area\nL01;100\n", "text/csv"),
                },
            )
            assert response.status_code == 400, response.text
            body = response.json()["detail"]
            assert body["error"] == "attribute_join_mismatch"
            assert body["context"]["duplicate_geometry_keys"] == ["L01"]

    def test_rejects_duplicate_key_on_attribute_side(self) -> None:
        with TestClient(create_app()) as client:
            project_id = str(
                client.post("/v1/projects", json={"name": "Chave duplicada CSV"}).json()["id"]
            )
            response = client.post(
                f"/v1/projects/{project_id}/layers",
                data={
                    "layer_type": "territorio",
                    "import_profile": "split",
                    "attributes_join_key": "Name",
                },
                files={
                    "file": (
                        "t.geojson",
                        _minimal_territorio_geojson_with_id("L01"),
                        "application/geo+json",
                    ),
                    "attributes_file": (
                        "a.csv",
                        b"Name;Area\nL01;100\nL01;200\n",
                        "text/csv",
                    ),
                },
            )
            assert response.status_code == 400, response.text
            body = response.json()["detail"]
            assert body["error"] == "attribute_join_mismatch"
            assert body["context"]["duplicate_attribute_keys"] == ["L01"]

    def test_failed_join_leaves_no_layer_persisted(self) -> None:
        """b7.3: the join is validated entirely before any file is saved or
        any database write happens - a rejected upload leaves the project
        exactly as empty as it started, not a partially created layer."""
        with TestClient(create_app()) as client:
            project_id = str(
                client.post("/v1/projects", json={"name": "Rollback"}).json()["id"]
            )
            response = client.post(
                f"/v1/projects/{project_id}/layers",
                data={
                    "layer_type": "territorio",
                    "import_profile": "split",
                    "attributes_join_key": "Name",
                },
                files={
                    "file": (
                        "t.geojson",
                        _minimal_territorio_geojson_with_id("L01"),
                        "application/geo+json",
                    ),
                    "attributes_file": ("a.csv", b"Name;Area\nL02;100\n", "text/csv"),
                },
            )
            assert response.status_code == 400, response.text
            assert client.get(f"/v1/projects/{project_id}/layers").json() == []


class TestSplitImportNamedGeometryKey:
    """b7.2: a positive split upload using an explicit geometry_join_key
    (not the feature.id default) across more than one matched feature."""

    def test_multi_feature_upload_with_named_geometry_join_key(self) -> None:
        geojson = json.dumps({
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "id": f"internal-{suffix}",
                    "geometry": {"type": "Polygon", "coordinates": coordinates},
                    "properties": {"URBDATA_ID": f"L0{suffix}"},
                }
                for suffix, coordinates in (
                    (1, [[
                        [-52.002, -27.001], [-52.000, -27.001], [-52.000, -26.999],
                        [-52.002, -26.999], [-52.002, -27.001],
                    ]]),
                    (2, [[
                        [-52.000, -27.001], [-51.998, -27.001], [-51.998, -26.999],
                        [-52.000, -26.999], [-52.000, -27.001],
                    ]]),
                )
            ],
        }).encode()
        with TestClient(create_app()) as client:
            project_id = str(
                client.post("/v1/projects", json={"name": "Chave nomeada"}).json()["id"]
            )
            response = client.post(
                f"/v1/projects/{project_id}/layers",
                data={
                    "layer_type": "territorio",
                    "import_profile": "split",
                    "attributes_join_key": "Name",
                    "geometry_join_key": "URBDATA_ID",
                },
                files={
                    "file": ("t.geojson", geojson, "application/geo+json"),
                    "attributes_file": (
                        "a.csv",
                        b"Name;Area\nL01;100\nL02;200\n",
                        "text/csv",
                    ),
                },
            )
            assert response.status_code == 201, response.text
            layer = response.json()
            assert layer["geometry_join_key"] == "URBDATA_ID"
            assert layer["join_summary"]["matched"] == 2

            geojson_out = client.get(
                f"/v1/projects/{project_id}/layers/{layer['id']}/geojson"
            ).json()
            # GeoJSON output "id" is always the internal Feature UUID
            # (ADR 014), never the original feature.id/external_id - key by
            # a property value instead, same as the b7.4 real-sample test.
            properties_by_urbdata_id = {
                feature["properties"]["URBDATA_ID"]: feature["properties"]
                for feature in geojson_out["features"]
            }
            assert properties_by_urbdata_id["L01"] == {
                "URBDATA_ID": "L01",
                "Name": "L01",
                "Area": "100",
            }
            assert properties_by_urbdata_id["L02"] == {
                "URBDATA_ID": "L02",
                "Name": "L02",
                "Area": "200",
            }


class TestSplitImportRealSample:
    """b7.4: the real GeoJSON+CSV pair evaluated in nota 53 (102 features,
    UTF-8 with BOM, ';' delimiter) - a permanent fixture, not a substitute
    for the synthetic tests above."""

    def test_real_sample_uploads_and_joins_all_102_features(self) -> None:
        with TestClient(create_app()) as client:
            project_id = str(
                client.post("/v1/projects", json={"name": "Amostra real"}).json()["id"]
            )
            response = client.post(
                f"/v1/projects/{project_id}/layers",
                data={
                    "layer_type": "territorio",
                    "import_profile": "split",
                    "attributes_join_key": "Name",
                },
                files={
                    "file": (
                        "PROJETO_R01_GEOMETRIA.json",
                        REAL_SPLIT_GEOMETRY_FIXTURE.read_bytes(),
                        "application/geo+json",
                    ),
                    "attributes_file": (
                        "DATA_EXPORT_PROJETO_01.csv",
                        REAL_SPLIT_ATTRIBUTES_FIXTURE.read_bytes(),
                        "text/csv",
                    ),
                },
            )
            assert response.status_code == 201, response.text
            layer = response.json()
            assert layer["feature_count"] == 102
            assert layer["join_summary"] == {
                "geometry_count": 102,
                "attribute_count": 102,
                "matched": 102,
                "missing_geometry_keys": [],
                "missing_attribute_keys": [],
                "duplicate_geometry_keys": [],
                "duplicate_attribute_keys": [],
            }

            geojson = client.get(
                f"/v1/projects/{project_id}/layers/{layer['id']}/geojson"
            ).json()
            properties_by_name = {
                feature["properties"]["Name"]: feature["properties"]
                for feature in geojson["features"]
            }
            assert len(properties_by_name) == 102

            av_1 = properties_by_name["AV-1"]
            assert av_1["TIPO DE MACROÁREA"] == "AVL"
            assert av_1["Area"] == "1338.63 m²"

            l_01 = properties_by_name["L-01"]
            assert l_01["Uso do solo"] == "Misto"
            assert l_01["07.COEFICIENTE DE APROVEITAMENTO"] == "2"

            app_1 = properties_by_name["app-1"]
            assert app_1["QUADRA"] == ""  # 3 of 102 rows have this genuinely empty
