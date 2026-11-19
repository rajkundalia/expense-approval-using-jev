"""Reusable exact monetary and submission-relative invoice-date validation."""

from calendar import monthrange
from datetime import date
from decimal import Decimal, InvalidOperation


def parse_money(value: object) -> Decimal:
    """Parse a positive, finite amount exactly representable in whole paise.

    Floats and booleans are rejected before coercion. Redundant trailing zeros
    are preserved; precision checks never round or use Decimal arithmetic.
    """
    if isinstance(value, bool) or not isinstance(value, (str, Decimal, int)):
        raise ValueError("Money must be decimal text, a Decimal, or an integer.")

    try:
        amount = value if isinstance(value, Decimal) else Decimal(value)
    except (InvalidOperation, ValueError):
        raise ValueError("Money must be a valid decimal amount.") from None

    if not amount.is_finite() or amount <= 0:
        raise ValueError("Money must be finite and greater than zero.")

    decimal_parts = amount.as_tuple()
    extra_places = -int(decimal_parts.exponent) - 2
    if extra_places > 0 and any(decimal_parts.digits[-extra_places:]):
        raise ValueError("Money must be exactly representable with two decimal places.")

    return amount


def validate_invoice_date(invoice_date: date, original_submission_date: date) -> None:
    """Require an invoice within the original submission's three-calendar-month window.

    Both dates must already be structurally validated. The caller supplies the
    trusted business date captured on initial submission, also for corrections.
    Bounds are inclusive; month subtraction clamps to the target month's last day.
    Return None on success, or raise ValueError distinguishing too-old and later
    invoice dates. This function never reads a clock or parses employee input.
    """
    if invoice_date > original_submission_date:
        raise ValueError("Invoice date must not be after the original submission date.")

    target_year, target_month_index = divmod(
        original_submission_date.year * 12 + original_submission_date.month - 1 - 3,
        12,
    )
    target_month = target_month_index + 1
    target_day = min(
        original_submission_date.day, monthrange(target_year, target_month)[1]
    )
    earliest_allowed_date = date(target_year, target_month, target_day)
    if invoice_date < earliest_allowed_date:
        raise ValueError(
            "Invoice date is too old; it must be on or after "
            f"{earliest_allowed_date.isoformat()} (three calendar months before "
            "the original submission date)."
        )
