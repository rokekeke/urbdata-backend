from dataclasses import dataclass, field
from enum import StrEnum
from uuid import UUID


class WarningSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"


@dataclass(frozen=True, slots=True)
class AnalysisWarning:
    code: str
    message: str
    feature_ids: tuple[UUID, ...] = field(default_factory=tuple)
    severity: WarningSeverity = WarningSeverity.WARNING
