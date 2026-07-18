"""Single error-detail shape for every HTTPException raised by the API.

Contract (Fase 0 do roadmap, nota Obsidian 28): `{error, message, context}`.
`context` carries the actionable detail (e.g. which layer_type is missing)
and is always present, even when empty, so clients can rely on the shape.
FastAPI's own request-validation 422s keep the framework format in v1.
"""

from collections.abc import Mapping
from typing import Any


def error_detail(
    code: str, message: str, context: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    return {"error": code, "message": message, "context": dict(context or {})}
