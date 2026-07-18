"""Lot-level indicators (Epico 8): frontage against the road footprint and
parceling efficiency relative to each derived quadra (ADR 009).

The lot<->quadra relation itself needs no extra indicator here: quadras are
dissolved directly from lots sharing a `quadra_id` (ADR 009), so the
relation exists by construction, not by a spatial join computed in this
module.
"""

from dataclasses import dataclass
from uuid import UUID

from shapely.geometry.base import BaseGeometry

from app.config.macroarea_mapping import Macroarea
from app.domain.analysis.exceptions import InvalidGeometryError
from app.domain.analysis.result import IndicatorCalculation
from app.domain.analysis.warnings import AnalysisWarning, WarningSeverity
from app.domain.geospatial.context import GeospatialContext
from app.domain.geospatial.geometry import area_m2, dissolve, resolve_feature_area
from app.domain.indicators.quadras import quadras_from_context

TERRITORIO_LAYER = "territorio"
LOT_MACROAREA = Macroarea.LOTE.value
ROAD_MACROAREA = Macroarea.SISTEMA_VIARIO.value

# The only tolerance value ever associated with lot frontage in this
# project's domain notes (Obsidian note 07) - reused as the MVP default
# rather than inventing a new one. Closes a small digitizing gap between a
# lot's boundary and the road footprint polygon it faces.
FRONTAGE_TOLERANCE_M = 3.0


@dataclass(frozen=True, slots=True)
class LotFrontageRecord:
    feature_id: UUID
    frontage_m: float


def _frontage_length_m(boundary: BaseGeometry, road_buffer: BaseGeometry) -> float:
    overlap = boundary.intersection(road_buffer)
    if overlap.is_empty:
        return 0.0
    if hasattr(overlap, "geoms"):
        return float(sum(part.length for part in overlap.geoms if part.length > 0))
    return float(overlap.length)


def calculate_lot_frontage_from_context(context: GeospatialContext) -> IndicatorCalculation:
    """Epico 8: length of each lot's boundary that faces the road footprint
    (`sistema_viario` polygon already in the `territorio` layer - reuses
    what ADR 008 already loads, no dependency on the road-network graph
    from Epico 9). A lot that does not touch any road within the tolerance
    gets `0.0`, a legitimate value for an interior lot, not a warning."""
    gdf = context.metric_gdf(TERRITORIO_LAYER)
    lots = gdf[gdf["macroarea"] == LOT_MACROAREA]
    roads = gdf[gdf["macroarea"] == ROAD_MACROAREA]

    warnings: list[AnalysisWarning] = []
    frontage: dict[str, float] = {}
    contributing: list[UUID] = []

    road_buffer: BaseGeometry | None
    if roads.empty:
        warnings.append(
            AnalysisWarning(
                code="no_road_footprint_for_frontage",
                message=(
                    "Nenhuma feicao de sistema viario foi encontrada; "
                    "testada nao pode ser calculada."
                ),
                feature_ids=tuple(lots["feature_id"]),
                severity=WarningSeverity.INFO,
            )
        )
        road_buffer = None
    else:
        try:
            road_geometry, _, _ = dissolve(roads)
            road_buffer = road_geometry.buffer(FRONTAGE_TOLERANCE_M)
        except InvalidGeometryError:
            warnings.append(
                AnalysisWarning(
                    code="no_road_footprint_for_frontage",
                    message=(
                        "As feicoes de sistema viario nao possuem geometria valida; "
                        "testada nao pode ser calculada."
                    ),
                    feature_ids=tuple(lots["feature_id"]),
                    severity=WarningSeverity.INFO,
                )
            )
            road_buffer = None

    for row in lots.itertuples(index=False):
        feature_id: UUID = row.feature_id
        geometry: BaseGeometry = row.geometry
        if geometry is None or geometry.is_empty or not geometry.is_valid:
            warnings.append(
                AnalysisWarning(
                    code="invalid_lot_geometry",
                    message="Um lote possui geometria invalida ou vazia e foi ignorado.",
                    feature_ids=(feature_id,),
                )
            )
            continue
        value = (
            _frontage_length_m(geometry.boundary, road_buffer) if road_buffer is not None else 0.0
        )
        frontage[str(feature_id)] = value
        contributing.append(feature_id)

    return IndicatorCalculation(
        indicator_code="lots.frontage_length",
        theme="lots",
        formula_version="1.0.0",
        raw_value=frontage,
        unit="m",
        metric_crs=str(context.metric_crs_value()),
        source_layers=(TERRITORIO_LAYER,),
        contributing_feature_ids=tuple(contributing),
        parameters={
            "metric_crs": str(context.metric_crs_value()),
            "frontage_tolerance_m": FRONTAGE_TOLERANCE_M,
        },
        warnings=tuple(warnings),
    )


def calculate_parceling_efficiency_from_context(context: GeospatialContext) -> IndicatorCalculation:
    """Epico 8: gross lot area / quadra area, per quadra. "Area util" is the
    gross resolved lot area (no parcelavel or land-use filter) - confirmed
    2026-07-17. Reuses the same quadra grouping as the `quadras` theme
    (`quadras_from_context`) instead of dissolving lots by `quadra_id` a
    second time."""
    gdf = context.metric_gdf(TERRITORIO_LAYER)
    lots = gdf[gdf["macroarea"] == LOT_MACROAREA].set_index("feature_id")
    quadras, quadra_warnings = quadras_from_context(context)

    warnings = list(quadra_warnings)
    efficiency: dict[str, float] = {}
    contributing: list[UUID] = []
    metric_crs = context.metric_crs_value()
    for quadra in quadras:
        quadra_area = area_m2(quadra.geometry, crs=metric_crs)
        lot_area = 0.0
        for feature_id in quadra.lot_feature_ids:
            row = lots.loc[feature_id]
            # Same resolution rule as every other area-consuming indicator
            # (territorial, land_use, green_areas, density): reference_area_m2
            # wins when present and valid (see resolve_feature_area's
            # invariant docstring) - lots are not exempt from that rule.
            resolved = resolve_feature_area(
                feature_id, row["geometry"], row["reference_area_m2"], crs=metric_crs
            )
            if resolved.warning is not None:
                warnings.append(resolved.warning)
            lot_area += resolved.area_m2
        efficiency[quadra.quadra_id] = lot_area / quadra_area if quadra_area else 0.0
        contributing.extend(quadra.lot_feature_ids)

    return IndicatorCalculation(
        indicator_code="lots.parceling_efficiency",
        theme="lots",
        formula_version="1.0.0",
        raw_value=efficiency,
        unit="ratio",
        metric_crs=str(metric_crs),
        source_layers=(TERRITORIO_LAYER,),
        contributing_feature_ids=tuple(contributing),
        parameters={
            "metric_crs": str(metric_crs),
            "numerador": "area_bruta_dos_lotes",
            "denominador": "area_da_quadra",
        },
        warnings=tuple(warnings),
    )
