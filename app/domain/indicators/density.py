"""Maximum lot buildability from the minimum approved input: lot area x CA."""

import math
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from shapely.geometry.base import BaseGeometry

from app.domain.analysis.exceptions import IndicatorCalculationError, InvalidGeometryError
from app.domain.analysis.result import IndicatorCalculation
from app.domain.analysis.warnings import AnalysisWarning, WarningSeverity
from app.domain.geospatial.context import GeospatialContext
from app.domain.geospatial.geometry import AREA_DIVERGENCE_THRESHOLD, resolve_feature_area

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
            "area_source": "imported_geometry",
            "area_reference_divergence_threshold": AREA_DIVERGENCE_THRESHOLD,
            "formula": "lot_geometry_area_m2 * ca_max",
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
