from app.domain.analysis.exceptions import AnalysisError


class MapDocumentContextError(AnalysisError):
    """A MapDocument references a layer/indicator/field that doesn't exist
    or isn't compatible, checked against real DB state (ADR 014, Decisao 3:
    layer-version membership, indicator-layer compatibility, property
    field existence). `context["violations"]` carries one entry per
    problem found - collected, not fail-fast, so the client fixes
    everything in one round-trip (same philosophy as Pydantic's own
    structural errors, item 2)."""

    code = "map_document_context_invalid"


class MapDocumentRevisionConflictError(AnalysisError):
    """PUT sent a stale `revision` (ADR 014, Decisao 4/8) - optimistic
    concurrency conflict detected by an atomic `UPDATE ... WHERE id = ...
    AND revision = ...` (never a read-then-compare in Python, which would
    be a lost-update race under concurrent writers). `context` carries
    `document_id`/`expected_revision`/`current_revision`; the caller
    (route, 4.6) already holds the document object - refreshed in place
    to the true current row state before this is raised - and returns it
    as the 409 body."""

    code = "map_document_revision_conflict"


class BasemapNotExportableError(AnalysisError):
    """The document's `basemap_id` resolves in the catalog (Pydantic
    already checked that, `document.py`) but is flagged
    `export_allowed=False` (ADR 014 Decisao 5 - reserved for a provider
    whose license/availability doesn't guarantee reproducibility in an
    archived artifact; no catalog entry sets this today, but the field
    exists precisely for this check, wired up here in Fase 5)."""

    code = "basemap_not_exportable"
