"""Land-use taxonomy for the MVP (domain decision, 2026-07-17 - see Obsidian
note 12 for the literature references and full reasoning). Aliases resolve
case/accent variation defensively even though source terms are meant to be
pre-set/closed at export time (never free text).
"""

import unicodedata
from enum import StrEnum


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


def normalize_land_use_key(text: str) -> str:
    """Lowercase and strip accents, so lookup is robust to export-tool case
    or encoding quirks without having to enumerate every accented variant.
    """
    decomposed = unicodedata.normalize("NFKD", text.strip().lower())
    return "".join(character for character in decomposed if not unicodedata.combining(character))


LAND_USE_ALIASES: dict[str, LandUseCategory] = {
    normalize_land_use_key(category.value): category for category in LandUseCategory
}
