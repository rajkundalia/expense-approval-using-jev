"""Exact-money and contextual date validation without persistence or model calls."""

from datetime import date, datetime, timedelta
from decimal import Decimal, localcontext

import pytest

from expense_approval.clock import business_date
from expense_approval.validation import parse_money, validate_invoice_date


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


@pytest.mark.parametrize(
    ("reference", "lower_bound"),
    [
        (date(2026, 10, 15), date(2026, 7, 15)),
        (date(2026, 10, 31), date(2026, 7, 31)),
        (date(2026, 5, 31), date(2026, 2, 28)),
        (date(2024, 5, 31), date(2024, 2, 29)),
        (date(2026, 1, 31), date(2025, 10, 31)),
    ],
)
def test_invoice_window_includes_exact_bounds_and_rejects_adjacent_dates(
    reference: date, lower_bound: date
) -> None:
    assert validate_invoice_date(lower_bound, reference) is None
    assert validate_invoice_date(reference, reference) is None
    assert validate_invoice_date(lower_bound + timedelta(days=1), reference) is None

    with pytest.raises(ValueError, match=f"too old.*{lower_bound.isoformat()}"):
        validate_invoice_date(lower_bound - timedelta(days=1), reference)
    with pytest.raises(ValueError, match="after the original submission date"):
        validate_invoice_date(reference + timedelta(days=1), reference)


@pytest.mark.parametrize(
    ("reference", "invoice_date", "eligible"),
    [
        (date(2026, 10, 31), date(2026, 7, 31), True),  # 92 days, eligible.
        (date(2026, 5, 1), date(2026, 1, 31), False),  # 90 days, too old.
    ],
)
def test_calendar_months_are_not_a_ninety_day_window(
    reference: date, invoice_date: date, eligible: bool
) -> None:
    if eligible:
        assert validate_invoice_date(invoice_date, reference) is None
    else:
        with pytest.raises(ValueError, match="too old"):
            validate_invoice_date(invoice_date, reference)


def test_initial_and_revision_calls_retain_original_submission_date() -> None:
    original_submission_date = business_date(
        lambda: datetime.fromisoformat("2026-10-31T18:30:00+00:00")
    )
    invoice_date = date(2026, 8, 1)
    assert validate_invoice_date(invoice_date, original_submission_date) is None

    revision_date = business_date(
        lambda: datetime.fromisoformat("2027-03-15T12:00:00+00:00")
    )
    assert revision_date > original_submission_date
    assert validate_invoice_date(invoice_date, original_submission_date) is None
    assert validate_invoice_date(date(2026, 9, 15), original_submission_date) is None

    with pytest.raises(ValueError, match="too old"):
        validate_invoice_date(date(2026, 7, 31), original_submission_date)

    corrected_date = date(2026, 12, 1)
    assert corrected_date < revision_date
    with pytest.raises(ValueError, match="after the original submission date"):
        validate_invoice_date(corrected_date, original_submission_date)

    # A new initial submission on the later date has its own reference window.
    assert validate_invoice_date(revision_date, revision_date) is None
    with pytest.raises(ValueError, match="too old"):
        validate_invoice_date(invoice_date, revision_date)
