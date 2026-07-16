from pyproj import CRS

from app.domain.analysis.exceptions import MetricCRSSelectionError


def require_metric_crs(crs: CRS | str | int) -> CRS:
    parsed = CRS.from_user_input(crs)
    axis_units = {axis.unit_name.lower() for axis in parsed.axis_info if axis.unit_name}
    if not parsed.is_projected or not axis_units or not axis_units <= {"metre", "meter"}:
        raise MetricCRSSelectionError(
            "A projected metric CRS is required for metric calculations.",
            context={"crs": parsed.to_string(), "axis_units": sorted(axis_units)},
        )
    return parsed
