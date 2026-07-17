from app.domain.indicators.catalog import build_registry


def test_registry_has_the_territorial_indicators_registered() -> None:
    registry = build_registry()

    definitions = registry.by_theme("territorial")

    assert {d.code for d in definitions} == {
        "territorial.total_area",
        "territorial.perimeter",
        "territorial.compactness",
    }


def test_build_registry_is_cached() -> None:
    assert build_registry() is build_registry()
