import uuid

import pytest

from app.application.selection.select_related_features import (
    SelectRelatedFeatures,
    SelectRelatedFeaturesCommand,
)
from app.domain.analysis.exceptions import InvalidSelectionError
from app.domain.geospatial.spatial_relations import SpatialRelation

PROJECT_ID = uuid.uuid4()
VERSION_ID = uuid.uuid4()


class FakeProjectVersions:
    def current_version_id(self, project_id: uuid.UUID) -> uuid.UUID:
        assert project_id == PROJECT_ID
        return VERSION_ID


class FakeSelector:
    def __init__(self, feature_ids: tuple[uuid.UUID, ...] = ()) -> None:
        self.feature_ids = feature_ids
        self.calls: list[dict[str, object]] = []

    def select_related_feature_ids(
        self,
        *,
        project_version_id: uuid.UUID,
        target_layer_type: str,
        relation: SpatialRelation | None,
        source_feature_ids: tuple[uuid.UUID, ...] | None,
        distance_m: float | None,
        attribute_filters: dict[str, str] | None,
    ) -> tuple[uuid.UUID, ...]:
        assert project_version_id == VERSION_ID
        self.calls.append(
            {
                "target_layer_type": target_layer_type,
                "relation": relation,
                "source_feature_ids": source_feature_ids,
                "distance_m": distance_m,
                "attribute_filters": attribute_filters,
            }
        )
        return self.feature_ids


def test_pure_attribute_filter_without_spatial_relation_is_allowed() -> None:
    expected = (uuid.uuid4(),)
    selector = FakeSelector(expected)
    use_case = SelectRelatedFeatures(project_versions=FakeProjectVersions(), selector=selector)

    result = use_case.execute(
        SelectRelatedFeaturesCommand(
            project_id=PROJECT_ID,
            target_layer_type="lotes",
            attribute_filters={"land_use": "residencial"},
        )
    )

    assert result == expected
    assert selector.calls[0]["relation"] is None


def test_spatial_relation_requires_source_feature_ids() -> None:
    use_case = SelectRelatedFeatures(
        project_versions=FakeProjectVersions(), selector=FakeSelector()
    )

    with pytest.raises(InvalidSelectionError):
        use_case.execute(
            SelectRelatedFeaturesCommand(
                project_id=PROJECT_ID,
                target_layer_type="lotes",
                relation=SpatialRelation.INTERSECTS,
            )
        )


def test_dwithin_requires_distance_m() -> None:
    use_case = SelectRelatedFeatures(
        project_versions=FakeProjectVersions(), selector=FakeSelector()
    )

    with pytest.raises(InvalidSelectionError):
        use_case.execute(
            SelectRelatedFeaturesCommand(
                project_id=PROJECT_ID,
                target_layer_type="equipamentos",
                relation=SpatialRelation.DWITHIN,
                source_feature_ids=(uuid.uuid4(),),
            )
        )


def test_combined_spatial_and_attribute_filter_is_forwarded_to_the_selector() -> None:
    source_id = uuid.uuid4()
    selector = FakeSelector((uuid.uuid4(),))
    use_case = SelectRelatedFeatures(project_versions=FakeProjectVersions(), selector=selector)

    use_case.execute(
        SelectRelatedFeaturesCommand(
            project_id=PROJECT_ID,
            target_layer_type="lotes",
            relation=SpatialRelation.WITHIN,
            source_feature_ids=(source_id,),
            attribute_filters={"land_use": "residencial"},
        )
    )

    call = selector.calls[0]
    assert call["relation"] is SpatialRelation.WITHIN
    assert call["source_feature_ids"] == (source_id,)
    assert call["attribute_filters"] == {"land_use": "residencial"}
