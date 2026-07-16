from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="URBDATA_", env_file=".env", extra="ignore")

    app_name: str = "URBDATA API"
    environment: str = "local"
    api_v1_prefix: str = "/v1"
    database_url: str = "postgresql+psycopg://urbdata:urbdata@localhost:5432/urbdata"


class IndicatorDefaults(BaseSettings):
    """Effective values must be copied into the analysis run configuration."""

    model_config = SettingsConfigDict(env_prefix="URBDATA_INDICATOR_", extra="ignore")

    road_snapping_tolerance_m: float = Field(default=2.0, gt=0)
    lot_frontage_tolerance_m: float = Field(default=3.0, gt=0)
    average_household_size: float = Field(default=2.5, gt=0)
    average_unit_area_m2: float = Field(default=75.0, gt=0)
    floor_height_m: float = Field(default=3.0, gt=0)
    collinear_angle_tolerance_deg: float | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
