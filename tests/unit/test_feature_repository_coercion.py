from decimal import Decimal

from app.infrastructure.database.repositories.feature_repository import (
    _coerce_area_m2,
    _coerce_bool,
    _coerce_decimal,
    _coerce_nonnegative_decimal,
)

_M2 = chr(0x6D) + chr(0xB2)  # "m" + SUPERSCRIPT TWO ("m²") - avoids a literal special char


class TestCoerceBool:
    def test_passes_through_real_booleans(self) -> None:
        assert _coerce_bool(True) is True
        assert _coerce_bool(False) is False

    def test_coerces_numeric_zero_and_one(self) -> None:
        assert _coerce_bool(1) is True
        assert _coerce_bool(0) is False
        assert _coerce_bool(1.0) is True

    def test_coerces_common_text_tokens_case_and_accent_insensitively(self) -> None:
        n_with_tilde = "n" + chr(0xE3) + "o"  # "não"
        assert _coerce_bool("1") is True
        assert _coerce_bool("true") is True
        assert _coerce_bool("Sim") is True
        assert _coerce_bool("0") is False
        assert _coerce_bool("FALSE") is False
        assert _coerce_bool(n_with_tilde) is False
        assert _coerce_bool(n_with_tilde.upper()) is False

    def test_unrecognized_value_returns_none(self) -> None:
        assert _coerce_bool("talvez") is None
        assert _coerce_bool(None) is None
        assert _coerce_bool("") is None


class TestCoerceDecimal:
    def test_parses_numeric_strings(self) -> None:
        assert _coerce_decimal("4110.16406585") == Decimal("4110.16406585")

    def test_parses_native_numbers(self) -> None:
        assert _coerce_decimal(1500) == Decimal("1500")
        assert _coerce_decimal(1500.5) == Decimal("1500.5")

    def test_none_and_unparseable_return_none(self) -> None:
        assert _coerce_decimal(None) is None
        assert _coerce_decimal("nao-e-um-numero") is None
        assert _coerce_decimal("") is None


class TestCoerceNonnegativeDecimal:
    def test_accepts_zero_and_positive_values(self) -> None:
        assert _coerce_nonnegative_decimal(0) == Decimal("0")
        assert _coerce_nonnegative_decimal("3.42") == Decimal("3.42")

    def test_rejects_negative_and_invalid_values(self) -> None:
        assert _coerce_nonnegative_decimal(-0.1) is None
        assert _coerce_nonnegative_decimal("invalido") is None


class TestCoerceAreaM2:
    """Nota 53/54 checkpoint: only a plain number or the exact confirmed
    unit suffix are accepted - any other unit or text becomes `None` with a
    warning, never an automatic conversion."""

    def test_none_is_absent_not_a_warning(self) -> None:
        assert _coerce_area_m2(None) == (None, None)

    def test_plain_number_needs_no_unit(self) -> None:
        assert _coerce_area_m2(1338.63) == (Decimal("1338.63"), None)
        assert _coerce_area_m2("450") == (Decimal("450"), None)

    def test_accepts_the_confirmed_unit_suffix(self) -> None:
        value, warning = _coerce_area_m2(f"1338.63 {_M2}")
        assert value == Decimal("1338.63")
        assert warning is None

    def test_tolerates_extra_whitespace_around_the_suffix(self) -> None:
        value, warning = _coerce_area_m2(f"  1338.63   {_M2}  ")
        assert value == Decimal("1338.63")
        assert warning is None

    def test_rejects_other_units_with_a_warning_instead_of_converting(self) -> None:
        value, warning = _coerce_area_m2("1338.63 ha")
        assert value is None
        assert warning is not None
        assert "1338.63 ha" in warning

    def test_rejects_unparseable_text_with_a_warning(self) -> None:
        value, warning = _coerce_area_m2("nao-e-uma-area")
        assert value is None
        assert warning is not None

    def test_suffix_with_no_number_is_a_warning_not_a_crash(self) -> None:
        value, warning = _coerce_area_m2(_M2)
        assert value is None
        assert warning is not None
