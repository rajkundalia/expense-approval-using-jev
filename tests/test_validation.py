"""Exact-money behavior without clocks, persistence or model calls."""

from decimal import Decimal, localcontext

import pytest

from expense_approval.validation import parse_money


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("12.34", "12.34"),
        ("12.340", "12.340"),
        ("12.0000", "12.0000"),
        (Decimal("12.340"), "12.340"),
        (12, "12"),
        ("0.01", "0.01"),
        ("0.01000", "0.01000"),
        ("1e2", "1E+2"),
        ("123456789012345678901234567890.1200", "123456789012345678901234567890.1200"),
    ],
)
def test_valid_money_is_exact_and_retains_trailing_zeros(
    value: object, expected: str
) -> None:
    amount = parse_money(value)

    assert isinstance(amount, Decimal)
    assert amount.as_tuple() == Decimal(expected).as_tuple()


@pytest.mark.parametrize(
    "value",
    [
        12.34,
        True,
        False,
        None,
        [],
        "",
        " \t\n",
        "not-a-number",
        "12..34",
        "INR 12.34",
        0,
        "0.00",
        Decimal("-0"),
        -1,
        "-0.01",
        "NaN",
        Decimal("sNaN"),
        "Infinity",
        Decimal("-Infinity"),
        "12.345",
        "12.001",
        Decimal("0.0001"),
    ],
)
def test_invalid_money_is_rejected(value: object) -> None:
    with pytest.raises(ValueError):
        parse_money(value)


def test_precision_validation_does_not_depend_on_decimal_context() -> None:
    exact_amount = Decimal("123456789012345678901234567890.1200")
    rounding_required = Decimal("123456789012345678901234567890.1201")

    with localcontext() as decimal_context:
        decimal_context.prec = 3

        assert parse_money(exact_amount).as_tuple() == exact_amount.as_tuple()
        with pytest.raises(ValueError):
            parse_money(rounding_required)
