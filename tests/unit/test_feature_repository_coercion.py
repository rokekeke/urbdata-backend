from decimal import Decimal

from app.infrastructure.database.repositories.feature_repository import (
    _coerce_bool,
    _coerce_decimal,
    _coerce_nonnegative_decimal,
)


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
