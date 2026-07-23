"""Maximum lot buildability from the minimum approved input: lot area x CA."""

import math
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from shapely.geometry.base import BaseGeometry

from app.config.land_use_mapping import LandUseCategory
from app.config.macroarea_mapping import Macroarea
from app.domain.analysis.exceptions import IndicatorCalculationError, InvalidGeometryError
from app.domain.analysis.result import IndicatorCalculation
from app.domain.analysis.warnings import AnalysisWarning, WarningSeverity
from app.domain.geospatial.context import GeospatialContext
from app.domain.geospatial.geometry import AREA_DIVERGENCE_THRESHOLD, resolve_feature_area
from app.domain.indicators.land_use import classify_land_use
from app.domain.indicators.territorial import calculate_territorial_area_by_category_from_context

TERRITORIO_LAYER = "territorio"
LOT_MACROAREA = "lote"


@dataclass(frozen=True, slots=True)
class LotBuildabilityRecord:
    feature_id: UUID
    lot_area_m2: float
    ca_max: float | None

    @property
    def max_computable_area_m2(self) -> float | None:
        if self.ca_max is None:
            return None
        return self.lot_area_m2 * self.ca_max


def _optional_nonnegative_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(parsed) or parsed < 0:
        return None
    return parsed


def _build_lot_records(
    context: GeospatialContext,
) -> tuple[tuple[LotBuildabilityRecord, ...], tuple[AnalysisWarning, ...]]:
    lots = context.metric_gdf(TERRITORIO_LAYER)
    lots = lots[lots["macroarea"] == LOT_MACROAREA]
    records: list[LotBuildabilityRecord] = []
    warnings: list[AnalysisWarning] = []
    missing_ca_ids: list[UUID] = []

    for row in lots.itertuples(index=False):
        feature_id: UUID = row.feature_id
        geometry: BaseGeometry = row.geometry
        reference_area = _optional_nonnegative_float(row.reference_area_m2)
        try:
            resolved_area = resolve_feature_area(
                feature_id,
                geometry,
                reference_area,
                crs=context.metric_crs_value(),
            )
        except InvalidGeometryError:
            warnings.append(
                AnalysisWarning(
                    code="invalid_lot_geometry",
                    message="Um lote possui geometria invalida ou vazia e foi ignorado.",
                    feature_ids=(feature_id,),
                )
            )
            continue
        if resolved_area.warning is not None:
            warnings.append(resolved_area.warning)

        ca_max = _optional_nonnegative_float(row.ca_max)
        if ca_max is None:
            missing_ca_ids.append(feature_id)
        records.append(
            LotBuildabilityRecord(
                feature_id=feature_id,
                lot_area_m2=resolved_area.area_m2,
                ca_max=ca_max,
            )
        )

    if not records:
        raise IndicatorCalculationError(
            "No valid lot geometry is available for maximum buildability calculations."
        )
    if missing_ca_ids:
        warnings.append(
            AnalysisWarning(
                code="lot_ca_missing",
                message="Um ou mais lotes nao possuem CA maximo valido e ficaram sem calculo.",
                feature_ids=tuple(missing_ca_ids),
                severity=WarningSeverity.INFO,
            )
        )
    return tuple(records), tuple(warnings)


def _lot_records_from_context(
    context: GeospatialContext,
) -> tuple[tuple[LotBuildabilityRecord, ...], tuple[AnalysisWarning, ...]]:
    return context.cached("density:lot_buildability_records", lambda: _build_lot_records(context))


def _calculated_records(
    records: tuple[LotBuildabilityRecord, ...],
) -> tuple[LotBuildabilityRecord, ...]:
    return tuple(record for record in records if record.ca_max is not None)


def _result(
    context: GeospatialContext,
    *,
    code: str,
    value: float | int,
    unit: str,
    records: tuple[LotBuildabilityRecord, ...],
    warnings: tuple[AnalysisWarning, ...],
) -> IndicatorCalculation:
    calculated = _calculated_records(records)
    return IndicatorCalculation(
        indicator_code=code,
        theme="density",
        formula_version="1.0.0",
        raw_value=value,
        unit=unit,
        metric_crs=str(context.metric_crs_value()),
        source_layers=(TERRITORIO_LAYER,),
        contributing_feature_ids=tuple(record.feature_id for record in calculated),
        parameters={
            "area_reference_divergence_threshold": AREA_DIVERGENCE_THRESHOLD,
            "formula": "lot_area_m2 * ca_max",
        },
        warnings=warnings,
    )


def calculate_max_computable_area_from_context(
    context: GeospatialContext,
) -> IndicatorCalculation:
    records, warnings = _lot_records_from_context(context)
    total = sum(
        value
        for record in records
        if (value := record.max_computable_area_m2) is not None
    )
    return _result(
        context,
        code="density.max_computable_area",
        value=total,
        unit="m2",
        records=records,
        warnings=warnings,
    )


def calculate_lot_count_with_ca_from_context(
    context: GeospatialContext,
) -> IndicatorCalculation:
    records, warnings = _lot_records_from_context(context)
    return _result(
        context,
        code="density.lot_count_with_ca",
        value=len(_calculated_records(records)),
        unit="count",
        records=records,
        warnings=warnings,
    )


def calculate_ca_coverage_from_context(context: GeospatialContext) -> IndicatorCalculation:
    records, warnings = _lot_records_from_context(context)
    total_lot_area = sum(record.lot_area_m2 for record in records)
    covered_lot_area = sum(
        record.lot_area_m2 for record in records if record.ca_max is not None
    )
    coverage = covered_lot_area / total_lot_area if total_lot_area else 0.0
    return _result(
        context,
        code="density.ca_coverage",
        value=coverage,
        unit="ratio",
        records=records,
        warnings=warnings,
    )


def calculate_built_open_ratio_from_context(context: GeospatialContext) -> IndicatorCalculation:
    """AQUA-HQE "Densidade": relacao espaco construido / espaco aberto.

    Numerador: potencial construtivo maximo, mesma logica de
    `calculate_max_computable_area_from_context` (area do lote x CA
    maximo, area resolvida). Denominador: area do territorio que NAO e
    macroarea Lote (sistema viario, AVL, APP, ACI, Nulo), reaproveitando
    `territorial.calculate_territorial_area_by_category_from_context`
    (BT-043, inventario completo, sem filtro de parcelavel).

    Interpretacao assumida, a confirmar com o urbanista (nota Obsidian 90,
    item 1): "espaco construido" e o potencial de area de piso (CA x area
    do lote), nao a area de implantacao/footprint (que o motor nao le
    hoje); "espaco aberto" e todo o territorio que nao e Lote, nao so
    area verde - leitura mais ampla do termo na literatura HQE/AQUA,
    distinta dos indicadores `green_areas.*` (especificamente AVL/APP).

    Mesmo padrao de `green_areas.calculate_green_area_percent_from_context`:
    chama a funcao pura de outro modulo diretamente dentro da mesma
    execucao (ADR 004 - nunca le o valor persistido de um indicador
    irmao, so pode chamar a mesma funcao de novo).
    """
    built_result = calculate_max_computable_area_from_context(context)
    built_area_m2 = built_result.raw_value
    assert isinstance(built_area_m2, float)  # calculate_max_computable_area's contract

    breakdown_result = calculate_territorial_area_by_category_from_context(context)
    breakdown = breakdown_result.raw_value
    assert isinstance(breakdown, dict)  # calculate_territorial_area_by_category's contract
    open_space_area_m2: float = sum(
        float(area) for category, area in breakdown.items() if category != Macroarea.LOTE.value
    )

    if open_space_area_m2 <= 0:
        raise IndicatorCalculationError(
            "A positive non-Lote (open-space) area is required to compute "
            "the built/open ratio."
        )

    return IndicatorCalculation(
        indicator_code="density.built_open_ratio",
        theme="density",
        formula_version="1.0.0",
        raw_value=built_area_m2 / open_space_area_m2,
        unit="ratio",
        metric_crs=str(context.metric_crs_value()),
        source_layers=(TERRITORIO_LAYER,),
        contributing_feature_ids=tuple(
            set(built_result.contributing_feature_ids)
            | set(breakdown_result.contributing_feature_ids)
        ),
        parameters={
            "formula": "max_computable_area_m2 / (territorio_total_m2 - lote_m2)",
            "numerator": "density.max_computable_area",
            "denominator": "territorial.area_by_category (todas as categorias exceto Lote)",
        },
        warnings=built_result.warnings + breakdown_result.warnings,
    )


NON_RESIDENTIAL_LAND_USE_CATEGORIES: frozenset[LandUseCategory] = frozenset(
    {
        LandUseCategory.COMERCIAL,
        LandUseCategory.SERVICOS,
        LandUseCategory.INSTITUCIONAL,
        LandUseCategory.INDUSTRIAL,
    }
)


@dataclass(frozen=True, slots=True)
class _NonResidentialLotRecord:
    feature_id: UUID
    lot_area_m2: float
    ca_max: float | None

    @property
    def built_area_m2(self) -> float | None:
        if self.ca_max is None:
            return None
        return self.lot_area_m2 * self.ca_max


def _non_residential_lot_records_from_context(
    context: GeospatialContext,
) -> tuple[tuple[_NonResidentialLotRecord, ...], tuple[AnalysisWarning, ...]]:
    """Lote features whose land use resolves to a non-residential category
    (comercial, servicos, institucional, industrial -
    NON_RESIDENTIAL_LAND_USE_CATEGORIES). Residencial is excluded by
    definition; Misto is also excluded - a mixed-use lot has a residential
    component, so it would misrepresent "non residential" either way it
    were counted (same spirit as `land_use.classify_land_use`'s own rule:
    a lot with more than one recognized use is always Misto, never
    silently folded into a single-use category).
    """
    gdf = context.metric_gdf(TERRITORIO_LAYER)
    metric_crs = context.metric_crs_value()
    records: list[_NonResidentialLotRecord] = []
    warnings: list[AnalysisWarning] = []
    for row in gdf.itertuples():
        if row.macroarea != LOT_MACROAREA:
            continue
        if classify_land_use(row.land_use) not in NON_RESIDENTIAL_LAND_USE_CATEGORIES:
            continue
        resolved = resolve_feature_area(
            row.feature_id, row.geometry, row.reference_area_m2, crs=metric_crs
        )
        if resolved.warning is not None:
            warnings.append(resolved.warning)
        records.append(
            _NonResidentialLotRecord(
                feature_id=row.feature_id,
                lot_area_m2=resolved.area_m2,
                ca_max=_optional_nonnegative_float(row.ca_max),
            )
        )
    return tuple(records), tuple(warnings)


def calculate_non_residential_ca_from_context(context: GeospatialContext) -> IndicatorCalculation:
    """LEED-ND "Densidades": CA (area construida / area disponivel)
    restrito aos lotes de uso nao residencial (comercial, servicos,
    institucional, industrial).

    O lado residencial do mesmo credito (UH/hectare) fica de fora - precisa
    de contagem de unidades habitacionais, ainda nao implementada (ver nota
    Obsidian 79, `density.estimated_units`).

    Formula: soma(area_do_lote x CA) / soma(area_do_lote), restrita aos
    lotes nao residenciais com CA valido em ambos os lados da razao - mesmo
    criterio de "calculado" que `calculate_max_computable_area_from_context`
    ja usa (lote sem CA gera aviso INFO, nao entra na conta).

    Zero lotes nao residenciais no projeto e um universo qualificante vazio
    legitimo (um loteamento 100% residencial e um projeto valido, nao um
    erro estrutural) - degrada para None + aviso, em vez de falhar (mesmo
    espirito de ADR 013 / `territorial.percent_by_category`'s
    no_parcelavel_area) - diferente do "sem area aberta" de
    `calculate_built_open_ratio_from_context`, que e estruturalmente quase
    impossivel (sistema viario sempre existe).
    """
    records, warnings = _non_residential_lot_records_from_context(context)

    missing_ca_ids = tuple(record.feature_id for record in records if record.ca_max is None)
    if missing_ca_ids:
        warnings = (
            *warnings,
            AnalysisWarning(
                code="lot_ca_missing",
                message=(
                    "Um ou mais lotes nao residenciais nao possuem CA "
                    "maximo valido e ficaram fora do calculo."
                ),
                feature_ids=missing_ca_ids,
                severity=WarningSeverity.INFO,
            ),
        )

    parameters = {
        "formula": "sum(lot_area_m2 * ca_max) / sum(lot_area_m2)",
        "land_use_filter": sorted(c.value for c in NON_RESIDENTIAL_LAND_USE_CATEGORIES),
    }

    calculated = [record for record in records if record.ca_max is not None]
    if not calculated:
        return IndicatorCalculation(
            indicator_code="density.non_residential_ca",
            theme="density",
            formula_version="1.0.0",
            raw_value=None,
            unit="ratio",
            metric_crs=str(context.metric_crs_value()),
            source_layers=(TERRITORIO_LAYER,),
            contributing_feature_ids=(),
            parameters=parameters,
            warnings=(
                *warnings,
                AnalysisWarning(
                    code="no_non_residential_lot",
                    message=(
                        "Nenhum lote de uso nao residencial com CA valido; "
                        "a razao nao pode ser calculada."
                    ),
                    severity=WarningSeverity.WARNING,
                ),
            ),
        )

    total_area = sum(record.lot_area_m2 for record in calculated)
    total_built = sum(
        value for record in calculated if (value := record.built_area_m2) is not None
    )

    return IndicatorCalculation(
        indicator_code="density.non_residential_ca",
        theme="density",
        formula_version="1.0.0",
        raw_value=total_built / total_area,
        unit="ratio",
        metric_crs=str(context.metric_crs_value()),
        source_layers=(TERRITORIO_LAYER,),
        contributing_feature_ids=tuple(record.feature_id for record in calculated),
        parameters=parameters,
        warnings=warnings,
    )
