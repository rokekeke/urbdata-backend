"""The catalog endpoint is database-free, so it gets full unit coverage."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class TestCatalogIndicatorsEndpoint:
    def test_returns_every_registered_indicator(self) -> None:
        response = client.get("/v1/catalog/indicators")

        assert response.status_code == 200
        body = response.json()
        assert len(body) == 27
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

    def test_sorted_by_theme_then_code(self) -> None:
        body = client.get("/v1/catalog/indicators").json()
        keys = [(entry["theme"], entry["code"]) for entry in body]
        assert keys == sorted(keys)
