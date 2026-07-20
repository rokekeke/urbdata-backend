"""MapDocument v1 - structural validation of the cartographic contract.

Implements ADR 014 (Decisoes 2-4). These models enforce every rule that
does NOT require database context: enum vocabularies, mode x scale
compatibility, hex colors, opacity/width bounds, ordered stops, palette
sizing, reserved-in-v1 fields and basemap membership. Context-dependent
rules (layer belongs to the ProjectVersion, field exists in the layer,
mode compatible with field type and geometry) are applied at persistence
time by the Fase 3 CRUD on top of these models.

`extra="forbid"` everywhere: an unknown key is a schema violation, never
silently carried - evolving the shape requires a `schema_version` bump
(upcast-on-read policy, ADR 014 Decisao 4).

Pydantic error paths (`loc`) satisfy DOC-BE-005's acceptance criterion:
invalid configuration reports code, message and field path.
"""

import re
import uuid
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.analysis.presentation import PRESENTATIONS, IndicatorGranularity
from app.domain.cartography.basemaps import BASEMAP_IDS

SCHEMA_VERSION = "1"

# ADR 014 / nota 28: warn above 12 classes, block above 32.
CATEGORICAL_CLASS_WARN_LIMIT = 12
CATEGORICAL_CLASS_BLOCK_LIMIT = 32
STOPS_MIN = 2
STOPS_MAX = 12
STROKE_WIDTH_MAX_PX = 20.0

# Feature panel limits (ADR 014, Decisao 7 / nota 33): the panel never
# carries free text - blocks reference fields/indicators, never a literal
# user string - so these bounds are about clutter, not injection.
FEATURE_PANEL_MAX_BLOCKS = 8
TABLE_FIELD_MIN = 1
TABLE_FIELD_MAX = 12
FIELD_LABEL_MAX_LENGTH = 60
FORMAT_PREFIX_MAX_LENGTH = 8
FORMAT_SUFFIX_MAX_LENGTH = 16
FORMAT_DECIMALS_MAX = 6

_HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}([0-9a-fA-F]{2})?$")


class RepresentationSource(StrEnum):
    PROPERTY = "property"
    INDICATOR = "indicator"
    NONE = "none"


class RepresentationMode(StrEnum):
    SINGLE = "single"
    CATEGORICAL = "categorical"
    SEQUENTIAL = "sequential"
    DIVERGING = "diverging"


class ScaleType(StrEnum):
    """Vocabulary shared with kepler.gl/d3-scale (ADR 014, nota 32)."""

    ORDINAL = "ordinal"
    QUANTILE = "quantile"
    QUANTIZE = "quantize"
    LINEAR = "linear"
    SQRT = "sqrt"
    LOG = "log"
    THRESHOLD = "threshold"


class StrokeLineStyle(StrEnum):
    SOLID = "solid"
    DASHED = "dashed"
    DOTTED = "dotted"


class NullBehavior(StrEnum):
    TRANSPARENT = "transparent"
    COLOR = "color"


_SCALES_BY_MODE: dict[RepresentationMode, frozenset[ScaleType]] = {
    RepresentationMode.SINGLE: frozenset(),
    RepresentationMode.CATEGORICAL: frozenset({ScaleType.ORDINAL}),
    RepresentationMode.SEQUENTIAL: frozenset(
        {
            ScaleType.QUANTILE,
            ScaleType.QUANTIZE,
            ScaleType.LINEAR,
            ScaleType.SQRT,
            ScaleType.LOG,
            ScaleType.THRESHOLD,
        }
    ),
    RepresentationMode.DIVERGING: frozenset(
        {
            ScaleType.QUANTILE,
            ScaleType.QUANTIZE,
            ScaleType.LINEAR,
            ScaleType.SQRT,
            ScaleType.LOG,
            ScaleType.THRESHOLD,
        }
    ),
}


def _require_hex(value: str | None) -> str | None:
    if value is not None and not _HEX_COLOR.match(value):
        raise ValueError(f"cor invalida (esperado #RRGGBB ou #RRGGBBAA): {value!r}")
    return value


def _validate_por_feicao_indicator(indicator_code: str) -> None:
    """Shared by Representation (Decisao 2) and the feature panel blocks
    (Decisao 7): only per-feature indicators can be tied to one feature."""
    presentation = PRESENTATIONS.get(indicator_code)
    if presentation is None:
        raise ValueError(f"indicador nao registrado: {indicator_code!r}")
    if presentation.granularity is not IndicatorGranularity.POR_FEICAO:
        raise ValueError(
            f"indicador {indicator_code!r} nao e por feicao - "
            "nao pode ser associado a uma feicao"
        )


class Viewport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    longitude: float = Field(ge=-180, le=180)
    latitude: float = Field(ge=-90, le=90)
    zoom: float = Field(ge=0, le=24)
    bearing: float = Field(default=0, ge=-360, le=360)
    pitch: float = Field(default=0, ge=0, le=85)


class Representation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: RepresentationSource
    field: str | None = None
    indicator_code: str | None = None
    mode: RepresentationMode
    scale: ScaleType | None = None
    classes: int | None = Field(default=None, ge=1, le=CATEGORICAL_CLASS_BLOCK_LIMIT)
    stops: list[float] | None = None
    null_behavior: NullBehavior = NullBehavior.TRANSPARENT

    @model_validator(mode="after")
    def _check_source(self) -> "Representation":
        if self.source is RepresentationSource.PROPERTY:
            if not self.field:
                raise ValueError("source=property exige 'field'")
            if self.indicator_code is not None:
                raise ValueError("source=property nao aceita 'indicator_code'")
        elif self.source is RepresentationSource.INDICATOR:
            if not self.indicator_code:
                raise ValueError("source=indicator exige 'indicator_code'")
            if self.field is not None:
                raise ValueError("source=indicator nao aceita 'field'")
            _validate_por_feicao_indicator(self.indicator_code)
        else:  # NONE
            if self.field is not None or self.indicator_code is not None:
                raise ValueError("source=none nao aceita 'field' nem 'indicator_code'")
            if self.mode is not RepresentationMode.SINGLE:
                raise ValueError("source=none exige mode=single")
        return self

    @model_validator(mode="after")
    def _check_mode_scale(self) -> "Representation":
        allowed = _SCALES_BY_MODE[self.mode]
        if self.mode is RepresentationMode.SINGLE:
            if self.scale is not None:
                raise ValueError("mode=single nao aceita 'scale'")
            if self.classes is not None or self.stops is not None:
                raise ValueError("mode=single nao aceita 'classes' nem 'stops'")
            return self
        if self.scale is None:
            raise ValueError(f"mode={self.mode.value} exige 'scale'")
        if self.scale not in allowed:
            raise ValueError(
                f"scale={self.scale.value} incompativel com mode={self.mode.value}"
            )
        if self.scale is ScaleType.THRESHOLD:
            if self.stops is None:
                raise ValueError("scale=threshold exige 'stops'")
            if self.classes is not None:
                raise ValueError(
                    "scale=threshold nao aceita 'classes' (derivado de stops)"
                )
            if not (STOPS_MIN <= len(self.stops) <= STOPS_MAX):
                raise ValueError(
                    f"stops deve ter entre {STOPS_MIN} e {STOPS_MAX} valores"
                )
            if any(b <= a for a, b in zip(self.stops, self.stops[1:], strict=False)):
                raise ValueError("stops devem ser estritamente crescentes e unicos")
        else:
            if self.stops is not None:
                raise ValueError("'stops' so e aceito com scale=threshold")
            if self.classes is None:
                raise ValueError(f"mode={self.mode.value} exige 'classes'")
        return self

    def effective_classes(self) -> int | None:
        """Number of legend classes: explicit, or derived from stops."""
        if self.stops is not None:
            return len(self.stops) + 1
        return self.classes


class FillStyle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    color: str | None = None
    palette: list[str] | None = None
    opacity: float = Field(ge=0, le=1)

    @field_validator("color")
    @classmethod
    def _color_hex(cls, value: str | None) -> str | None:
        return _require_hex(value)

    @field_validator("palette")
    @classmethod
    def _palette_hex(cls, value: list[str] | None) -> list[str] | None:
        if value is not None:
            for item in value:
                _require_hex(item)
        return value


class StrokeStyle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    color: str
    width_px: float = Field(gt=0, le=STROKE_WIDTH_MAX_PX)
    style: StrokeLineStyle = StrokeLineStyle.SOLID
    opacity: float = Field(ge=0, le=1)

    @field_validator("color")
    @classmethod
    def _color_hex(cls, value: str) -> str:
        _require_hex(value)
        return value


class LayerStyle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fill: FillStyle
    stroke: StrokeStyle
    null_color: str | None = None
    # Reserved in v1 (ADR 014): persisted for round-trip, no editor yet.
    labels: None = None

    @field_validator("null_color")
    @classmethod
    def _null_color_hex(cls, value: str | None) -> str | None:
        return _require_hex(value)


class FeaturePanelFieldSource(StrEnum):
    """Origin of a feature-panel field - deliberately its own enum (not
    RepresentationSource): a panel block never has a 'none' origin."""

    PROPERTY = "property"
    INDICATOR = "indicator"


class TextBlockStyle(StrEnum):
    BODY = "body"
    SUBTITLE = "subtitle"


class FeaturePanelWidth(StrEnum):
    COMPACT = "compact"
    MEDIUM = "medium"


class FieldFormatType(StrEnum):
    TEXT = "text"
    NUMBER = "number"


class FieldFormat(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: FieldFormatType
    decimals: int | None = Field(default=None, ge=0, le=FORMAT_DECIMALS_MAX)
    prefix: str | None = Field(default=None, min_length=1, max_length=FORMAT_PREFIX_MAX_LENGTH)
    suffix: str | None = Field(default=None, min_length=1, max_length=FORMAT_SUFFIX_MAX_LENGTH)

    @model_validator(mode="after")
    def _check_type_consistency(self) -> "FieldFormat":
        if self.type is FieldFormatType.TEXT and (
            self.decimals is not None or self.prefix is not None or self.suffix is not None
        ):
            raise ValueError("format tipo=text nao aceita decimals/prefix/suffix")
        return self


class TextBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["text"]
    source: FeaturePanelFieldSource
    field: str = Field(min_length=1)
    style: TextBlockStyle = TextBlockStyle.BODY

    @model_validator(mode="after")
    def _check_indicator_field(self) -> "TextBlock":
        if self.source is FeaturePanelFieldSource.INDICATOR:
            _validate_por_feicao_indicator(self.field)
        return self


class TableField(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: FeaturePanelFieldSource
    key: str = Field(min_length=1)
    label: str = Field(min_length=1, max_length=FIELD_LABEL_MAX_LENGTH)
    format: FieldFormat | None = None

    @model_validator(mode="after")
    def _check_indicator_key(self) -> "TableField":
        if self.source is FeaturePanelFieldSource.INDICATOR:
            _validate_por_feicao_indicator(self.key)
        return self


class TableBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["table"]
    layout: Literal["key_value"] = "key_value"
    fields: list[TableField] = Field(min_length=TABLE_FIELD_MIN, max_length=TABLE_FIELD_MAX)

    @model_validator(mode="after")
    def _check_unique_fields(self) -> "TableBlock":
        seen: set[tuple[FeaturePanelFieldSource, str]] = set()
        for item in self.fields:
            key = (item.source, item.key)
            if key in seen:
                raise ValueError(
                    f"campo duplicado na tabela: source={item.source.value!r}, "
                    f"key={item.key!r}"
                )
            seen.add(key)
        return self


FeaturePanelBlock = Annotated[TextBlock | TableBlock, Field(discriminator="type")]


class FeaturePanelConfig(BaseModel):
    """ADR 014, Decisao 7 (nota 33) - core panel opened on feature click.
    Disabled by default: an absent/default config is a valid, inert
    document, not an error."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    title_field: str | None = None
    width: FeaturePanelWidth = FeaturePanelWidth.COMPACT
    blocks: list[FeaturePanelBlock] = Field(
        default_factory=list, max_length=FEATURE_PANEL_MAX_BLOCKS
    )


class Interaction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tooltip_fields: list[str] = Field(default_factory=list)
    selectable: bool = True
    feature_panel: FeaturePanelConfig = Field(default_factory=FeaturePanelConfig)
    # Reserved in v1 (ADR 014): visual filters never alter persisted results.
    filters: None = None


class DocumentLayer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    layer_id: uuid.UUID
    visible: bool = True
    representation: Representation
    style: LayerStyle
    interaction: Interaction = Field(default_factory=Interaction)

    @model_validator(mode="after")
    def _check_palette_against_classes(self) -> "DocumentLayer":
        mode = self.representation.mode
        palette = self.style.fill.palette
        if mode is RepresentationMode.SINGLE:
            if palette is not None:
                raise ValueError("mode=single nao aceita 'palette' (use fill.color)")
            return self
        if palette is None:
            raise ValueError(f"mode={mode.value} exige 'style.fill.palette'")
        expected = self.representation.effective_classes()
        if expected is not None and len(palette) != expected:
            raise ValueError(
                f"palette tem {len(palette)} cores, esperado {expected} "
                "(= classes, ou stops + 1)"
            )
        return self

    @model_validator(mode="after")
    def _check_null_color(self) -> "DocumentLayer":
        if (
            self.representation.null_behavior is NullBehavior.COLOR
            and self.style.null_color is None
        ):
            raise ValueError("null_behavior=color exige 'style.null_color'")
        return self


class MapDocumentConfig(BaseModel):
    """The JSONB payload of a map document (ADR 014, Decisao 2)."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1"]
    name: str = Field(min_length=1)
    title: str | None = None
    basemap_id: str
    viewport: Viewport
    layers: list[DocumentLayer] = Field(default_factory=list)

    @field_validator("basemap_id")
    @classmethod
    def _basemap_in_catalog(cls, value: str) -> str:
        if value not in BASEMAP_IDS:
            raise ValueError(f"basemap_id fora do catalogo: {value!r}")
        return value

    @model_validator(mode="after")
    def _unique_layer_ids(self) -> "MapDocumentConfig":
        seen: set[uuid.UUID] = set()
        for layer in self.layers:
            if layer.layer_id in seen:
                raise ValueError(f"layer_id duplicado no documento: {layer.layer_id}")
            seen.add(layer.layer_id)
        return self


class DocumentWarning(BaseModel):
    """Soft rule outcome: valid document, but worth surfacing (ADR 014)."""

    code: str
    message: str
    layer_id: uuid.UUID | None = None


def document_warnings(document: MapDocumentConfig) -> list[DocumentWarning]:
    """Soft rules that do not block persistence - today only the
    categorical legibility warning (>12 classes, block at >32 is a hard
    rule enforced by the models)."""
    warnings: list[DocumentWarning] = []
    for layer in document.layers:
        classes = layer.representation.effective_classes()
        if (
            layer.representation.mode is RepresentationMode.CATEGORICAL
            and classes is not None
            and classes > CATEGORICAL_CLASS_WARN_LIMIT
        ):
            warnings.append(
                DocumentWarning(
                    code="high_categorical_class_count",
                    message=(
                        f"{classes} classes categoricas - acima de "
                        f"{CATEGORICAL_CLASS_WARN_LIMIT} a legenda perde legibilidade."
                    ),
                    layer_id=layer.layer_id,
                )
            )
    return warnings


def upcast_document(payload: dict[str, object]) -> dict[str, object]:
    """Schema-version upcast on read (ADR 014, Decisao 4). v1 -> v1 is the
    identity; future versions chain pure conversions here. Unknown versions
    raise - never guess."""
    version = payload.get("schema_version")
    if version == SCHEMA_VERSION:
        return payload
    raise ValueError(f"schema_version desconhecida: {version!r}")
