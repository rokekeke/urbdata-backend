from app.domain.analysis.definitions import IndicatorDefinition
from app.domain.analysis.exceptions import IndicatorDependencyError


def resolve_dependencies(
    definitions: tuple[IndicatorDefinition, ...],
) -> tuple[IndicatorDefinition, ...]:
    """Return a deterministic topological order and reject missing dependencies or cycles."""
    by_code = {definition.code: definition for definition in definitions}
    ordered: list[IndicatorDefinition] = []
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(code: str) -> None:
        if code in visited:
            return
        if code in visiting:
            raise IndicatorDependencyError(
                "Indicator dependency cycle detected.", context={"code": code}
            )
        try:
            definition = by_code[code]
        except KeyError as exc:
            raise IndicatorDependencyError(
                "Indicator dependency is not available.", context={"code": code}
            ) from exc
        visiting.add(code)
        for dependency in sorted(definition.dependencies):
            visit(dependency)
        visiting.remove(code)
        visited.add(code)
        ordered.append(definition)

    for indicator_code in sorted(by_code):
        visit(indicator_code)
    return tuple(ordered)
