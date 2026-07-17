from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from app.domain.analysis.exceptions import InvalidSelectionError
from app.domain.geospatial.spatial_relations import SpatialRelation


@dataclass(frozen=True, slots=True)
class SelectRelatedFeaturesCommand:
    project_id: UUID
    target_layer_type: str
    relation: SpatialRelation | None = None
    source_feature_ids: tuple[UUID, ...] | None = None
    distance_m: float | None = None
    attribute_filters: dict[str, str] | None = None


class ProjectVersionResolver(Protocol):
    def current_version_id(self, project_id: UUID) -> UUID: ...


class FeatureSelector(Protocol):
    def select_related_feature_ids(
        self,
        *,
        project_version_id: UUID,
        target_layer_type: str,
        relation: SpatialRelation | None,
        source_feature_ids: tuple[UUID, ...] | None,
        distance_m: float | None,
        attribute_filters: dict[str, str] | None,
    ) -> tuple[UUID, ...]: ...


@dataclass(frozen=True, slots=True)
class SelectRelatedFeatures:
    """Interactive counterpart to the batch analysis engine (ADR 007): answers
    a spatial-plus-attribute query against one project version and returns
    matching feature ids, nothing else.
    """

    project_versions: ProjectVersionResolver
    selector: FeatureSelector

    def execute(self, command: SelectRelatedFeaturesCommand) -> tuple[UUID, ...]:
        if command.relation is not None and not command.source_feature_ids:
            raise InvalidSelectionError(
                "source_feature_ids is required when a spatial relation is given.",
                context={"relation": command.relation.value},
            )
        if command.relation is SpatialRelation.DWITHIN and command.distance_m is None:
            raise InvalidSelectionError(
                "distance_m is required for the 'dwithin' relation.",
                context={"relation": command.relation.value},
            )

        version_id = self.project_versions.current_version_id(command.project_id)
        return self.selector.select_related_feature_ids(
            project_version_id=version_id,
            target_layer_type=command.target_layer_type,
            relation=command.relation,
            source_feature_ids=command.source_feature_ids,
            distance_m=command.distance_m,
            attribute_filters=command.attribute_filters,
        )
