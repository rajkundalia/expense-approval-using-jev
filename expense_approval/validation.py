"""Reusable exact monetary validation; relative date eligibility is separate."""

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
