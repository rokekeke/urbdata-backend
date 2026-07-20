"""Write-time contextual validation of a MapDocument (ADR 014, Decisao 3
and 8) - the checks `document.py` (item 2) explicitly cannot do without
DB access: a layer_id belongs to the document's ProjectVersion, an
indicator_code is compatible with its layer's type, a property field
reference actually exists in that layer's data, and `representation.mode`
is compatible with what actually drives it (a field's real data, or an
indicator's value shape).

Pure and DB-free: takes pre-fetched `LayerContext` per layer (built by
`build_layer_contexts`, which does the real querying) so this module is
unit-testable with synthetic data. Collects every violation instead of
failing on the first one, matching the structural validation's philosophy
(item 2) of reporting everything wrong in one pass.

This is the authoritative counterpart to `representation_options.
recommend_mode` (Fase 2): that module only *suggests*; a field/indicator
reference either resolves against real data here, or the write is
rejected - never silently accepted or silently dropped.

Geometry is deliberately NOT part of this module's checks: `LayerStyle`
(item 2) always carries both `fill` and `stroke` regardless of the
layer's geometry - a LineString's unused `fill` or a Polygon's unused
`stroke` values simply don't render client-side. There is no mode that a
geometry type makes structurally invalid, so "mode compativel com a
geometria" (document.py's docstring) is satisfied by that schema choice,
not by an additional rule here.
"""

import uuid
from dataclasses import dataclass

from app.domain.cartography.document import (
    DocumentLayer,
    FeaturePanelConfig,
    FeaturePanelFieldSource,
    MapDocumentConfig,
    Representation,
    RepresentationMode,
    RepresentationSource,
    TableBlock,
    TextBlock,
)
from app.domain.cartography.representation_options import (
    DetectedType,
    FieldStats,
    compatible_indicator_codes,
    recommend_mode,
)
from app.domain.indicators.catalog import build_registry

# Catalog convention (ADR 014 / Fase 0): a structured (dict-shaped) result,
# e.g. quadras.stats, quadras.min_rotated_rectangle. Cannot drive any
# thematic scale - there is no numeric/ordinal domain to classify.
_STRUCTURED_INDICATOR_UNIT = "composto"

# scale/mode families that genuinely require a numeric domain (d3-scale's
# quantile/quantize/linear/sqrt/log/threshold all operate on numbers).
_NUMERIC_ONLY_MODES = frozenset({RepresentationMode.SEQUENTIAL, RepresentationMode.DIVERGING})


@dataclass(frozen=True, slots=True)
class LayerContext:
    layer_type: str
    fields: dict[str, FieldStats]


@dataclass(frozen=True, slots=True)
class ContextViolation:
    path: str
    code: str
    message: str


def references_property_field(layer: DocumentLayer) -> bool:
    """Whether resolving `layer` needs field-stats data at all - lets the
    caller skip the aggregate_representation_stats query for layers that
    only use source=indicator/none (DOC-BE-004's "never scan the layer
    for nothing" discipline, Fase 2)."""
    if (
        layer.representation.source is RepresentationSource.PROPERTY
        or layer.interaction.feature_panel.title_field is not None
    ):
        return True
    for block in layer.interaction.feature_panel.blocks:
        if isinstance(block, TextBlock):
            if block.source is FeaturePanelFieldSource.PROPERTY:
                return True
        else:
            if any(
                field.source is FeaturePanelFieldSource.PROPERTY for field in block.fields
            ):
                return True
    return False


def validate_document_context(
    config: MapDocumentConfig, layers: dict[uuid.UUID, LayerContext]
) -> list[ContextViolation]:
    violations: list[ContextViolation] = []
    for index, layer in enumerate(config.layers):
        base = f"layers[{index}]"
        context = layers.get(layer.layer_id)
        if context is None:
            violations.append(
                ContextViolation(
                    path=f"{base}.layer_id",
                    code="layer_not_in_version",
                    message=(
                        f"Camada {layer.layer_id} nao pertence a esta versao do projeto."
                    ),
                )
            )
            continue  # nothing else about this layer can be checked
        violations.extend(
            _validate_representation(layer.representation, context, f"{base}.representation")
        )
        violations.extend(
            _validate_feature_panel(
                layer.interaction.feature_panel,
                context,
                f"{base}.interaction.feature_panel",
            )
        )
    return violations


@dataclass(frozen=True, slots=True)
class IntegrityWarning:
    layer_id: uuid.UUID
    code: str
    message: str


def compute_integrity_warnings(
    config: MapDocumentConfig, layers: dict[uuid.UUID, LayerContext]
) -> list[IntegrityWarning]:
    """Read-time diagnostic (ADR 014, Decisao 8): the exact same
    compatibility rules `validate_document_context` enforces at write
    time (4.3), reused here as information only - GET never fails and
    never silently corrects a stale reference (regra 2 do projeto), it
    just reports what has rotted since the document was saved (deleted
    layer, quadras re-derived with a new id - ADR 009, remapped field,
    catalog change). Grouped by the owning `layer_id` - a reader wants
    "what's wrong with this layer", not the write-time field path."""
    violations = validate_document_context(config, layers)
    warnings: list[IntegrityWarning] = []
    for index, layer in enumerate(config.layers):
        prefix = f"layers[{index}]."
        for violation in violations:
            if violation.path.startswith(prefix):
                warnings.append(
                    IntegrityWarning(
                        layer_id=layer.layer_id,
                        code=violation.code,
                        message=violation.message,
                    )
                )
    return warnings


def _field_violation(path: str, field: str) -> ContextViolation:
    return ContextViolation(
        path=path,
        code="field_not_found",
        message=f"Campo '{field}' nao encontrado na camada.",
    )


def _indicator_violation(path: str, indicator_code: str, layer_type: str) -> ContextViolation:
    return ContextViolation(
        path=path,
        code="indicator_incompatible_with_layer",
        message=(
            f"Indicador '{indicator_code}' nao e compativel com o tipo de "
            f"camada '{layer_type}'."
        ),
    )


def _mode_field_violations(
    mode: RepresentationMode, field: str, stats: FieldStats, path: str
) -> list[ContextViolation]:
    recommendation = recommend_mode(stats)
    if recommendation.unsuitable_reason is not None and mode is not RepresentationMode.SINGLE:
        return [
            ContextViolation(
                path=path,
                code="field_unsuitable_for_representation",
                message=(
                    f"Campo '{field}' nao pode ser representado tematicamente "
                    f"({recommendation.unsuitable_reason})."
                ),
            )
        ]
    if mode in _NUMERIC_ONLY_MODES and recommendation.detected_type is not DetectedType.NUMERIC:
        return [
            ContextViolation(
                path=path,
                code="mode_incompatible_with_field_type",
                message=(
                    f"mode={mode.value} exige campo numerico; '{field}' e "
                    f"{recommendation.detected_type.value}."
                ),
            )
        ]
    return []


def _mode_indicator_violations(
    mode: RepresentationMode, indicator_code: str, path: str
) -> list[ContextViolation]:
    definition = build_registry().get(indicator_code)
    if definition.unit == _STRUCTURED_INDICATOR_UNIT and mode is not RepresentationMode.SINGLE:
        return [
            ContextViolation(
                path=path,
                code="mode_incompatible_with_indicator_type",
                message=(
                    f"Indicador '{indicator_code}' tem valor composto (nao "
                    f"escalar) - nao pode alimentar mode={mode.value}."
                ),
            )
        ]
    return []


def _validate_representation(
    representation: Representation, context: LayerContext, path: str
) -> list[ContextViolation]:
    if representation.source is RepresentationSource.PROPERTY:
        assert representation.field is not None  # guaranteed by document.py's own validation
        stats = context.fields.get(representation.field)
        if stats is None:
            return [_field_violation(f"{path}.field", representation.field)]
        return _mode_field_violations(
            representation.mode, representation.field, stats, f"{path}.mode"
        )
    if representation.source is RepresentationSource.INDICATOR:
        assert representation.indicator_code is not None
        if representation.indicator_code not in compatible_indicator_codes(context.layer_type):
            return [
                _indicator_violation(
                    f"{path}.indicator_code", representation.indicator_code, context.layer_type
                )
            ]
        return _mode_indicator_violations(
            representation.mode, representation.indicator_code, f"{path}.mode"
        )
    return []


def _validate_field_reference(
    source: FeaturePanelFieldSource, value: str, context: LayerContext, path: str
) -> list[ContextViolation]:
    if source is FeaturePanelFieldSource.PROPERTY:
        if value not in context.fields:
            return [_field_violation(path, value)]
    elif value not in compatible_indicator_codes(context.layer_type):
        return [_indicator_violation(path, value, context.layer_type)]
    return []


def _validate_feature_panel(
    panel: FeaturePanelConfig, context: LayerContext, path: str
) -> list[ContextViolation]:
    violations: list[ContextViolation] = []
    if panel.title_field is not None and panel.title_field not in context.fields:
        violations.append(_field_violation(f"{path}.title_field", panel.title_field))
    for block_index, block in enumerate(panel.blocks):
        block_path = f"{path}.blocks[{block_index}]"
        if isinstance(block, TextBlock):
            violations.extend(
                _validate_field_reference(
                    block.source, block.field, context, f"{block_path}.field"
                )
            )
        else:
            assert isinstance(block, TableBlock)
            for field_index, field in enumerate(block.fields):
                violations.extend(
                    _validate_field_reference(
                        field.source,
                        field.key,
                        context,
                        f"{block_path}.fields[{field_index}].key",
                    )
                )
    return violations
