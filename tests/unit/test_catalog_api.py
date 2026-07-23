"""The catalog endpoint is database-free, so it gets full unit coverage."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class TestCatalogIndicatorsEndpoint:
    def test_returns_every_registered_indicator(self) -> None:
        response = client.get("/v1/catalog/indicators")

        assert response.status_code == 200
        body = response.json()
        assert len(body) == 35
        assert {entry["theme"] for entry in body} == {
            "territorial",
            "land_use",
            "green_areas",
            "quadras",
            "road_network",
            "density",
            "lots",
        }

    def test_entries_carry_presentation_and_join_metadata(self) -> None:
        body = client.get("/v1/catalog/indicators").json()
        by_code = {entry["code"]: entry for entry in body}

        frontage = by_code["lots.frontage_length"]
        assert frontage["granularity"] == "por_feicao"
        assert frontage["feature_key"] == "feature_id"
        assert frontage["display_name"]
        assert frontage["description"]
        assert frontage["required_layers"] == ["territorio"]

        total_area = by_code["territorial.total_area"]
        assert total_area["granularity"] == "projeto"
        assert total_area["feature_key"] is None
        assert total_area["unit"] == "m2"
        assert total_area["display_name"].startswith(chr(0xC1) + "rea")
        assert total_area["value_shape"] == "scalar"

        quadras_stats = by_code["quadras.stats"]
        assert quadras_stats["value_shape"] == "feature_compound"
        area_by_category = by_code["territorial.area_by_category"]
        assert area_by_category["value_shape"] == "category_breakdown"

    def test_sorted_by_theme_then_code(self) -> None:
        body = client.get("/v1/catalog/indicators").json()
        keys = [(entry["theme"], entry["code"]) for entry in body]
        assert keys == sorted(keys)

    def test_internal_flag_defaults_false_and_is_true_for_face_length_score(self) -> None:
        """Parecer da revisao teorica, nota 71/87/88 (22/07/2026): a
        metrica interna continua no catalogo, so nao deve virar card de
        destaque - o frontend le esse campo para decidir isso."""
        body = client.get("/v1/catalog/indicators").json()
        by_code = {entry["code"]: entry for entry in body}

        assert by_code["quadras.face_length_score"]["internal"] is True
        assert by_code["territorial.total_area"]["internal"] is False
        assert by_code["green_areas.total_area"]["internal"] is False

    def test_green_area_with_app_variants_are_additive(self) -> None:
        """Parecer da revisao teorica, nota 66/67 (22/07/2026): as duas
        variantes com APP sao indicadores novos, as duas variantes AVL-only
        continuam exatamente como estavam."""
        body = client.get("/v1/catalog/indicators").json()
        by_code = {entry["code"]: entry for entry in body}

        with_app_total = by_code["green_areas.total_area_with_app"]
        assert with_app_total["value_shape"] == "scalar"
        assert with_app_total["unit"] == "m2"
        assert with_app_total["granularity"] == "projeto"

        with_app_percent = by_code["green_areas.percent_of_project_with_app"]
        assert with_app_percent["value_shape"] == "scalar"
        assert with_app_percent["unit"] == "ratio"

        # AVL-only variants unchanged
        assert by_code["green_areas.total_area"]["unit"] == "m2"
        assert by_code["green_areas.percent_of_project"]["unit"] == "ratio"
