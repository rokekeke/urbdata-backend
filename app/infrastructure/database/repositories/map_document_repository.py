"""MapDocument persistence adapter (ADR 014).

create/get/list only (item 4.2/4.3) - no update/delete yet (4.4/4.5).
`create` enforces the contextual validation item 2 explicitly deferred to
this layer (layer belongs to the version, indicator compatible with the
layer's type, property field exists, mode compatible with the field's or
indicator's actual value type) before persisting - a config that passes
Pydantic (item 2) can still be rejected here (ADR 014, Decisao 3).

`create`/`list_for_version` trust the caller already resolved
`project_version_id` via `ProjectRepository.get_version_for_project` -
this repository does not re-check project ownership for those two, only
`get_for_project` does (its URL has no version_id to scope by, ADR 014
Decisao 8).
"""

import dataclasses
import uuid

from sqlalchemy.orm import Session

from app.domain.cartography.contextual_validation import (
    LayerContext,
    references_property_field,
    validate_document_context,
)
from app.domain.cartography.document import MapDocumentConfig
from app.domain.cartography.exceptions import MapDocumentContextError
from app.domain.cartography.representation_options import FieldStats
from app.infrastructure.database.models.map_document import MapDocument
from app.infrastructure.database.models.version import ProjectVersion
from app.infrastructure.database.repositories.feature_repository import FeatureRepository


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
        violations = validate_document_context(config, layer_contexts)
        if violations:
            raise MapDocumentContextError(
                "Documento referencia camadas, indicadores ou campos invalidos.",
                context={"violations": [dataclasses.asdict(v) for v in violations]},
            )

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
