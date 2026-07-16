from shapely.geometry.base import BaseGeometry

from app.domain.analysis.exceptions import InvalidGeometryError
from app.domain.geospatial.crs import require_metric_crs


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
        raise InvalidGeometryError("A valid, non-empty geometry is required for length calculation.")
    return float(geometry.length)
