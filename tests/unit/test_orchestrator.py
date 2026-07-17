import uuid
from typing import Any

import pytest
from geopandas import GeoDataFrame
from pyproj import CRS
from shapely.geometry import Polygon

from app.application.analysis.analyze_project import AnalyzeProjectCommand
from app.application.analysis.orchestrator import SynchronousAnalysisOrchestrator
from app.domain.analysis.exceptions import IndicatorDependencyError, RequiredLayerMissingError
from app.domain.analysis.result import IndicatorCalculation
from app.domain.geospatial.layers import LoadedFeatureLayer
from app.domain.indicators.catalog import build_registry

PROJECT_ID = uuid.uuid4()
VERSION_ID = uuid.uuid4()


class FakeProjectVersions:
    def current_version_id(self, project_id: uuid.UUID) -> uuid.UUID:
        assert project_id == PROJECT_ID
        return VERSION_ID


class FakeLayerLoader:
    def __init__(self, layers: dict[str, LoadedFeatureLayer]) -> None:
        self._layers = layers

    def load_layer_by_type(
        self, project_version_id: uuid.UUID, layer_type: str
    ) -> LoadedFeatureLayer | None:
        assert project_version_id == VERSION_ID
        return self._layers.get(layer_type)


class FakeRunStore:
    def __init__(self) -> None:
        self.run_id = uuid.uuid4()
        self.calls: list[tuple[Any, ...]] = []

    def create_pending(self, project_version_id: uuid.UUID, *, config: dict[str, Any]) -> uuid.UUID:
        assert project_version_id == VERSION_ID
        self.calls.append(("create_pending", config))
        return self.run_id

    def mark_running(self, run_id: uuid.UUID) -> None:
        self.calls.append(("mark_running", run_id))

    def mark_completed(self, run_id: uuid.UUID, *, duration_ms: int) -> None:
        self.calls.append(("mark_completed", run_id))

    def mark_failed(self, run_id: uuid.UUID, *, error: dict[str, Any], duration_ms: int) -> None:
        self.calls.append(("mark_failed", run_id, error))


class FakeResultStore:
    def __init__(self) -> None:
        self.saved: tuple[uuid.UUID, tuple[IndicatorCalculation, ...]] | None = None

    def save_batch(self, run_id: uuid.UUID, results: tuple[IndicatorCalculation, ...]) -> None:
        self.saved = (run_id, results)


def _perimeter_layer() -> LoadedFeatureLayer:
    square = Polygon([(-52.0, -27.0), (-52.0, -26.999), (-51.999, -26.999), (-51.999, -27.0)])
    gdf = GeoDataFrame({"feature_id": [uuid.uuid4()], "geometry": [square]}, crs="EPSG:4326")
    return LoadedFeatureLayer(
        layer_id=uuid.uuid4(), layer_type="perimetro", source_crs=CRS.from_epsg(4326), gdf=gdf
    )


def _territorio_layer() -> LoadedFeatureLayer:
    """One parcelavel Lote feature - enough to satisfy
    territorial.area_by_category/percent_by_category (BT-043/044)."""
    square = Polygon(
        [(-52.0, -27.0), (-52.0, -26.9998), (-51.9998, -26.9998), (-51.9998, -27.0)]
    )
    gdf = GeoDataFrame(
        {
            "feature_id": [uuid.uuid4()],
            "geometry": [square],
            "macroarea": ["lote"],
            "parcelavel": [True],
            "land_use": ["residencial"],
            "reference_area_m2": [None],
        },
        crs="EPSG:4326",
    )
    return LoadedFeatureLayer(
        layer_id=uuid.uuid4(), layer_type="territorio", source_crs=CRS.from_epsg(4326), gdf=gdf
    )


def _orchestrator(
    layers: dict[str, LoadedFeatureLayer], runs: FakeRunStore, results: FakeResultStore
) -> SynchronousAnalysisOrchestrator:
    return SynchronousAnalysisOrchestrator(
        project_versions=FakeProjectVersions(),
        layers=FakeLayerLoader(layers),
        runs=runs,
        results=results,
        registry=build_registry(),
        default_metric_crs="EPSG:32722",
    )


def test_happy_path_completes_the_run_and_persists_the_result() -> None:
    runs, results = FakeRunStore(), FakeResultStore()
    layers = {"perimetro": _perimeter_layer(), "territorio": _territorio_layer()}
    orchestrator = _orchestrator(layers, runs, results)
    command = AnalyzeProjectCommand(project_id=PROJECT_ID, themes=("territorial",))

    outcome = orchestrator.execute(command)

    assert outcome.run_id == runs.run_id
    assert [call[0] for call in runs.calls] == ["create_pending", "mark_running", "mark_completed"]
    assert results.saved is not None
    assert results.saved[0] == runs.run_id
    by_code = {result.indicator_code: result for result in outcome.results}
    assert set(by_code) == {
        "territorial.total_area",
        "territorial.perimeter",
        "territorial.compactness",
        "territorial.area_by_category",
        "territorial.percent_by_category",
    }
    for code in ("territorial.total_area", "territorial.perimeter", "territorial.compactness"):
        raw_value = by_code[code].raw_value
        assert isinstance(raw_value, float) and raw_value > 0
    for code in ("territorial.area_by_category", "territorial.percent_by_category"):
        raw_value = by_code[code].raw_value
        assert isinstance(raw_value, dict) and raw_value.get("lote", 0) > 0


def test_unknown_theme_marks_the_run_failed_and_reraises() -> None:
    runs, results = FakeRunStore(), FakeResultStore()
    orchestrator = _orchestrator({"perimetro": _perimeter_layer()}, runs, results)
    command = AnalyzeProjectCommand(project_id=PROJECT_ID, themes=("nao_existe",))

    with pytest.raises(IndicatorDependencyError):
        orchestrator.execute(command)

    assert runs.calls == []
    assert results.saved is None


def test_missing_perimeter_layer_marks_the_run_failed_and_reraises() -> None:
    runs, results = FakeRunStore(), FakeResultStore()
    orchestrator = _orchestrator({}, runs, results)
    command = AnalyzeProjectCommand(project_id=PROJECT_ID, themes=("territorial",))

    with pytest.raises(RequiredLayerMissingError):
        orchestrator.execute(command)

    assert [call[0] for call in runs.calls] == ["create_pending", "mark_running", "mark_failed"]
    assert results.saved is None
    failure = runs.calls[-1]
    assert failure[2]["code"] == "required_layer_missing"
