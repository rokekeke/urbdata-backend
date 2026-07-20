"""SQLAlchemy models mapped onto the URBDATA relational schema.

Ported from the already-running URBDATA backend (project -> version -> layer ->
feature). This is the model set the domain and application layers were waiting
on before any repository or route could be implemented for real.
"""

from app.infrastructure.database.base import Base
from app.infrastructure.database.models.analysis import (
    AnalysisRun,
    AnalysisStatus,
    IndicatorClassification,
    IndicatorResult,
    ReferenceParameter,
)
from app.infrastructure.database.models.export import Export
from app.infrastructure.database.models.feature import Feature, RelationMethod
from app.infrastructure.database.models.layer import (
    LayerAttributeMapping,
    LayerStatus,
    LayerType,
    ProjectLayer,
)
from app.infrastructure.database.models.map_document import MapDocument
from app.infrastructure.database.models.project import Project
from app.infrastructure.database.models.style import StylePreset
from app.infrastructure.database.models.validation import (
    ValidationIssue,
    ValidationRun,
    ValidationSeverity,
    ValidationStatus,
)
from app.infrastructure.database.models.version import ProjectVersion, ProjectVersionStatus

__all__ = [
    "Base",
    "Project",
    "ProjectVersion",
    "ProjectVersionStatus",
    "ProjectLayer",
    "LayerAttributeMapping",
    "LayerType",
    "LayerStatus",
    "Feature",
    "RelationMethod",
    "ValidationRun",
    "ValidationIssue",
    "ValidationStatus",
    "ValidationSeverity",
    "AnalysisRun",
    "IndicatorResult",
    "ReferenceParameter",
    "AnalysisStatus",
    "IndicatorClassification",
    "StylePreset",
    "Export",
    "MapDocument",
]
