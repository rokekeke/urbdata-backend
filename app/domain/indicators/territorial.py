import math
from uuid import UUID

from shapely.geometry.base import BaseGeometry

from app.domain.analysis.result import IndicatorCalculation
from app.domain.analysis.warnings import AnalysisWarning, WarningSeverity
from app.domain.geospatial.context import GeospatialContext
from app.domain.geospatial.geometry import area_m2, dissolve, length_m

PERIMETER_LAYER = "perimetro"


def _dissolve_perimeter(
    context: GeospatialContext,
) -> tuple[BaseGeometry, tuple[UUID, ...], tuple[AnalysisWarning, ...]]:
    """Shared first step for every territorial indicator: consolidate the
    perimeter layer once and report which features were skipped.
    """
    gdf = context.metric_gdf(PERIMETER_LAYER)
    geometry, contributing_ids, skipped_ids = dissolve(gdf)
    warnings = (
        (
            AnalysisWarning(
                code="perimeter_feature_skipped",
                message=(
                    "Uma ou mais feicoes do perimetro estavam vazias ou invalidas "
                    "e foram ignoradas na consolidacao."
                ),
                feature_ids=skipped_ids,
                severity=WarningSeverity.WARNING,
            ),
        )
        if skipped_ids
        else ()
    )
    return geometry, contributing_ids, warnings


def _metric_crs_value(context: GeospatialContext) -> str | int:
    epsg = context.metric_crs.to_epsg()
    return epsg if epsg is not None else context.metric_crs.to_string()


def calculate_total_area(
    geometry: BaseGeometry,
    *,
    metric_crs: str | int,
    contributing_feature_ids: tuple[UUID, ...] = (),
    warnings: tuple[AnalysisWarning, ...] = (),
) -> IndicatorCalculation:
    return IndicatorCalculation(
        indicator_code="territorial.total_area",
        theme="territorial",
        formula_version="1.0.0",
        raw_value=area_m2(geometry, crs=metric_crs),
        unit="m2",
        metric_crs=str(metric_crs),
        source_layers=(PERIMETER_LAYER,),
        contributing_feature_ids=contributing_feature_ids,
        parameters={"metric_crs": str(metric_crs)},
        warnings=warnings,
    )


def calculate_total_area_from_context(context: GeospatialContext) -> IndicatorCalculation:
    """Consolidate the perimeter layer and calculate its total area.

    This is the `IndicatorDefinition.calculator` registered for
    `territorial.total_area` (see app/domain/indicators/catalog.py): the
    orchestrator calls it with nothing but the shared `GeospatialContext`.
    """
    geometry, contributing_ids, warnings = _dissolve_perimeter(context)
    return calculate_total_area(
        geometry,
        metric_crs=_metric_crs_value(context),
        contributing_feature_ids=contributing_ids,
        warnings=warnings,
    )


def calculate_perimeter(
    geometry: BaseGeometry,
    *,
    metric_crs: str | int,
    contributing_feature_ids: tuple[UUID, ...] = (),
    warnings: tuple[AnalysisWarning, ...] = (),
) -> IndicatorCalculation:
    return IndicatorCalculation(
        indicator_code="territorial.perimeter",
        theme="territorial",
        formula_version="1.0.0",
        # A (Multi)Polygon's `.length` is the sum of its ring lengths, i.e.
        # exactly the boundary/perimeter length - no separate boundary
        # extraction is needed.
        raw_value=length_m(geometry, crs=metric_crs),
        unit="m",
        metric_crs=str(metric_crs),
        source_layers=(PERIMETER_LAYER,),
        contributing_feature_ids=contributing_feature_ids,
        parameters={"metric_crs": str(metric_crs)},
        warnings=warnings,
    )


def calculate_perimeter_from_context(context: GeospatialContext) -> IndicatorCalculation:
    """BT-041: `IndicatorDefinition.calculator` for `territorial.perimeter`."""
    geometry, contributing_ids, warnings = _dissolve_perimeter(context)
    return calculate_perimeter(
        geometry,
        metric_crs=_metric_crs_value(context),
        contributing_feature_ids=contributing_ids,
        warnings=warnings,
    )


def calculate_compactness(
    geometry: BaseGeometry,
    *,
    metric_crs: str | int,
    contributing_feature_ids: tuple[UUID, ...] = (),
    warnings: tuple[AnalysisWarning, ...] = (),
) -> IndicatorCalculation:
    """Polsby-Popper isoperimetric quotient: `4 * pi * area / perimeter^2`.

    A perfect circle scores 1.0 (maximum compactness); more elongated or
    irregular perimeters approach 0. Standard, unambiguous formula - no
    domain sign-off needed on the math itself.
    """
    area = area_m2(geometry, crs=metric_crs)
    perimeter = length_m(geometry, crs=metric_crs)
    compactness = (4 * math.pi * area) / (perimeter**2)
    return IndicatorCalculation(
        indicator_code="territorial.compactness",
        theme="territorial",
        formula_version="1.0.0",
        raw_value=compactness,
        unit="adimensional",
        metric_crs=str(metric_crs),
        source_layers=(PERIMETER_LAYER,),
        contributing_feature_ids=contributing_feature_ids,
        parameters={"metric_crs": str(metric_crs), "formula": "4*pi*area/perimeter^2"},
        warnings=warnings,
    )


def calculate_compactness_from_context(context: GeospatialContext) -> IndicatorCalculation:
    """BT-042: `IndicatorDefinition.calculator` for `territorial.compactness`."""
    geometry, contributing_ids, warnings = _dissolve_perimeter(context)
    return calculate_compactness(
        geometry,
        metric_crs=_metric_crs_value(context),
        contributing_feature_ids=contributing_ids,
        warnings=warnings,
    )
