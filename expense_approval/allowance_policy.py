"""Fixed allowance metadata and invoice periods; no financial enforcement."""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType

from expense_approval.claim_input import ReimbursementCategory


class AllowancePeriodKind(StrEnum):
    """Calendar frequencies for capped allowances."""

    ANNUAL = "ANNUAL"
    MONTHLY = "MONTHLY"


@dataclass(frozen=True)
class AllowancePolicy:
    """Fixed policy value; cap is INR, or None with no allowance period."""

    category: ReimbursementCategory
    cap: Decimal | None
    period_kind: AllowancePeriodKind | None


@dataclass(frozen=True)
class AllowancePeriod:
    """Invoice calendar key; annual periods have no month.

    The key covers the whole calendar year or month, inclusive. Employee and
    category are separate scopes, not part of this calendar key.
    """

    kind: AllowancePeriodKind
    year: int
    month: int | None


_POLICIES = MappingProxyType(
    {
        ReimbursementCategory.WELLNESS: AllowancePolicy(
            ReimbursementCategory.WELLNESS, Decimal("30000"), AllowancePeriodKind.ANNUAL
        ),
        ReimbursementCategory.SMARTPHONE: AllowancePolicy(
            ReimbursementCategory.SMARTPHONE,
            Decimal("100000"),
            AllowancePeriodKind.ANNUAL,
        ),
        ReimbursementCategory.BROADBAND: AllowancePolicy(
            ReimbursementCategory.BROADBAND,
            Decimal("3000"),
            AllowancePeriodKind.MONTHLY,
        ),
        ReimbursementCategory.MOBILE_BILL: AllowancePolicy(
            ReimbursementCategory.MOBILE_BILL,
            Decimal("750"),
            AllowancePeriodKind.MONTHLY,
        ),
        ReimbursementCategory.BUSINESS_HOTEL: AllowancePolicy(
            ReimbursementCategory.BUSINESS_HOTEL, None, None
        ),
        ReimbursementCategory.BUSINESS_TRANSPORT: AllowancePolicy(
            ReimbursementCategory.BUSINESS_TRANSPORT, None, None
        ),
    }
)


def get_allowance_policy(category: ReimbursementCategory) -> AllowancePolicy:
    """Return fixed metadata for an existing category, without string coercion."""
    if not isinstance(category, ReimbursementCategory):
        raise TypeError("Category must be a ReimbursementCategory.")
    return _POLICIES[category]


def get_allowance_period(
    category: ReimbursementCategory, invoice_date: date
) -> AllowancePeriod | None:
    """Select an invoice-only period, or None for an uncapped policy.

    Validate category before date, including for uncapped categories. Dates may
    be date subclasses, but never datetimes or text. This does not check invoice
    eligibility, read a clock or authorize a claim.
    """
    policy = get_allowance_policy(category)
    if not isinstance(invoice_date, date) or isinstance(invoice_date, datetime):
        raise TypeError("Invoice date must be a date without a time component.")
    if policy.period_kind is None:
        return None
    month = (
        invoice_date.month
        if policy.period_kind is AllowancePeriodKind.MONTHLY
        else None
    )
    return AllowancePeriod(policy.period_kind, invoice_date.year, month)
