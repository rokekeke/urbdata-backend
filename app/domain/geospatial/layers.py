from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from geopandas import GeoDataFrame
from pyproj import CRS

from app.domain.analysis.exceptions import DuplicateLayerError


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


def resolve_single_layer_id(layer_ids: Sequence[UUID], *, layer_type: str) -> UUID | None:
    """Resolve a project version's layer of *layer_type* to a single id
    (BT-011).

    Returns `None` when there is none. Raises `DuplicateLayerError` when
    more than one layer of the same type exists for the version - which one
    is authoritative is a data problem to fix upstream, not something to
    guess by silently picking the first match.
    """
    if not layer_ids:
        return None
    if len(layer_ids) > 1:
        raise DuplicateLayerError(
            "More than one layer of this type exists for the project version.",
            context={"layer_type": layer_type, "layer_ids": [str(lid) for lid in layer_ids]},
        )
    return layer_ids[0]
