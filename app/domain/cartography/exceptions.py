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
