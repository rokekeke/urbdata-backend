from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from app.domain.analysis.result import IndicatorCalculation


class ResultReader(Protocol):
    def latest_completed(self, project_id: UUID) -> tuple[IndicatorCalculation, ...]: ...


@dataclass(frozen=True, slots=True)
class GetResults:
    repository: ResultReader

    def execute(self, project_id: UUID) -> tuple[IndicatorCalculation, ...]:
        return self.repository.latest_completed(project_id)
