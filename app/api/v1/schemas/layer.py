import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.domain.cartography.document import RepresentationMode
from app.domain.cartography.representation_options import DetectedType, FieldOrigin
from app.infrastructure.database.models.layer import ImportProfile, LayerStatus, LayerType


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
    # Combined/split import traceability (nota 53/54) - always present;
    # only the split profile populates anything beyond import_profile itself.
    import_profile: ImportProfile
    attributes_filename: str | None
    attributes_join_key: str | None
    geometry_join_key: str | None
    join_summary: dict[str, Any] | None


class RepresentationFieldOut(BaseModel):
    """Aggregated stats + cartographic recommendation for one field
    (DOC-BE-004 / ADR 014). The recommendation is a suggestion; the
    authoritative validation happens on the map document itself."""

    field: str
    origin: FieldOrigin
    detected_type: DetectedType
    present_count: int
    empty_count: int
    cardinality: int
    distinct_values: list[str] | None
    min_value: float | None
    max_value: float | None
    recommended_mode: RepresentationMode | None
    unsuitable_reason: str | None


class LayerAttributesOut(BaseModel):
    layer_id: uuid.UUID
    source_fields: list[str]
    sample_values: dict[str, list[str]]
    suggested_mapping: dict[str, str | None]
    feature_count: int
    fields: list[RepresentationFieldOut]
    # Per-feature indicators whose persisted dict values can style this
    # layer type (join contract documented in ADR 014).
    compatible_indicators: list[str]


class LayerAttributeMappingIn(BaseModel):
    mappings: dict[str, str | None]


class AttributeMappingWarningOut(BaseModel):
    feature_id: uuid.UUID
    message: str


class LayerAttributeMappingOut(BaseModel):
    layer_id: uuid.UUID
    status: str
    features_updated: int
    # Values the checkpoint decision (nota 53/54) says must never be
    # auto-converted (e.g. reference_area_m2 with an unrecognized unit) -
    # set to null and reported here instead of failing the whole mapping.
    warnings: list[AttributeMappingWarningOut]


class QuadrasDeriveOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    layer_id: uuid.UUID
    quadra_count: int
    lot_count: int


class GeoJSONFeatureOut(BaseModel):
    type: str = "Feature"
    id: str
    geometry: dict[str, object]
    properties: dict[str, object]


class GeoJSONFeatureCollectionOut(BaseModel):
    type: str = "FeatureCollection"
    features: list[GeoJSONFeatureOut]
