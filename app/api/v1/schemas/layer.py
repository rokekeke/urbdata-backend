import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.infrastructure.database.models.layer import LayerStatus, LayerType


class LayerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_version_id: uuid.UUID
    layer_type: LayerType
    source_filename: str | None
    geometry_type: str | None
    feature_count: int
    status: LayerStatus
    uploaded_at: datetime


class LayerAttributesOut(BaseModel):
    layer_id: uuid.UUID
    source_fields: list[str]
    sample_values: dict[str, list[str]]
    suggested_mapping: dict[str, str | None]


class LayerAttributeMappingIn(BaseModel):
    mappings: dict[str, str | None]
