from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol
from uuid import UUID

from app.application.analysis.dependency_resolver import resolve_dependencies
from app.domain.analysis.definitions import IndicatorDefinition
from app.domain.analysis.exceptions import (
    AnalysisError,
    IndicatorDependencyError,
    RequiredLayerMissingError,
)
from app.domain.analysis.registry import IndicatorRegistry
from app.domain.analysis.result import IndicatorCalculation
from app.domain.geospatial.context import GeospatialContext
from app.domain.geospatial.crs import select_metric_crs
from app.domain.geospatial.geometry import dissolve
from app.domain.geospatial.layers import LoadedFeatureLayer

if TYPE_CHECKING:
    from app.application.analysis.analyze_project import AnalyzeProjectCommand


@dataclass(frozen=True, slots=True)
class AnalysisRunOutcome:
    run_id: UUID
    results: tuple[IndicatorCalculation, ...]


class AnalysisOrchestrator(Protocol):
    """Port that can later be implemented by a synchronous service or a queued worker."""

    def execute(self, command: AnalyzeProjectCommand) -> AnalysisRunOutcome: ...


class ProjectVersionResolver(Protocol):
    def current_version_id(self, project_id: UUID) -> UUID: ...


class LayerLoader(Protocol):
    def load_layer_by_type(
        self, project_version_id: UUID, layer_type: str
    ) -> LoadedFeatureLayer | None: ...


class AnalysisRunStore(Protocol):
    def create_pending(self, project_version_id: UUID, *, config: dict[str, Any]) -> UUID: ...
    def mark_running(self, run_id: UUID) -> None: ...
    def mark_completed(self, run_id: UUID, *, duration_ms: int) -> None: ...
    def mark_failed(self, run_id: UUID, *, error: dict[str, Any], duration_ms: int) -> None: ...


class IndicatorResultStore(Protocol):
    def save_batch(self, run_id: UUID, results: tuple[IndicatorCalculation, ...]) -> None: ...


PERIMETER_LAYER = "perimetro"


@dataclass(slots=True)
class SynchronousAnalysisOrchestrator:
    """MVP orchestrator (ADR 004): resolves indicators, loads every required
    layer once, selects the metric CRS from the perimeter, and runs every
    calculator synchronously against the resulting `GeospatialContext`.
    """

    project_versions: ProjectVersionResolver
    layers: LayerLoader
    runs: AnalysisRunStore
    results: IndicatorResultStore
    registry: IndicatorRegistry
    default_metric_crs: str
    indicator_parameters: dict[str, Any] | None = None

    def execute(self, command: AnalyzeProjectCommand) -> AnalysisRunOutcome:
        definitions = self._resolve_definitions(command.themes)
        version_id = self.project_versions.current_version_id(command.project_id)
        effective_parameters = dict(self.indicator_parameters or {})
        run_id = self.runs.create_pending(
            version_id,
            config={
                "themes": list(command.themes),
                "default_metric_crs": self.default_metric_crs,
                "indicator_parameters": effective_parameters,
            },
        )
        self.runs.mark_running(run_id)
        started = time.monotonic()
        try:
            context = self._build_context(version_id, definitions)
            calculations = tuple(definition.calculator(context) for definition in definitions)
            self.results.save_batch(run_id, calculations)
        except AnalysisError as exc:
            self._fail(run_id, started, code=exc.code, message=exc.message, extra=exc.context)
            raise
        except Exception as exc:  # noqa: BLE001 - normalized into an auditable run failure
            self._fail(run_id, started, code="unexpected_error", message=str(exc), extra={})
            raise
        else:
            self.runs.mark_completed(run_id, duration_ms=self._elapsed_ms(started))
            return AnalysisRunOutcome(run_id=run_id, results=calculations)

    def _resolve_definitions(self, themes: tuple[str, ...]) -> tuple[IndicatorDefinition, ...]:
        selected: list[IndicatorDefinition] = []
        for theme in themes:
            by_theme = self.registry.by_theme(theme)
            if not by_theme:
                raise IndicatorDependencyError(
                    "Theme has no registered indicators.", context={"theme": theme}
                )
            selected.extend(by_theme)
        return resolve_dependencies(tuple(selected))

    def _build_context(
        self, version_id: UUID, definitions: tuple[IndicatorDefinition, ...]
    ) -> GeospatialContext:
        required_layer_types = sorted(
            {layer_type for definition in definitions for layer_type in definition.required_layers}
            | {PERIMETER_LAYER}
        )
        optional_layer_types = sorted(
            {layer_type for definition in definitions for layer_type in definition.optional_layers}
            - set(required_layer_types)
        )
        layers: dict[str, LoadedFeatureLayer] = {}
        for layer_type in required_layer_types:
            loaded = self.layers.load_layer_by_type(version_id, layer_type)
            if loaded is None:
                raise RequiredLayerMissingError(
                    "Required layer is missing for this analysis.",
                    context={"layer_type": layer_type},
                )
            layers[layer_type] = loaded

        for layer_type in optional_layer_types:
            loaded = self.layers.load_layer_by_type(version_id, layer_type)
            if loaded is not None:
                layers[layer_type] = loaded

        perimeter_wgs84, _, _ = dissolve(layers[PERIMETER_LAYER].gdf)
        metric_crs = select_metric_crs(
            perimeter_wgs84,
            layers[PERIMETER_LAYER].source_crs,
            default_crs=self.default_metric_crs,
        )
        return GeospatialContext(
            project_version_id=version_id,
            metric_crs=metric_crs,
            layers=layers,
            parameters=dict(self.indicator_parameters or {}),
        )

    def _fail(
        self, run_id: UUID, started: float, *, code: str, message: str, extra: dict[str, Any]
    ) -> None:
        self.runs.mark_failed(
            run_id,
            error={"code": code, "message": message, "context": extra},
            duration_ms=self._elapsed_ms(started),
        )

    @staticmethod
    def _elapsed_ms(started: float) -> int:
        return int((time.monotonic() - started) * 1000)
