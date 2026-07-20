"""HTTP schemas for the MapDocument CRUD (item 4.6, ADR 014 Decisao 8).

Request bodies are nested (`{"name": ..., "config": {...}}`, nota Obsidian
39): `name` is the repository's own listing column (`MapDocumentRepository.
create`/`update`), independent of `MapDocumentConfig.name` (an "internal
name" field inside the payload itself, ADR 014 Decisao 2) - the two are
never compared or synced, same as the repository/tests already treat them.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.cartography.contextual_validation import IntegrityWarning
from app.domain.cartography.document import MapDocumentConfig, upcast_document
from app.infrastructure.database.models.map_document import MapDocument


class MapDocumentCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    config: MapDocumentConfig


class MapDocumentUpdateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    config: MapDocumentConfig
    expected_revision: int = Field(ge=1)


class MapDocumentOut(BaseModel):
    id: uuid.UUID
    project_version_id: uuid.UUID
    name: str
    config: MapDocumentConfig
    revision: int
    schema_version: str
    created_at: datetime
    updated_at: datetime


class IntegrityWarningOut(BaseModel):
    layer_id: uuid.UUID
    code: str
    message: str


class MapDocumentWithWarningsOut(MapDocumentOut):
    """Only the single-item GET carries this (ADR 014, Decisao 8) - the
    list route stays cheap, without a diagnostic pass per document."""

    integrity_warnings: list[IntegrityWarningOut]


def map_document_to_out(document: MapDocument) -> MapDocumentOut:
    return MapDocumentOut(
        id=document.id,
        project_version_id=document.project_version_id,
        name=document.name,
        config=MapDocumentConfig.model_validate(upcast_document(document.config)),
        revision=document.revision,
        schema_version=document.schema_version,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


def map_document_with_warnings_to_out(
    document: MapDocument, warnings: list[IntegrityWarning]
) -> MapDocumentWithWarningsOut:
    return MapDocumentWithWarningsOut(
        id=document.id,
        project_version_id=document.project_version_id,
        name=document.name,
        config=MapDocumentConfig.model_validate(upcast_document(document.config)),
        revision=document.revision,
        schema_version=document.schema_version,
        created_at=document.created_at,
        updated_at=document.updated_at,
        integrity_warnings=[
            IntegrityWarningOut(
                layer_id=warning.layer_id, code=warning.code, message=warning.message
            )
            for warning in warnings
        ],
    )
