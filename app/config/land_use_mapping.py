"""Land-use taxonomy for the MVP (domain decision, 2026-07-17 - see Obsidian
note 12 for the literature references and full reasoning). Aliases resolve
case/accent variation defensively even though source terms are meant to be
pre-set/closed at export time (never free text).
"""

from enum import StrEnum

from app.domain.text_encoding import normalize_key


class LandUseCategory(StrEnum):
    RESIDENCIAL = "residencial"
    COMERCIAL = "comercial"
    SERVICOS = "servicos"
    INSTITUCIONAL = "institucional"
    INDUSTRIAL = "industrial"
    MISTO = "misto"


# A single feature's raw land-use property may list more than one pre-set
# term separated by this delimiter, when a lot already carries more than one
# use tag (see app/domain/indicators/land_use.py::classify_land_use).
LAND_USE_DELIMITER = ";"

# Re-exported under this name for call sites written before normalize_key
# moved to app.domain.text_encoding (shared with app/config/macroarea_mapping.py).
normalize_land_use_key = normalize_key

LAND_USE_ALIASES: dict[str, LandUseCategory] = {
    normalize_land_use_key(category.value): category for category in LandUseCategory
}
