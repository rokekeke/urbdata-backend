"""OpenAPI schema for the unified error envelope (Fase 1, nota 28).

Every HTTPException raised by the API carries `{error, message, context}`
in `detail` (see `app.api.v1.errors.error_detail`). Declaring the envelope
here lets routes document their 4xx responses so the generated TypeScript
client types the error path too. FastAPI's own request-validation 422 keeps
the framework shape in v1.
"""

from typing import Any

from pydantic import BaseModel


class ErrorDetailOut(BaseModel):
    error: str
    message: str
    context: dict[str, Any]


class ErrorEnvelopeOut(BaseModel):
    detail: ErrorDetailOut


# Reusable `responses=` fragments for route decorators, typed to match
# FastAPI's expected `dict[int | str, dict[str, Any]]`.
ErrorResponses = dict[int | str, dict[str, Any]]

NOT_FOUND: ErrorResponses = {404: {"model": ErrorEnvelopeOut}}
UNPROCESSABLE: ErrorResponses = {422: {"model": ErrorEnvelopeOut}}
BAD_REQUEST: ErrorResponses = {400: {"model": ErrorEnvelopeOut}}
TOO_LARGE: ErrorResponses = {413: {"model": ErrorEnvelopeOut}}
# First 409 in the API (MapDocument optimistic-concurrency conflict, ADR 014
# Decisao 4/8): stays inside the same envelope as every other 4xx -
# `context.current_document` carries the current MapDocumentOut so the
# client gets it without a second round-trip, without special-casing this
# route in the OpenAPI contract guard (test_openapi_contract.py).
CONFLICT: ErrorResponses = {409: {"model": ErrorEnvelopeOut}}
