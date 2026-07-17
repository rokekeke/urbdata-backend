from app.domain.indicators.catalog import build_registry


def test_registry_has_the_territorial_indicators_registered() -> None:
    registry = build_registry()

    definitions = registry.by_theme("territorial")

    assert {d.code for d in definitions} == {
        "territorial.total_area",
        "territorial.perimeter",
        "territorial.compactness",
        "territorial.area_by_category",
        "territorial.percent_by_category",
    }


def test_build_registry_is_cached() -> None:
    assert build_registry() is build_registry()


def test_registry_has_the_road_network_indicators_registered() -> None:
    definitions = build_registry().by_theme("road_network")

    assert {definition.code for definition in definitions} == {
        "road_network.total_length",
        "road_network.existing_length",
        "road_network.proposed_length",
        "road_network.intersection_count",
        "road_network.intersection_density",
        "road_network.link_node_ratio",
        "road_network.proposed_connection_count",
    }
    assert all("sistema_viario" in definition.required_layers for definition in definitions)
    assert all("desconexoes_viarias" in definition.optional_layers for definition in definitions)


def test_registry_has_the_minimum_density_indicators_registered() -> None:
    definitions = build_registry().by_theme("density")

    assert {definition.code for definition in definitions} == {
        "density.max_computable_area",
        "density.lot_count_with_ca",
        "density.ca_coverage",
    }
    assert all(definition.required_layers == ("territorio",) for definition in definitions)
