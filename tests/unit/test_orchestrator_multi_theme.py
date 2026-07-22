"""End-to-end wiring check for ADR 008/009: a single TERRITORIO layer,
filtered by `macroarea` and grouped by `quadra_id`, feeding four themes
(territorial, land_use, green_areas, quadras) through the real orchestrator
in one run.
"""

import uuid
from typing import Any

import pytest
from geopandas import GeoDataFrame
from pyproj import CRS
from shapely.geometry import Polygon

from app.application.analysis.analyze_project import AnalyzeProjectCommand
from app.application.analysis.orchestrator import SynchronousAnalysisOrchestrator
from app.domain.geospatial.layers import LoadedFeatureLayer
from app.domain.indicators.catalog import build_registry

PROJECT_ID = uuid.uuid4()
VERSION_ID = uuid.uuid4()


class FakeProjectVersions:
    def current_version_id(self, project_id: uuid.UUID) -> uuid.UUID:
        return VERSION_ID


class FakeLayerLoader:
    def __init__(self, layers: dict[str, LoadedFeatureLayer]) -> None:
        self._layers = layers

    def load_layer_by_type(
        self, project_version_id: uuid.UUID, layer_type: str
    ) -> LoadedFeatureLayer | None:
        return self._layers.get(layer_type)


class FakeRunStore:
    def __init__(self) -> None:
        self.run_id = uuid.uuid4()

    def create_pending(self, project_version_id: uuid.UUID, *, config: dict[str, Any]) -> uuid.UUID:
        return self.run_id

    def mark_running(self, run_id: uuid.UUID) -> None:
        pass

    def mark_completed(self, run_id: uuid.UUID, *, duration_ms: int) -> None:
        pass

    def mark_failed(self, run_id: uuid.UUID, *, error: dict[str, Any], duration_ms: int) -> None:
        pass


class FakeResultStore:
    def save_batch(self, run_id: uuid.UUID, results: tuple[Any, ...]) -> None:
        pass


def _square(west: float, south: float, east: float, north: float) -> Polygon:
    return Polygon([(west, south), (east, south), (east, north), (west, north)])


def _perimeter_layer() -> LoadedFeatureLayer:
    square = _square(-52.0, -27.0, -51.999, -26.999)
    gdf = GeoDataFrame({"feature_id": [uuid.uuid4()], "geometry": [square]}, crs="EPSG:4326")
    return LoadedFeatureLayer(
        layer_id=uuid.uuid4(), layer_type="perimetro", source_crs=CRS.from_epsg(4326), gdf=gdf
    )


def _territorio_layer() -> tuple[LoadedFeatureLayer, dict[str, uuid.UUID]]:
    """Five features sharing the perimeter's bounding box: two plain-use
    lots sharing quadra Q1 (adjacent, so they dissolve into one outline),
    one mixed-use lot alone in quadra Q2 (comma-delimited raw value), one
    AVL with a reference area that diverges past the 5% threshold (must
    warn), and one APP (must be excluded from land_use/green_areas, and
    from quadras since it isn't a Lote)."""
    ids = {
        "lot_res": uuid.uuid4(),
        "lot_com": uuid.uuid4(),
        "lot_misto": uuid.uuid4(),
        "avl": uuid.uuid4(),
        "app": uuid.uuid4(),
    }
    geometries = [
        _square(-52.0000, -27.0000, -51.9998, -26.9998),
        _square(-51.9998, -27.0000, -51.9996, -26.9998),
        _square(-51.9996, -27.0000, -51.9994, -26.9998),
        _square(-51.9994, -27.0000, -51.9992, -26.9998),
        _square(-51.9992, -27.0000, -51.9990, -26.9998),
    ]
    gdf = GeoDataFrame(
        {
            "feature_id": list(ids.values()),
            "geometry": geometries,
            "macroarea": ["lote", "lote", "lote", "avl", "app"],
            "parcelavel": [True, True, True, True, False],
            "land_use": ["residencial", "comercial", "residencial;comercial", None, None],
            "quadra_id": ["Q1", "Q1", "Q2", None, None],
            # AVL's reference diverges >5% from its ~484 m2 geometric area
            # (a ~22x22m square) - must trigger area_reference_divergence,
            # while staying a plausible fraction of the project's ~12_000 m2.
            "reference_area_m2": [None, None, None, 300.0, None],
        },
        crs="EPSG:4326",
    )
    layer = LoadedFeatureLayer(
        layer_id=uuid.uuid4(), layer_type="territorio", source_crs=CRS.from_epsg(4326), gdf=gdf
    )
    return layer, ids


def test_all_three_themes_run_together_against_one_territorio_layer() -> None:
    perimeter = _perimeter_layer()
    territorio, feature_ids = _territorio_layer()
    orchestrator = SynchronousAnalysisOrchestrator(
        project_versions=FakeProjectVersions(),
        layers=FakeLayerLoader({"perimetro": perimeter, "territorio": territorio}),
        runs=FakeRunStore(),
        results=FakeResultStore(),
        registry=build_registry(),
        default_metric_crs="EPSG:32722",
    )
    command = AnalyzeProjectCommand(
        project_id=PROJECT_ID, themes=("territorial", "land_use", "green_areas", "quadras")
    )

    outcome = orchestrator.execute(command)

    by_code = {result.indicator_code: result for result in outcome.results}
    assert set(by_code) == {
        "territorial.total_area",
        "territorial.perimeter",
        "territorial.compactness",
        "territorial.area_by_category",
        "territorial.percent_by_category",
        "land_use.area_by_category",
        "land_use.percent_by_category",
        "land_use.predominant_use",
        "land_use.diversity_shannon",
        "green_areas.total_area",
        "green_areas.percent_of_project",
        "green_areas.total_area_with_app",
        "green_areas.percent_of_project_with_app",
        "quadras.stats",
        "quadras.compactness",
        "quadras.min_rotated_rectangle",
        "quadras.face_length_score",
    }

    # territorial: full inventory includes every macroarea (BT-043)...
    territorial_area = by_code["territorial.area_by_category"]
    assert isinstance(territorial_area.raw_value, dict)
    assert set(territorial_area.raw_value) == {"lote", "avl", "app"}

    # ...but the percent view (BT-044) drops the non-parcelavel APP feature
    # from both numerator and denominator, so lote+avl sum to ~100%.
    territorial_percent = by_code["territorial.percent_by_category"]
    assert isinstance(territorial_percent.raw_value, dict)
    assert set(territorial_percent.raw_value) == {"lote", "avl"}
    assert sum(territorial_percent.raw_value.values()) == pytest.approx(1.0)

    # land_use: three lots classified, none unclassified/excluded.
    area_by_category = by_code["land_use.area_by_category"]
    assert isinstance(area_by_category.raw_value, dict)
    assert set(area_by_category.raw_value) == {"residencial", "comercial", "misto"}
    assert set(area_by_category.contributing_feature_ids) == {
        feature_ids["lot_res"],
        feature_ids["lot_com"],
        feature_ids["lot_misto"],
    }

    percent_by_category = by_code["land_use.percent_by_category"]
    assert isinstance(percent_by_category.raw_value, dict)
    assert sum(percent_by_category.raw_value.values()) == pytest.approx(1.0)

    # green_areas: only the AVL feature counts, APP is excluded.
    green_total = by_code["green_areas.total_area"]
    assert green_total.contributing_feature_ids == (feature_ids["avl"],)
    assert isinstance(green_total.raw_value, float) and green_total.raw_value > 0

    green_percent = by_code["green_areas.percent_of_project"]
    assert isinstance(green_percent.raw_value, float)
    assert 0 < green_percent.raw_value < 1

    # The AVL feature's absurd reference_area_m2 must surface a warning on
    # both green_areas indicators that consume it.
    assert any(w.code == "area_reference_divergence" for w in green_total.warnings)
    assert any(w.code == "area_reference_divergence" for w in green_percent.warnings)

    # green_areas *_with_app: additive over the AVL-only readings - APP
    # brings its own geometric area in (no reference override), so both
    # with-APP results must sit strictly above their AVL-only siblings, and
    # both feature ids must contribute.
    green_total_with_app = by_code["green_areas.total_area_with_app"]
    assert set(green_total_with_app.contributing_feature_ids) == {
        feature_ids["avl"],
        feature_ids["app"],
    }
    assert isinstance(green_total_with_app.raw_value, float)
    assert green_total_with_app.raw_value > green_total.raw_value

    green_percent_with_app = by_code["green_areas.percent_of_project_with_app"]
    assert isinstance(green_percent_with_app.raw_value, float)
    assert 0 < green_percent_with_app.raw_value < 1
    assert green_percent_with_app.raw_value > green_percent.raw_value

    # AVL's divergence still surfaces even once APP joins the reading.
    assert any(w.code == "area_reference_divergence" for w in green_total_with_app.warnings)
    assert any(w.code == "area_reference_divergence" for w in green_percent_with_app.warnings)

    # quadras: Q1 dissolves two adjacent lots into one outline, Q2 has one.
    # APP never had a quadra_id and isn't a Lote either way, so it never
    # appears here.
    stats = by_code["quadras.stats"]
    assert isinstance(stats.raw_value, dict)
    assert set(stats.raw_value) == {"Q1", "Q2"}
    assert stats.raw_value["Q1"]["quantidade_lotes"] == 2
    assert stats.raw_value["Q2"]["quantidade_lotes"] == 1
    # Adjacent, non-overlapping lots dissolve without losing area.
    assert stats.raw_value["Q1"]["area_m2"] == pytest.approx(
        stats.raw_value["Q2"]["area_m2"] * 2, rel=0.05
    )

    compactness = by_code["quadras.compactness"]
    assert isinstance(compactness.raw_value, dict)
    assert set(compactness.raw_value) == {"Q1", "Q2"}
    for value in compactness.raw_value.values():
        assert 0 < value <= 1

    rectangle = by_code["quadras.min_rotated_rectangle"]
    assert isinstance(rectangle.raw_value, dict)
    assert set(rectangle.raw_value) == {"Q1", "Q2"}
    for dims in rectangle.raw_value.values():
        assert dims["comprimento_m"] >= dims["largura_m"] > 0

    # Both quadras here are tiny (well under the 120m ideal), so both score
    # a perfect 1.0 with no compliance warning.
    face_length_score = by_code["quadras.face_length_score"]
    assert isinstance(face_length_score.raw_value, dict)
    assert face_length_score.raw_value == {"Q1": pytest.approx(1.0), "Q2": pytest.approx(1.0)}
    assert not any(w.code == "block_face_out_of_compliance" for w in face_length_score.warnings)
