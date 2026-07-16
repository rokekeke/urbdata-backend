from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class AnalyzeProjectCommand:
    project_id: UUID
    themes: tuple[str, ...]
    feature_ids: tuple[UUID, ...] | None = None


class Orchestrator(Protocol):
    def execute(self, command: AnalyzeProjectCommand) -> object: ...


class AnalyzeProject:
    """Application boundary for the synchronous MVP analysis flow."""

    def __init__(self, orchestrator: Orchestrator) -> None:
        self._orchestrator = orchestrator

    def execute(self, command: AnalyzeProjectCommand) -> object:
        return self._orchestrator.execute(command)
