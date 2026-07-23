"""Lot-level indicators (Epico 8): frontage against the road footprint and
parceling efficiency relative to each derived quadra (ADR 009).

The lot<->quadra relation itself needs no extra indicator here: quadras are
dissolved directly from lots sharing a `quadra_id` (ADR 009), so the
relation exists by construction, not by a spatial join computed in this
module.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from geopandas import GeoDataFrame
from shapely.geometry import Point
from shapely.geometry.base import BaseGeometry

from app.config.land_use_mapping import LandUseCategory
from app.config.macroarea_mapping import Macroarea
from app.domain.analysis.exceptions import InvalidGeometryError
from app.domain.analysis.result import IndicatorCalculation
from app.domain.analysis.warnings import AnalysisWarning, WarningSeverity
from app.domain.geospatial.context import GeospatialContext
from app.domain.geospatial.geometry import area_m2, dissolve, resolve_feature_area
from app.domain.geospatial.networks import (
    NetworkTargets,
    build_node_index,
    distance_to_nearest_target,
    snap_targets,
)
from app.domain.indicators.land_use import classify_land_use
from app.domain.indicators.quadras import quadras_from_context
from app.domain.indicators.roads import ROAD_LAYER as ROAD_CENTERLINE_LAYER
from app.domain.indicators.roads import UNLINK_LAYER as ROAD_UNLINK_LAYER
from app.domain.indicators.roads import road_network_from_context

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


@dataclass(frozen=True, slots=True)
class FrontageGeometry:
    length_m: float
    midpoint: Point | None


def _frontage_geometry(
    boundary: BaseGeometry, road_buffer: BaseGeometry | None
) -> FrontageGeometry:
    """Shared by `lots.frontage_length` (needs only `.length_m`) and the
    network-distance indicators below (need `.midpoint` too - the
    street-facing reference point for a lot, reusing this exact frontage
    detection instead of a bare centroid, which can sit far from real
    street access on an irregular or corner lot; parecer confirmado,
    nota Obsidian 90 item 5).

    `midpoint` is the middle of the longest contiguous frontage segment
    when a lot's boundary overlaps the road buffer in more than one place
    (`.geoms`); `None` whenever there is no frontage to speak of - no road
    layer, no overlap, or a tangent touch with zero-length overlap (a
    `Point` intersection has no `.interpolate()` to call).
    """
    if road_buffer is None:
        return FrontageGeometry(length_m=0.0, midpoint=None)
    overlap = boundary.intersection(road_buffer)
    if overlap.is_empty:
        return FrontageGeometry(length_m=0.0, midpoint=None)
    if hasattr(overlap, "geoms"):
        parts = [part for part in overlap.geoms if part.length > 0]
        if not parts:
            return FrontageGeometry(length_m=0.0, midpoint=None)
        longest = max(parts, key=lambda part: part.length)
        total_length = sum(part.length for part in parts)
        return FrontageGeometry(
            length_m=float(total_length), midpoint=longest.interpolate(0.5, normalized=True)
        )
    if overlap.length <= 0:
        return FrontageGeometry(length_m=0.0, midpoint=None)
    return FrontageGeometry(
        length_m=float(overlap.length), midpoint=overlap.interpolate(0.5, normalized=True)
    )


def _road_buffer_or_warning(
    roads: GeoDataFrame, lot_ids: Sequence[UUID]
) -> tuple[BaseGeometry | None, AnalysisWarning | None]:
    """Dissolve and buffer the sistema_viario footprint once, or explain
    why there isn't one to use - shared by `lots.frontage_length` and the
    network-distance indicators below, all of which need the same road
    buffer to find where a lot (or a green area) touches the street."""
    if roads.empty:
        return None, AnalysisWarning(
            code="no_road_footprint_for_frontage",
            message=(
                "Nenhuma feicao de sistema viario foi encontrada; "
                "testada nao pode ser calculada."
            ),
            feature_ids=tuple(lot_ids),
            severity=WarningSeverity.INFO,
        )
    try:
        road_geometry, _, _ = dissolve(roads)
    except InvalidGeometryError:
        return None, AnalysisWarning(
            code="no_road_footprint_for_frontage",
            message=(
                "As feicoes de sistema viario nao possuem geometria valida; "
                "testada nao pode ser calculada."
            ),
            feature_ids=tuple(lot_ids),
            severity=WarningSeverity.INFO,
        )
    return road_geometry.buffer(FRONTAGE_TOLERANCE_M), None


def calculate_lot_frontage_from_context(context: GeospatialContext) -> IndicatorCalculation:
    """Epico 8: length of each lot's boundary that faces the road footprint
    (`sistema_viario` polygon already in the `territorio` layer - reuses
    what ADR 008 already loads, no dependency on the road-network graph
    from Epico 9). A lot that does not touch any road within the tolerance
    gets `0.0`, a legitimate value for an interior lot, not a warning."""
    gdf = context.metric_gdf(TERRITORIO_LAYER)
    lots = gdf[gdf["macroarea"] == LOT_MACROAREA]
    roads = gdf[gdf["macroarea"] == ROAD_MACROAREA]

    road_buffer, buffer_warning = _road_buffer_or_warning(roads, tuple(lots["feature_id"]))
    warnings: list[AnalysisWarning] = [buffer_warning] if buffer_warning is not None else []
    frontage: dict[str, float] = {}
    contributing: list[UUID] = []

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
        frontage[str(feature_id)] = _frontage_geometry(geometry.boundary, road_buffer).length_m
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


@dataclass(frozen=True, slots=True)
class ReferencedLot:
    feature_id: UUID
    category: LandUseCategory | None
    point: Point | None


def _referenced_lots(
    context: GeospatialContext,
) -> tuple[tuple[ReferencedLot, ...], BaseGeometry | None, tuple[AnalysisWarning, ...]]:
    """Every Lote feature with its land-use category and its frontage
    midpoint (the same street-facing reference point `lots.frontage_length`
    already identifies) - shared basis for the network-distance indicators
    below. Also returns the dissolved+buffered road footprint, reused to
    find each green area's own frontage."""
    gdf = context.metric_gdf(TERRITORIO_LAYER)
    lots = gdf[gdf["macroarea"] == LOT_MACROAREA]
    roads = gdf[gdf["macroarea"] == ROAD_MACROAREA]

    road_buffer, buffer_warning = _road_buffer_or_warning(roads, tuple(lots["feature_id"]))
    warnings: list[AnalysisWarning] = [buffer_warning] if buffer_warning is not None else []

    referenced: list[ReferencedLot] = []
    no_frontage_ids: list[UUID] = []
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
        frontage = _frontage_geometry(geometry.boundary, road_buffer)
        category = classify_land_use(row.land_use)
        if frontage.midpoint is None:
            no_frontage_ids.append(feature_id)
        referenced.append(
            ReferencedLot(feature_id=feature_id, category=category, point=frontage.midpoint)
        )

    if no_frontage_ids:
        warnings.append(
            AnalysisWarning(
                code="lot_without_street_frontage",
                message=(
                    "Um ou mais lotes nao tocam nenhuma via e ficaram fora do "
                    "calculo de distancia caminhavel."
                ),
                feature_ids=tuple(no_frontage_ids),
                severity=WarningSeverity.INFO,
            )
        )

    return tuple(referenced), road_buffer, tuple(warnings)


def _green_area_reference_points(
    gdf: GeoDataFrame, road_buffer: BaseGeometry | None
) -> tuple[tuple[Point, ...], tuple[UUID, ...]]:
    """Frontage midpoint of each AVL (Area Verde de Lazer) feature, same
    convention as lots - excludes any green area that does not reach a
    road (no meaningful "entrance" to measure walking distance to)."""
    green_areas = gdf[gdf["macroarea"] == Macroarea.AVL.value]
    points: list[Point] = []
    contributing: list[UUID] = []
    for row in green_areas.itertuples(index=False):
        geometry: BaseGeometry = row.geometry
        if geometry is None or geometry.is_empty or not geometry.is_valid:
            continue
        frontage = _frontage_geometry(geometry.boundary, road_buffer)
        if frontage.midpoint is not None:
            points.append(frontage.midpoint)
            contributing.append(row.feature_id)
    return tuple(points), tuple(contributing)


_QUERY_CATEGORIES = frozenset({LandUseCategory.RESIDENCIAL, LandUseCategory.MISTO})


def _query_lots(referenced: Sequence[ReferencedLot]) -> list[ReferencedLot]:
    """Residencial and Misto lots with a usable frontage midpoint -
    "unidades residenciais", the side every certification credit measures
    access from (parecer confirmado, nota Obsidian 90 item 5)."""
    return [
        lot for lot in referenced if lot.point is not None and lot.category in _QUERY_CATEGORIES
    ]


def _network_distance_source_layers(context: GeospatialContext) -> tuple[str, ...]:
    layers: tuple[str, ...] = (TERRITORIO_LAYER, ROAD_CENTERLINE_LAYER)
    if ROAD_UNLINK_LAYER in context.layers:
        layers = (*layers, ROAD_UNLINK_LAYER)
    return layers


def _network_distance_result(
    context: GeospatialContext,
    *,
    code: str,
    query_lots: Sequence[ReferencedLot],
    target_points: Sequence[Point],
    target_ids: Sequence[UUID],
    no_target_warning_code: str,
    no_target_message: str,
    base_warnings: tuple[AnalysisWarning, ...],
    extra_parameters: dict[str, str],
) -> IndicatorCalculation:
    """Shared result assembly for both network-distance indicators - only
    the target set and a couple of descriptive parameters differ between
    them. Snaps every query lot's reference point once against a shared
    `NetworkNodeIndex` and the pre-snapped target set (`snap_targets`),
    rather than re-snapping the same targets for every query lot - except
    for a query lot that is *also* one of the targets (a Misto lot counts
    as both `lots.distance_to_non_residential_use`'s query and target set,
    per the confirmed domain decision), which gets its own point excluded
    from its own target search: a lot must never report "distance to
    itself"."""
    network = road_network_from_context(context)
    index = build_node_index(network)

    distances: dict[str, float | None] = {}
    contributing: list[UUID] = [lot.feature_id for lot in query_lots]
    warnings = base_warnings

    if not target_points:
        for lot in query_lots:
            distances[str(lot.feature_id)] = None
        warnings = (
            *warnings,
            AnalysisWarning(
                code=no_target_warning_code,
                message=no_target_message,
                severity=WarningSeverity.WARNING,
            ),
        )
    else:
        targets = snap_targets(index, target_points)
        contributing.extend(target_ids)
        target_id_set = set(target_ids)
        for lot in query_lots:
            assert lot.point is not None  # _query_lots already filtered this
            lot_targets = targets
            if lot.feature_id in target_id_set:
                other_points = [
                    point
                    for point, target_id in zip(target_points, target_ids, strict=True)
                    if target_id != lot.feature_id
                ]
                lot_targets = (
                    snap_targets(index, other_points)
                    if other_points
                    else NetworkTargets(node_last_mile_m={})
                )
            distances[str(lot.feature_id)] = distance_to_nearest_target(
                network, index, lot.point, lot_targets
            )

    return IndicatorCalculation(
        indicator_code=code,
        theme="lots",
        formula_version="1.0.0",
        raw_value=distances,
        unit="m",
        metric_crs=str(context.metric_crs_value()),
        source_layers=_network_distance_source_layers(context),
        contributing_feature_ids=tuple(contributing),
        parameters={
            "metric_crs": str(context.metric_crs_value()),
            "ponto_referencia": "ponto medio da testada (mesma deteccao de lots.frontage_length)",
            "consulta": "lotes residenciais e mistos",
            "metodo": "distancia de rede (Dijkstra) sobre o grafo viario, nao linha reta",
            **extra_parameters,
        },
        warnings=warnings,
    )


def calculate_distance_to_non_residential_use_from_context(
    context: GeospatialContext,
) -> IndicatorCalculation:
    """Distancia de rede (nao em linha reta), por lote residencial/misto,
    ate o lote de uso nao residencial mais proximo caminhando pela malha
    viaria - insumo para os creditos de "diversidade de usos a X metros
    caminhaveis" citados por FC/AQ/ND/LFC (nota Obsidian 89).

    Decisoes de dominio confirmadas com o urbanista antes de implementar
    (nota Obsidian 90, item 5):
    - Ponto de referencia: ponto medio da testada (mesma deteccao de
      frente que `lots.frontage_length` ja usa, nao o centroide) -
      aplicado tanto ao lote de consulta quanto ao lote-alvo.
    - Consulta: lotes residenciais e mistos.
    - Alvo: qualquer lote classificado que nao seja puramente residencial,
      **incluindo misto** - um lote misto genuinamente oferece uso nao
      residencial, pergunta diferente da media de CA do
      `density.non_residential_ca`, que excluiu misto por outro motivo
      (aquela era sobre media ponderada; esta e sobre "esse lote oferece
      o servico").

    Guarda a distancia bruta em metros por lote, nao um sim/nao contra um
    limiar - mesmo espirito dos itens 1-4 desta leva. Lote sem testada
    (nao toca nenhuma via) fica de fora, tanto como consulta quanto como
    alvo, com aviso. Projeto sem nenhum lote-alvo valido degrada para
    `None` em todos os lotes de consulta, nao falha o calculo.
    """
    referenced, _road_buffer, warnings = _referenced_lots(context)
    query_lots = _query_lots(referenced)
    target_lots = [
        lot
        for lot in referenced
        if lot.point is not None
        and lot.category is not None
        and lot.category is not LandUseCategory.RESIDENCIAL
    ]
    target_points = [lot.point for lot in target_lots if lot.point is not None]
    target_ids = tuple(lot.feature_id for lot in target_lots)

    return _network_distance_result(
        context,
        code="lots.distance_to_non_residential_use",
        query_lots=query_lots,
        target_points=target_points,
        target_ids=target_ids,
        no_target_warning_code="no_non_residential_target",
        no_target_message=(
            "Nenhum lote de uso nao residencial com testada valida; "
            "distancia nao pode ser calculada."
        ),
        base_warnings=warnings,
        extra_parameters={
            "alvo": "lotes classificados nao puramente residenciais (inclui misto)",
        },
    )


def calculate_distance_to_green_area_from_context(
    context: GeospatialContext,
) -> IndicatorCalculation:
    """Distancia de rede, por lote residencial/misto, ate a area verde
    (AVL) mais proxima caminhando pela malha viaria - insumo para os
    creditos de acesso a espaco livre (Bucket B da nota Obsidian 86; nota
    89).

    Mesmas decisoes de ponto de referencia e conjunto de consulta do
    `lots.distance_to_non_residential_use`. Alvo: feicoes AVL (Area Verde
    de Lazer) - **sem filtro de tamanho minimo por enquanto** (decisao
    confirmada, nota Obsidian 90 item 5): guarda a distancia bruta ate a
    area verde mais proxima de qualquer tamanho; o filtro de tamanho
    (4.050m2 ou 650m2, dependendo do credito) fica para a camada de
    relatorio, nao para a formula. Usa so AVL, nao a variante com APP -
    mesma leitura "primaria" que `green_areas.total_area` (AVL-only)
    mantem como padrao; uma variante com APP seguiria o mesmo padrao
    aditivo do item 1 desta leva se for pedida depois.
    """
    referenced, road_buffer, warnings = _referenced_lots(context)
    query_lots = _query_lots(referenced)

    gdf = context.metric_gdf(TERRITORIO_LAYER)
    green_points, green_ids = _green_area_reference_points(gdf, road_buffer)

    return _network_distance_result(
        context,
        code="lots.distance_to_green_area",
        query_lots=query_lots,
        target_points=green_points,
        target_ids=green_ids,
        no_target_warning_code="no_green_area_target",
        no_target_message=(
            "Nenhuma area verde (AVL) com testada valida; distancia nao pode ser calculada."
        ),
        base_warnings=warnings,
        extra_parameters={
            "alvo": "feicoes AVL, sem filtro de tamanho minimo",
        },
    )
