from pydantic import BaseModel

from app.domain.cartography.basemaps import BasemapColorMode


class BasemapOut(BaseModel):
    id: str
    label: str
    style_url: str | None
    color_mode: BasemapColorMode
    attribution: str | None
    export_allowed: bool
