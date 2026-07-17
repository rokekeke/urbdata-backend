import warnings
from uuid import UUID

from geopandas import GeoDataFrame
from shapely.geometry.base import BaseGeometry

from app.domain.analysis.exceptions import InvalidGeometryError
from app.domain.geospatial.crs import require_metric_crs


def dissolve(gdf: GeoDataFrame) -> tuple[BaseGeometry, tuple[UUID, ...], tuple[UUID, ...]]:
    """Union every valid, non-empty geometry in *gdf*.

    Returns the unioned geometry, the `feature_id`s that contributed, and the
    `feature_id`s skipped for being null, empty, or invalid. Geometries in
    *gdf* are read only; nothing is written back to storage (ADR 001/005).
    """
    # `.notna()` already excludes only missing values here; `.is_empty` is
    # checked separately, so this is exactly the non-deprecated combination
    # GeoPandas' own UserWarning recommends - safe to silence.
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="GeoSeries.notna()", category=UserWarning)
        valid_mask = ~gdf.geometry.is_empty & gdf.geometry.notna() & gdf.geometry.is_valid
    valid = gdf[valid_mask]
    if valid.empty:
        raise InvalidGeometryError("No valid, non-empty geometry available to dissolve.")
    skipped = tuple(gdf.loc[~valid_mask, "feature_id"])
    contributing = tuple(valid["feature_id"])
    geometry = valid.geometry.union_all()
    return geometry, contributing, skipped


def area_m2(geometry: BaseGeometry, *, crs: str | int) -> float:
    require_metric_crs(crs)
    if geometry.is_empty or not geometry.is_valid:
        raise InvalidGeometryError("A valid, non-empty geometry is required for area calculation.")
    value = float(geometry.area)
    if value <= 0:
        raise InvalidGeometryError("Geometry area must be greater than zero.")
    return value


def length_m(geometry: BaseGeometry, *, crs: str | int) -> float:
    require_metric_crs(crs)
    if geometry.is_empty or not geometry.is_valid:
        raise InvalidGeometryError(
            "A valid, non-empty geometry is required for length calculation."
        )
    return float(geometry.length)
