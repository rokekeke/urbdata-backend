from collections.abc import Mapping
from typing import Any


class AnalysisError(Exception):
    code = "analysis_error"

    def __init__(self, message: str, *, context: Mapping[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.context = dict(context or {})


class ProjectNotFoundError(AnalysisError):
    code = "project_not_found"


class ProjectVersionNotFoundError(AnalysisError):
    code = "project_version_not_found"


class RequiredLayerMissingError(AnalysisError):
    code = "required_layer_missing"


class InvalidGeometryError(AnalysisError):
    code = "invalid_geometry"


class MetricCRSSelectionError(AnalysisError):
    code = "metric_crs_selection_failed"


class IndicatorCalculationError(AnalysisError):
    code = "indicator_calculation_failed"


class IndicatorDependencyError(AnalysisError):
    code = "indicator_dependency_failed"
