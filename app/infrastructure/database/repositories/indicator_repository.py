"""Raw indicator-result persistence adapter."""

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.domain.analysis.result import IndicatorCalculation
from app.domain.analysis.warnings import AnalysisWarning, WarningSeverity
from app.infrastructure.database.models.analysis import AnalysisRun, AnalysisStatus, IndicatorResult
from app.infrastructure.database.models.version import ProjectVersion


def _warning_to_json(warning: AnalysisWarning) -> dict[str, Any]:
    return {
        "code": warning.code,
        "message": warning.message,
        "feature_ids": [str(feature_id) for feature_id in warning.feature_ids],
        "severity": warning.severity.value,
    }


def _warning_from_json(payload: dict[str, Any]) -> AnalysisWarning:
    return AnalysisWarning(
        code=payload["code"],
        message=payload["message"],
        feature_ids=tuple(uuid.UUID(value) for value in payload.get("feature_ids", [])),
        severity=WarningSeverity(payload.get("severity", WarningSeverity.WARNING.value)),
    )


def _to_calculation(row: IndicatorResult) -> IndicatorCalculation:
    return IndicatorCalculation(
        indicator_code=row.indicator_code,
        theme=row.theme,
        formula_version=row.formula_version,
        raw_value=float(row.value) if row.value is not None else None,
        unit=row.unit or "",
        metric_crs=row.metric_crs,
        source_layers=tuple(row.source_layers),
        contributing_feature_ids=tuple(uuid.UUID(value) for value in row.contributing_feature_ids),
        parameters=row.parameters,
        warnings=tuple(_warning_from_json(payload) for payload in row.warnings),
    )


class IndicatorRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save_batch(
        self, run_id: uuid.UUID, results: tuple[IndicatorCalculation, ...]
    ) -> None:
        for result in results:
            raw_value = result.raw_value
            self._session.add(
                IndicatorResult(
                    analysis_run_id=run_id,
                    theme=result.theme,
                    indicator_code=result.indicator_code,
                    formula_version=result.formula_version,
                    value=Decimal(str(raw_value)) if isinstance(raw_value, int | float) else None,
                    unit=result.unit,
                    metric_crs=result.metric_crs,
                    parameters=result.parameters,
                    source_layers=list(result.source_layers),
                    warnings=[_warning_to_json(warning) for warning in result.warnings],
                    contributing_feature_ids=[
                        str(feature_id) for feature_id in result.contributing_feature_ids
                    ],
                )
            )
        self._session.commit()

    def latest_completed(self, project_id: uuid.UUID) -> tuple[IndicatorCalculation, ...]:
        """Satisfies `app.application.analysis.get_results.ResultReader`."""
        run = (
            self._session.query(AnalysisRun)
            .join(ProjectVersion, AnalysisRun.project_version_id == ProjectVersion.id)
            .filter(
                ProjectVersion.project_id == project_id,
                AnalysisRun.status == AnalysisStatus.COMPLETED,
            )
            .order_by(AnalysisRun.run_at.desc())
            .first()
        )
        if run is None:
            return ()

        rows = (
            self._session.query(IndicatorResult)
            .filter(IndicatorResult.analysis_run_id == run.id)
            .order_by(IndicatorResult.indicator_code)
            .all()
        )
        return tuple(_to_calculation(row) for row in rows)
