from dataclasses import dataclass
from uuid import UUID

from app.application.analysis.orchestrator import AnalysisOrchestrator, AnalysisRunOutcome


@dataclass(frozen=True, slots=True)
class AnalyzeProjectCommand:
    project_id: UUID
    themes: tuple[str, ...]
    feature_ids: tuple[UUID, ...] | None = None


class AnalyzeProject:
    """Application boundary for the synchronous MVP analysis flow."""

    def __init__(self, orchestrator: AnalysisOrchestrator) -> None:
        self._orchestrator = orchestrator

    def execute(self, command: AnalyzeProjectCommand) -> AnalysisRunOutcome:
        return self._orchestrator.execute(command)
