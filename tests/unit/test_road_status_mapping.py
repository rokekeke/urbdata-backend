from app.config.road_hierarchy_mapping import RoadStatus, resolve_road_status


def test_resolves_existing_and_proposed_aliases() -> None:
    assert resolve_road_status("Existente") is RoadStatus.EXISTING
    assert resolve_road_status("VIA PROJETADA") is RoadStatus.PROPOSED
    assert resolve_road_status("nova") is RoadStatus.PROPOSED


def test_unknown_status_is_not_guessed() -> None:
    assert resolve_road_status(None) is None
    assert resolve_road_status("") is None
    assert resolve_road_status("talvez") is None
