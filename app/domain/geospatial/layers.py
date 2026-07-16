from dataclasses import dataclass
from uuid import UUID

from geopandas import GeoDataFrame
from pyproj import CRS


@dataclass(frozen=True, slots=True)
class LoadedFeatureLayer:
    layer_id: UUID
    layer_type: str
    source_crs: CRS
    gdf: GeoDataFrame

    def __post_init__(self) -> None:
        if "feature_id" not in self.gdf.columns:
            raise ValueError("Loaded layers must preserve an explicit feature_id column.")
        if self.gdf.crs is None:
            raise ValueError("Loaded layers must have an explicit CRS.")
