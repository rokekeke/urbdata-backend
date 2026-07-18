from pydantic import BaseModel

from app.domain.analysis.presentation import FeatureKey, IndicatorGranularity


class CatalogIndicatorOut(BaseModel):
    code: str
    theme: str
    display_name: str
    description: str
    unit: str
    formula_version: str
    granularity: IndicatorGranularity
    feature_key: FeatureKey | None
    required_layers: list[str]
    optional_layers: list[str]
