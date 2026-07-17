import uuid

from pydantic import BaseModel, Field

from app.domain.analysis.result import IndicatorCalculation


class AnalyzeRequest(BaseModel):
    themes: list[str] = Field(min_length=1)


class WarningOut(BaseModel):
    code: str
    message: str
    feature_ids: list[uuid.UUID]
    severity: str


class IndicatorResultOut(BaseModel):
    indicator_code: str
    theme: str
    formula_version: str
    value: float | int | str | dict[str, object] | None
    unit: str
    metric_crs: str | None
    parameters: dict[str, object]
    source_layers: list[str]
    contributing_feature_ids: list[uuid.UUID]
    warnings: list[WarningOut]


def indicator_result_to_out(calculation: IndicatorCalculation) -> IndicatorResultOut:
    return IndicatorResultOut(
        indicator_code=calculation.indicator_code,
        theme=calculation.theme,
        formula_version=calculation.formula_version,
        value=calculation.raw_value,
        unit=calculation.unit,
        metric_crs=calculation.metric_crs,
        parameters=calculation.parameters,
        source_layers=list(calculation.source_layers),
        contributing_feature_ids=list(calculation.contributing_feature_ids),
        warnings=[
            WarningOut(
                code=warning.code,
                message=warning.message,
                feature_ids=list(warning.feature_ids),
                severity=warning.severity.value,
            )
            for warning in calculation.warnings
        ],
    )


class AnalyzeResponse(BaseModel):
    analysis_run_id: uuid.UUID
    status: str
    results: list[IndicatorResultOut]
