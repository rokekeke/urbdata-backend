from app.config.macroarea_mapping import Macroarea, resolve_macroarea


def test_resolves_exact_values() -> None:
    assert resolve_macroarea("lote") == Macroarea.LOTE
    assert resolve_macroarea("sistema_viario") == Macroarea.SISTEMA_VIARIO
    assert resolve_macroarea("avl") == Macroarea.AVL
    assert resolve_macroarea("app") == Macroarea.APP
    assert resolve_macroarea("aci") == Macroarea.ACI
    assert resolve_macroarea("nulo") == Macroarea.NULO


def test_is_case_and_whitespace_insensitive() -> None:
    assert resolve_macroarea("Lote") == Macroarea.LOTE
    assert resolve_macroarea("  AVL  ") == Macroarea.AVL
    assert resolve_macroarea("SISTEMA_VIARIO") == Macroarea.SISTEMA_VIARIO


def test_matches_the_human_readable_form_seen_in_real_exports() -> None:
    # The real export file's `Comments` field uses "SISTEMA VIÁRIO" (space,
    # accent, uppercase), not the slug "sistema_viario" - both must resolve
    # to the same category. Built from chr() to avoid a literal accented
    # character in this source file (see tests/unit/test_text_encoding.py).
    a_upper_grave = chr(0xC1)  # "Á"
    human_readable = "SISTEMA VI" + a_upper_grave + "RIO"

    assert resolve_macroarea(human_readable) == Macroarea.SISTEMA_VIARIO


def test_unrecognized_or_missing_returns_none() -> None:
    assert resolve_macroarea(None) is None
    assert resolve_macroarea("") is None
    assert resolve_macroarea("xyz-nao-existe") is None
