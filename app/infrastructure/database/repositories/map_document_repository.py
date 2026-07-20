"""MapDocument persistence adapter (ADR 014).

create/get/list/update/delete (items 4.2/4.3/4.4/4.5) - no HTTP route yet
(4.6). `create`/`update` enforce the contextual validation item 2
explicitly deferred to this layer (layer belongs to the version, indicator
compatible with the layer's type, property field exists, mode compatible
with the field's or indicator's actual value type) before persisting - a
config that passes Pydantic (item 2) can still be rejected here (ADR 014,
Decisao 3).

`create`/`list_for_version` trust the caller already resolved
`project_version_id` via `ProjectRepository.get_version_for_project` -
this repository does not re-check project ownership for those two, only
`get_for_project` does (its URL has no version_id to scope by, ADR 014
Decisao 8).
"""

import dataclasses
import uuid
from typing import cast

from sqlalchemy import CursorResult
from sqlalchemy import update as sa_update
from sqlalchemy.orm import Session

from app.domain.cartography.contextual_validation import (
    ContextViolation,
    IntegrityWarning,
    LayerContext,
    compute_integrity_warnings,
    references_property_field,
    validate_document_context,
)
from app.domain.cartography.document import MapDocumentConfig, upcast_document
from app.domain.cartography.exceptions import (
    MapDocumentContextError,
    MapDocumentRevisionConflictError,
)
from app.domain.cartography.representation_options import FieldStats
from app.infrastructure.database.models.map_document import MapDocument
from app.infrastructure.database.models.version import ProjectVersion
from app.infrastructure.database.repositories.feature_repository import FeatureRepository


def _raise_if_invalid(
    violations: list[ContextViolation],
) -> None:
    if violations:
        raise MapDocumentContextError(
            "Documento referencia camadas, indicadores ou campos invalidos.",
            context={"violations": [dataclasses.asdict(v) for v in violations]},
        )


def build_layer_contexts(
    feature_repository: FeatureRepository,
    project_version_id: uuid.UUID,
    config: MapDocumentConfig,
) -> dict[uuid.UUID, LayerContext]:
    """Fetch just enough DB state to validate `config` against
    `project_version_id`: the type of every layer the document references
    (to know if it belongs to this version at all), and per-field
    aggregates only for layers actually used with a `source=property`
    reference - never queries a layer the document doesn't touch, and
    never aggregates fields a layer's references don't need."""
    layer_types = {
        layer.id: layer.layer_type.value
        for layer in feature_repository.list_layers(project_version_id)
    }
    contexts: dict[uuid.UUID, LayerContext] = {}
    for document_layer in config.layers:
        layer_type = layer_types.get(document_layer.layer_id)
        if layer_type is None:
            continue  # not in this version - validate_document_context reports it
        fields: dict[str, FieldStats] = {}
        if references_property_field(document_layer):
            stats = feature_repository.aggregate_representation_stats(
                document_layer.layer_id
            )
            fields = {stat.field: stat for stat in stats}
        contexts[document_layer.layer_id] = LayerContext(layer_type=layer_type, fields=fields)
    return contexts


class MapDocumentRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        *,
        project_version_id: uuid.UUID,
        name: str,
        config: MapDocumentConfig,
        layer_contexts: dict[uuid.UUID, LayerContext],
    ) -> MapDocument:
        _raise_if_invalid(validate_document_context(config, layer_contexts))

        document = MapDocument(
            project_version_id=project_version_id,
            name=name,
            config=config.model_dump(mode="json"),
            schema_version=config.schema_version,
        )
        self._session.add(document)
        self._session.commit()
        self._session.refresh(document)
        return document

    def update(
        self,
        document: MapDocument,
        *,
        expected_revision: int,
        name: str,
        config: MapDocumentConfig,
        layer_contexts: dict[uuid.UUID, LayerContext],
    ) -> MapDocument:
        """Optimistic concurrency (ADR 014, Decisao 4/8): a single atomic
        `UPDATE ... WHERE id = ... AND revision = ...` - never a
        read-then-compare in Python, which would be a lost-update race
        under concurrent writers (two PUTs both reading revision=N would
        both "pass" a Python-side check). Contextual validation (4.3) runs
        before the UPDATE is even attempted, so an invalid config never
        touches the row - the previous valid revision survives untouched.

        On conflict, `document` is refreshed in place to the row's true
        current state (which may have moved past what the caller
        originally fetched) before raising, so the caller (route, 4.6)
        already holds what belongs in the 409 body without a second
        query."""
        _raise_if_invalid(validate_document_context(config, layer_contexts))

        result = cast(
            "CursorResult[object]",
            self._session.execute(
                sa_update(MapDocument)
                .where(MapDocument.id == document.id, MapDocument.revision == expected_revision)
                .values(
                    name=name,
                    config=config.model_dump(mode="json"),
                    schema_version=config.schema_version,
                    revision=MapDocument.revision + 1,
                )
            ),
        )
        if result.rowcount == 0:
            self._session.refresh(document)
            raise MapDocumentRevisionConflictError(
                "Revisao desatualizada - o documento foi alterado por outra escrita.",
                context={
                    "document_id": str(document.id),
                    "expected_revision": expected_revision,
                    "current_revision": document.revision,
                },
            )
        self._session.commit()
        self._session.refresh(document)
        return document

    def list_for_version(self, project_version_id: uuid.UUID) -> list[MapDocument]:
        return list(
            self._session.query(MapDocument)
            .filter(MapDocument.project_version_id == project_version_id)
            .order_by(MapDocument.created_at.desc())
            .all()
        )

    def get_for_project(
        self, project_id: uuid.UUID, document_id: uuid.UUID
    ) -> MapDocument | None:
        """`None` when the document doesn't exist or belongs to a
        different project - the route (4.6) turns that into a 404 without
        distinguishing the two (same pattern as
        `AnalysisRepository.get_run_for_project`)."""
        return (
            self._session.query(MapDocument)
            .join(ProjectVersion, MapDocument.project_version_id == ProjectVersion.id)
            .filter(MapDocument.id == document_id, ProjectVersion.project_id == project_id)
            .first()
        )

    def get_with_integrity_warnings(
        self,
        project_id: uuid.UUID,
        document_id: uuid.UUID,
        feature_repository: FeatureRepository,
    ) -> tuple[MapDocument, list[IntegrityWarning]] | None:
        """Read-time diagnostic (ADR 014, Decisao 8, checkpoint 4.1b):
        `None` only when the document itself doesn't exist/isn't owned by
        `project_id` (same as `get_for_project`) - once found, this NEVER
        fails and NEVER silently rewrites the stored config (regra 2),
        even when a referenced layer was deleted or the quadras layer got
        re-derived with a new id (ADR 009's orphaning trap). `warnings` is
        computed fresh on every call, never persisted."""
        document = self.get_for_project(project_id, document_id)
        if document is None:
            return None
        config = MapDocumentConfig.model_validate(upcast_document(document.config))
        layer_contexts = build_layer_contexts(
            feature_repository, document.project_version_id, config
        )
        warnings = compute_integrity_warnings(config, layer_contexts)
        return document, warnings

    def delete(self, document: MapDocument) -> None:
        """Hard delete (ADR 014, Decisao 8): export snapshots copy the
        composition by value (Decisao 6) and there is no real FK from
        `exports` to `map_documents`, so removing a document never
        invalidates an export already produced. No `deleted_at`, no
        filtered-read overhead anywhere else in this repository."""
        self._session.delete(document)
        self._session.commit()
