"""Public fixed-policy and invoice-period contracts, without financial arithmetic."""

from dataclasses import FrozenInstanceError
from datetime import date, datetime, timezone
from decimal import Decimal, localcontext
from enum import StrEnum

import pytest

from expense_approval.allowance_policy import (
    AllowancePeriod,
    AllowancePeriodKind,
    AllowancePolicy,
    get_allowance_period,
    get_allowance_policy,
)
from expense_approval.claim_input import ReimbursementCategory

POLICY_CASES = [
    (ReimbursementCategory.WELLNESS, "30000", AllowancePeriodKind.ANNUAL),
    (ReimbursementCategory.SMARTPHONE, "100000", AllowancePeriodKind.ANNUAL),
    (ReimbursementCategory.BROADBAND, "3000", AllowancePeriodKind.MONTHLY),
    (ReimbursementCategory.MOBILE_BILL, "750", AllowancePeriodKind.MONTHLY),
    (ReimbursementCategory.BUSINESS_HOTEL, None, None),
    (ReimbursementCategory.BUSINESS_TRANSPORT, None, None),
]
CAPPED_CASES = POLICY_CASES[:4]
UNCAPPED_CATEGORIES = [
    ReimbursementCategory.BUSINESS_HOTEL,
    ReimbursementCategory.BUSINESS_TRANSPORT,
]


@pytest.mark.parametrize(("category", "cap_text", "kind"), POLICY_CASES)
def test_all_policy_mappings(category, cap_text, kind):
    policy = get_allowance_policy(category)

    assert isinstance(policy, AllowancePolicy)
    assert policy.category is category
    assert policy.period_kind is kind
    if cap_text is None:
        assert policy.cap is None
    else:
        assert isinstance(policy.cap, Decimal)
        assert policy.cap.as_tuple() == Decimal(cap_text).as_tuple()


def test_policy_cases_cover_exactly_the_existing_categories():
    assert {category for category, _, _ in POLICY_CASES} == set(ReimbursementCategory)


@pytest.mark.parametrize(("category", "cap_text", "kind"), CAPPED_CASES)
@pytest.mark.parametrize(
    ("invoice_date", "year", "month"),
    [
        (date(2026, 1, 1), 2026, 1),
        (date(2026, 1, 15), 2026, 1),
        (date(2026, 1, 31), 2026, 1),
        (date(2026, 2, 1), 2026, 2),
        (date(2026, 2, 28), 2026, 2),
        (date(2026, 3, 1), 2026, 3),
        (date(2026, 4, 30), 2026, 4),
        (date(2026, 5, 1), 2026, 5),
        (date(2026, 6, 15), 2026, 6),
        (date(2026, 12, 31), 2026, 12),
        (date(2027, 1, 1), 2027, 1),
        (date(2024, 2, 28), 2024, 2),
        (date(2024, 2, 29), 2024, 2),
        (date(2024, 3, 1), 2024, 3),
        (date.min, 1, 1),
        (date.max, 9999, 12),
    ],
)
def test_invoice_calendar_periods(category, cap_text, kind, invoice_date, year, month):
    period = get_allowance_period(category, invoice_date)

    assert isinstance(period, AllowancePeriod)
    assert period.kind is kind
    assert period.year == year
    assert period.month == (month if kind is AllowancePeriodKind.MONTHLY else None)


@pytest.mark.parametrize("category", UNCAPPED_CATEGORIES)
@pytest.mark.parametrize("invoice_date", [date.min, date(2024, 2, 29), date.max])
def test_uncapped_categories_have_no_period(category, invoice_date):
    assert get_allowance_period(category, invoice_date) is None


class InvoiceDate(date):
    pass


@pytest.mark.parametrize("category", list(ReimbursementCategory))
def test_date_subclasses_are_accepted(category):
    invoice_date = InvoiceDate(2024, 2, 29)

    assert get_allowance_period(category, invoice_date) == get_allowance_period(
        category, date(2024, 2, 29)
    )


class ForeignCategory(StrEnum):
    WELLNESS = "WELLNESS"


INVALID_CATEGORIES = [
    *(category.value for category in ReimbursementCategory),
    "OTHER",
    "UNKNOWN",
    "wellness",
    "",
    ForeignCategory.WELLNESS,
    None,
    True,
    False,
    1,
    1.0,
    b"WELLNESS",
    [],
    {},
]


@pytest.mark.parametrize("category", INVALID_CATEGORIES)
def test_category_types_are_rejected_by_both_functions(category):
    with pytest.raises(TypeError) as policy_error:
        get_allowance_policy(category)
    assert str(policy_error.value) == "Category must be a ReimbursementCategory."

    with pytest.raises(TypeError) as period_error:
        get_allowance_period(category, date(2026, 1, 1))
    assert str(period_error.value) == "Category must be a ReimbursementCategory."


@pytest.mark.parametrize("category", list(ReimbursementCategory))
@pytest.mark.parametrize(
    "invoice_date",
    [
        "2026-01-01",
        "2026-02-30",
        "",
        0,
        1798761600,
        1798761600.0,
        None,
        True,
        False,
        b"2026-01-01",
        [],
        {},
        datetime(2026, 1, 1),
        datetime(2026, 1, 1, tzinfo=timezone.utc),
    ],
)
def test_invalid_date_types_are_rejected_including_uncapped(category, invoice_date):
    with pytest.raises(TypeError) as error:
        get_allowance_period(category, invoice_date)
    assert str(error.value) == "Invoice date must be a date without a time component."


@pytest.mark.parametrize("category", INVALID_CATEGORIES)
def test_category_error_precedes_invalid_date_error(category):
    with pytest.raises(TypeError) as error:
        get_allowance_period(category, None)
    assert str(error.value) == "Category must be a ReimbursementCategory."


@pytest.mark.parametrize("category", list(ReimbursementCategory))
@pytest.mark.parametrize("field", ["category", "cap", "period_kind"])
@pytest.mark.parametrize("operation", [setattr, delattr])
def test_policy_records_are_frozen(category, field, operation):
    policy = get_allowance_policy(category)
    before = (policy.category, policy.cap, policy.period_kind)

    with pytest.raises(FrozenInstanceError):
        if operation is setattr:
            operation(policy, field, None)
        else:
            operation(policy, field)

    current = get_allowance_policy(category)
    assert (current.category, current.cap, current.period_kind) == before


@pytest.mark.parametrize(("category", "cap_text", "kind"), CAPPED_CASES)
@pytest.mark.parametrize("field", ["kind", "year", "month"])
@pytest.mark.parametrize("operation", [setattr, delattr])
def test_period_records_are_frozen(category, cap_text, kind, field, operation):
    period = get_allowance_period(category, date(2026, 1, 15))
    before = (period.kind, period.year, period.month)

    with pytest.raises(FrozenInstanceError):
        if operation is setattr:
            operation(period, field, None)
        else:
            operation(period, field)

    assert get_allowance_period(category, date(2026, 1, 15)) == period
    assert (period.kind, period.year, period.month) == before


def test_constants_are_exact_under_low_precision_without_context_changes():
    with localcontext() as context:
        context.prec = 2
        context.clear_flags()
        before = repr(context)

        for category, cap_text, kind in POLICY_CASES:
            policy = get_allowance_policy(category)
            assert policy.period_kind is kind
            if cap_text is None:
                assert policy.cap is None
            else:
                assert policy.cap.as_tuple() == Decimal(cap_text).as_tuple()
            get_allowance_period(category, date(2026, 1, 15))

        assert repr(context) == before
