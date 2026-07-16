from uuid import UUID

from shapely.geometry.base import BaseGeometry

from app.domain.analysis.result import IndicatorCalculation
from app.domain.geospatial.geometry import area_m2


def calculate_total_area(
    geometry: BaseGeometry,
    *,
    metric_crs: str | int,
    contributing_feature_ids: tuple[UUID, ...] = (),
) -> IndicatorCalculation:
    return IndicatorCalculation(
        indicator_code="territorial.total_area",
        theme="territorial",
        formula_version="1.0.0",
        raw_value=area_m2(geometry, crs=metric_crs),
        unit="m2",
        metric_crs=str(metric_crs),
        source_layers=("perimeter",),
        contributing_feature_ids=contributing_feature_ids,
        parameters={"metric_crs": str(metric_crs)},
    )
