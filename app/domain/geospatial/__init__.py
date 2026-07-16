"""Pure geospatial operations with explicit CRS and immutable source geometry."""

from app.domain.geospatial.crs import DEFAULT_METRIC_CRS, require_metric_crs, select_metric_crs

__all__ = ["DEFAULT_METRIC_CRS", "require_metric_crs", "select_metric_crs"]
