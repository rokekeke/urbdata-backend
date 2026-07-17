import math
import warnings
from dataclasses import dataclass
from uuid import UUID

from geopandas import GeoDataFrame
from shapely.geometry.base import BaseGeometry

from app.domain.analysis.exceptions import InvalidGeometryError
from app.domain.analysis.warnings import AnalysisWarning, WarningSeverity
from app.domain.geospatial.crs import require_metric_crs

# Relative divergence between geometric and reference area that is worth
# flagging as a warning. Below this, small digitizing/rounding differences
# are expected and not reported (Obsidian note 11, confirmed 5%).
AREA_DIVERGENCE_THRESHOLD = 0.05


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


def dissolve_by_group(
    gdf: GeoDataFrame, *, group_column: str
) -> dict[str, tuple[BaseGeometry, tuple[UUID, ...], tuple[UUID, ...]]]:
    """Group *gdf* by *group_column* and `dissolve()` each group separately
    (ADR 009 - e.g. lots sharing the same `quadra_id` dissolve into that
    quadra's outline).

    Rows where *group_column* is null are excluded entirely, not put in
    their own group - pandas' `groupby` drops null keys by default, which
    is exactly the right behavior here: a lot without a `quadra_id` doesn't
    belong to any quadra. A group where every row is invalid/empty is
    skipped rather than raising, so one bad group doesn't fail every other
    group's result.
    """
    results: dict[str, tuple[BaseGeometry, tuple[UUID, ...], tuple[UUID, ...]]] = {}
    for group_value, group_gdf in gdf.groupby(group_column):
        try:
            results[str(group_value)] = dissolve(group_gdf)
        except InvalidGeometryError:
            continue
    return results


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


@dataclass(frozen=True, slots=True)
class ResolvedArea:
    area_m2: float
    warning: AnalysisWarning | None


def resolve_feature_area(
    feature_id: UUID,
    geometry: BaseGeometry,
    reference_area_m2: float | None,
    *,
    crs: str | int,
    divergence_threshold: float = AREA_DIVERGENCE_THRESHOLD,
) -> ResolvedArea:
    """Pick the area to use for one feature (Obsidian note 11).

    The geometric area is always computed, for traceability and as the
    fallback when no reference is supplied. When *reference_area_m2* is
    present, it is the value actually used (it is assumed pre-verified
    outside the platform); the geometric area only serves as a check
    against it. A relative divergence at or above *divergence_threshold*
    produces a warning - below that, small digitizing/rounding differences
    are expected and not reported.

    A NaN *reference_area_m2* (as a pandas/GeoDataFrame column commonly
    represents a missing float rather than `None`) is treated the same as
    a missing reference, so callers reading straight from a GeoDataFrame
    row don't each need their own NaN-cleaning step.
    """
    geometric = area_m2(geometry, crs=crs)
    if reference_area_m2 is None or math.isnan(reference_area_m2):
        return ResolvedArea(area_m2=geometric, warning=None)

    divergence = (
        abs(geometric - reference_area_m2) / reference_area_m2 if reference_area_m2 else 1.0
    )
    warning = None
    if divergence >= divergence_threshold:
        warning = AnalysisWarning(
            code="area_reference_divergence",
            message=(
                f"Area geometrica ({geometric:.2f} m2) diverge "
                f"{divergence:.1%} da area de referencia ({reference_area_m2:.2f} m2)."
            ),
            feature_ids=(feature_id,),
            severity=WarningSeverity.WARNING,
        )
    return ResolvedArea(area_m2=reference_area_m2, warning=warning)
