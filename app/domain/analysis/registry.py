from app.domain.analysis.definitions import IndicatorDefinition
from app.domain.analysis.exceptions import IndicatorDependencyError


class IndicatorRegistry:
    def __init__(self) -> None:
        self._definitions: dict[str, IndicatorDefinition] = {}

    def register(self, definition: IndicatorDefinition) -> None:
        if definition.code in self._definitions:
            raise IndicatorDependencyError(
                "Indicator code is already registered.", context={"code": definition.code}
            )
        self._definitions[definition.code] = definition

    def get(self, code: str) -> IndicatorDefinition:
        try:
            return self._definitions[code]
        except KeyError as exc:
            raise IndicatorDependencyError(
                "Indicator code is not registered.", context={"code": code}
            ) from exc

    def by_theme(self, theme: str) -> tuple[IndicatorDefinition, ...]:
        return tuple(item for item in self._definitions.values() if item.theme == theme)
