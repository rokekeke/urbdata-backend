import uuid

from pydantic import BaseModel, model_validator

from app.domain.geospatial.spatial_relations import SpatialRelation


class SelectionRequest(BaseModel):
    target_layer_type: str
    relation: SpatialRelation | None = None
    source_feature_ids: list[uuid.UUID] | None = None
    distance_m: float | None = None
    attribute_filters: dict[str, str] | None = None

    @model_validator(mode="after")
    def _validate_relation_inputs(self) -> "SelectionRequest":
        if self.relation is not None and not self.source_feature_ids:
            raise ValueError("source_feature_ids e obrigatorio quando 'relation' e informado.")
        if self.relation is SpatialRelation.DWITHIN and self.distance_m is None:
            raise ValueError("distance_m e obrigatorio para a relacao 'dwithin'.")
        if self.distance_m is not None and self.distance_m <= 0:
            raise ValueError("distance_m deve ser maior que zero.")
        return self


class SelectionResponse(BaseModel):
    feature_ids: list[uuid.UUID]
    count: int
