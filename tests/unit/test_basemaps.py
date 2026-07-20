"""Basemap catalog (ADR 014, Decisao 5) - static, credential-free."""

import pytest
from fastapi.testclient import TestClient

from app.domain.cartography.basemaps import BASEMAPS, Basemap, BasemapColorMode
from app.main import app

client = TestClient(app)


class TestBasemapCatalog:
    def test_none_entry_is_always_present(self) -> None:
        assert any(basemap.id == "none" and basemap.style_url is None for basemap in BASEMAPS)

    def test_every_real_basemap_has_attribution_and_no_credentials(self) -> None:
        for basemap in BASEMAPS:
            if basemap.style_url is None:
                continue
            assert basemap.attribution, basemap.id
            assert "token" not in basemap.style_url
            assert "key=" not in basemap.style_url

    def test_basemap_without_attribution_is_impossible(self) -> None:
        with pytest.raises(ValueError):
            Basemap(
                id="x",
                label="X",
                style_url="https://example.com/style.json",
                color_mode=BasemapColorMode.LIGHT,
                attribution=None,
                export_allowed=True,
            )


class TestBasemapEndpoint:
    def test_lists_the_catalog(self) -> None:
        response = client.get("/v1/map-basemaps")

        assert response.status_code == 200
        body = response.json()
        assert [entry["id"] for entry in body] == [
            "none",
            "positron",
            "dark_matter",
            "voyager",
        ]
        carto = [entry for entry in body if entry["style_url"]]
        assert all(entry["attribution"] for entry in carto)
        assert all(entry["export_allowed"] for entry in body)
