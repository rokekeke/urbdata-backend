"""Controlled basemap catalog (ADR 014, Decisao 5 - DOC-BE-006).

No database, no credentials: the catalog is server-defined and static in
v1. Free-form URLs are deliberately not accepted.
"""

from fastapi import APIRouter

from app.api.v1.schemas.basemap import BasemapOut
from app.domain.cartography.basemaps import BASEMAPS

router = APIRouter(prefix="/map-basemaps", tags=["basemaps"])


@router.get("", response_model=list[BasemapOut])
def list_basemaps() -> list[BasemapOut]:
    return [
        BasemapOut(
            id=basemap.id,
            label=basemap.label,
            style_url=basemap.style_url,
            color_mode=basemap.color_mode,
            attribution=basemap.attribution,
            export_allowed=basemap.export_allowed,
        )
        for basemap in BASEMAPS
    ]
