"""Fixed allowance policies and exact assessment; no financial enforcement."""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, localcontext
from enum import StrEnum
from types import MappingProxyType

from expense_approval.claim_input import ReimbursementCategory
from expense_approval.validation import parse_money

type MoneyInput = str | Decimal | int


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


class AllowanceOutcome(StrEnum):
    """Financial comparisons, not claim statuses or reimbursement approval."""

    WITHIN_ALLOWANCE = "WITHIN_ALLOWANCE"
    EXCEEDS_ALLOWANCE = "EXCEEDS_ALLOWANCE"
    UNCAPPED = "UNCAPPED"


@dataclass(frozen=True)
class AllowanceAssessment:
    """Supplied amounts and remaining INR before the request; no reservation."""

    category: ReimbursementCategory
    period: AllowancePeriod | None
    requested: Decimal
    cap: Decimal | None
    consumed: Decimal | None
    remaining: Decimal | None
    outcome: AllowanceOutcome


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


def assess_allowance(
    category: ReimbursementCategory,
    invoice_date: date,
    requested: MoneyInput,
    consumed: MoneyInput | None,
) -> AllowanceAssessment:
    """Assess caller-supplied consumption without database or lifecycle checks.

    Validate category, date, request, then consumption. Capped consumption must
    be finite, nonnegative and exactly representable in paise; uncapped policies
    require None. Parsed input representations are retained. Remaining allowance
    is cap minus consumption, never reduced by this request or clamped to zero.
    """
    period = get_allowance_period(category, invoice_date)
    policy = get_allowance_policy(category)
    # Isolate parsing flags and make malformed-text errors independent of the
    # caller's InvalidOperation trap. Exact calculations need no Decimal context.
    with localcontext() as context:
        context.traps[InvalidOperation] = True
        requested_amount = parse_money(requested)
        if policy.cap is None:
            if consumed is not None:
                raise ValueError(
                    "Consumed allowance must be None for an uncapped policy."
                )
            return AllowanceAssessment(
                category,
                period,
                requested_amount,
                None,
                None,
                None,
                AllowanceOutcome.UNCAPPED,
            )
        if consumed is None:
            raise ValueError("Capped policies require a consumed amount.")
        consumed_amount = _parse_consumed_amount(consumed)

    remaining_paise = _amount_to_paise(policy.cap) - _amount_to_paise(consumed_amount)
    outcome = (
        AllowanceOutcome.WITHIN_ALLOWANCE
        if _amount_to_paise(requested_amount) <= remaining_paise
        else AllowanceOutcome.EXCEEDS_ALLOWANCE
    )
    return AllowanceAssessment(
        category,
        period,
        requested_amount,
        policy.cap,
        consumed_amount,
        _paise_to_decimal(remaining_paise),
        outcome,
    )


def _parse_consumed_amount(value: MoneyInput) -> Decimal:
    """Validate the nonnegative input domain within the caller's local context."""
    if isinstance(value, bool) or not isinstance(value, (str, Decimal, int)):
        raise ValueError(
            "Consumed allowance must be decimal text, a Decimal, or an integer."
        )
    try:
        amount = value if isinstance(value, Decimal) else Decimal(value)
    except (InvalidOperation, ValueError):
        raise ValueError("Consumed allowance must be a valid decimal amount.") from None
    if not amount.is_finite() or amount < 0:
        raise ValueError(
            "Consumed allowance must be finite and greater than or equal to zero."
        )
    parts = amount.as_tuple()
    extra_places = -int(parts.exponent) - 2
    if extra_places > 0 and any(parts.digits[-extra_places:]):
        raise ValueError("Money must be exactly representable with two decimal places.")
    return amount


def _amount_to_paise(amount: Decimal) -> int:
    """Convert validated nonnegative INR exactly, without integer/string limits."""
    if amount.is_zero():
        return 0
    parts = amount.as_tuple()
    shift = int(parts.exponent) + 2
    digits = parts.digits if shift >= 0 else parts.digits[:shift]
    coefficient = 0
    for digit in digits:
        coefficient = coefficient * 10 + digit
    return coefficient * 10**shift if shift > 0 else coefficient


def _paise_to_decimal(paise: int) -> Decimal:
    """Construct signed INR with two places, including canonical positive zero."""
    parts = Decimal(paise).as_tuple()
    return Decimal((parts.sign, parts.digits, -2))
