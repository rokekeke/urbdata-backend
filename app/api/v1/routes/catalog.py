"""Read-only indicator catalog (Fase 0, nota Obsidian 28/29).

No database involved: composes the in-process registry with the
presentation table so the frontend can discover themes, friendly names,
units and map-join metadata without hardcoding indicator codes.
"""

from fastapi import APIRouter

from app.api.v1.schemas.catalog import CatalogIndicatorOut
from app.domain.analysis.presentation import PRESENTATIONS
from app.domain.indicators.catalog import build_registry

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("/indicators", response_model=list[CatalogIndicatorOut])
def list_indicators() -> list[CatalogIndicatorOut]:
    registry = build_registry()
    entries: list[CatalogIndicatorOut] = []
    for definition in registry.all():
        presentation = PRESENTATIONS[definition.code]
        entries.append(
            CatalogIndicatorOut(
                code=definition.code,
                theme=definition.theme,
                display_name=presentation.display_name,
                description=presentation.description,
                unit=definition.unit,
                formula_version=definition.formula_version,
                granularity=presentation.granularity,
                feature_key=presentation.feature_key,
                value_shape=presentation.value_shape,
                category_feature_property=presentation.category_feature_property,
                internal=presentation.internal,
                required_layers=list(definition.required_layers),
                optional_layers=list(definition.optional_layers),
            )
        )
    return sorted(entries, key=lambda entry: (entry.theme, entry.code))
