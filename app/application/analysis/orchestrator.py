from typing import Protocol

from app.application.analysis.analyze_project import AnalyzeProjectCommand
from app.domain.analysis.result import IndicatorCalculation


class AnalysisOrchestrator(Protocol):
    """Port that can later be implemented by a synchronous service or a queued worker."""

    def execute(self, command: AnalyzeProjectCommand) -> tuple[IndicatorCalculation, ...]: ...
