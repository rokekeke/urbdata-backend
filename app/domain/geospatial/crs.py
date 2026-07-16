import math

from pyproj import CRS
from pyproj.aoi import AreaOfInterest
from pyproj.database import query_utm_crs_info
from pyproj.transformer import Transformer
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform

from app.domain.analysis.exceptions import MetricCRSSelectionError

DEFAULT_METRIC_CRS = CRS.from_epsg(32722)
WGS84 = CRS.from_epsg(4326)


def require_metric_crs(crs: CRS | str | int) -> CRS:
    parsed = CRS.from_user_input(crs)
    axis_units = {axis.unit_name.lower() for axis in parsed.axis_info if axis.unit_name}
    if not parsed.is_projected or not axis_units or not axis_units <= {"metre", "meter"}:
        raise MetricCRSSelectionError(
            "A projected metric CRS is required for metric calculations.",
            context={"crs": parsed.to_string(), "axis_units": sorted(axis_units)},
        )
    return parsed


def select_metric_crs(
    project_geometry: BaseGeometry,
    source_crs: CRS | str | int | None,
    *,
    default_crs: CRS | str | int = DEFAULT_METRIC_CRS,
) -> CRS:
    """Select one WGS 84 UTM CRS that fully contains the project extent.

    EPSG:32722 (WGS 84 / UTM zone 22S) is preferred when the entire project
    lies inside its area of use. Outside that zone, the PyProj database is
    queried at the project centre and the resulting CRS is accepted only when
    its area of use contains the full extent. Projects crossing a UTM boundary
    therefore fail explicitly instead of being measured in a distorted CRS.
    """
    if source_crs is None:
        raise MetricCRSSelectionError("The project source CRS is required.")
    if project_geometry.is_empty:
        raise MetricCRSSelectionError("A non-empty project geometry is required.")

    source = CRS.from_user_input(source_crs)
    try:
        to_wgs84 = Transformer.from_crs(source, WGS84, always_xy=True)
        geometry_wgs84 = transform(to_wgs84.transform, project_geometry)
    except Exception as exc:
        raise MetricCRSSelectionError(
            "The project geometry could not be transformed to WGS 84.",
            context={"source_crs": source.to_string()},
        ) from exc

    west, south, east, north = geometry_wgs84.bounds
    bounds = (west, south, east, north)
    if not all(math.isfinite(value) for value in bounds):
        raise MetricCRSSelectionError("The project extent contains non-finite coordinates.")
    if west < -180 or east > 180 or south < -90 or north > 90:
        raise MetricCRSSelectionError(
            "The project extent is outside valid longitude or latitude limits.",
            context={"bounds_wgs84": bounds},
        )

    preferred = require_metric_crs(default_crs)
    if _contains_extent(preferred, bounds):
        return preferred

    center_x = (west + east) / 2
    center_y = (south + north) / 2
    candidates = query_utm_crs_info(
        datum_name="WGS 84",
        area_of_interest=AreaOfInterest(center_x, center_y, center_x, center_y),
        contains=True,
    )
    for info in candidates:
        candidate = require_metric_crs(CRS.from_authority(info.auth_name, info.code))
        if _contains_extent(candidate, bounds):
            return candidate

    raise MetricCRSSelectionError(
        "No single WGS 84 UTM zone contains the complete project extent.",
        context={"bounds_wgs84": bounds, "default_crs": preferred.to_string()},
    )


def _contains_extent(crs: CRS, bounds: tuple[float, float, float, float]) -> bool:
    area = crs.area_of_use
    if area is None:
        return False
    west, south, east, north = bounds
    tolerance = 1e-9
    return (
        west >= area.west - tolerance
        and east <= area.east + tolerance
        and south >= area.south - tolerance
        and north <= area.north + tolerance
    )
