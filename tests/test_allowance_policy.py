"""Public policy, invoice-period and exact financial assessment contracts."""

import sys
from dataclasses import FrozenInstanceError
from datetime import date, datetime, timezone
from decimal import (
    ROUND_DOWN,
    ROUND_UP,
    Decimal,
    InvalidOperation,
    Rounded,
    localcontext,
)
from enum import StrEnum

import pytest

from expense_approval.allowance_policy import (
    AllowanceAssessment,
    AllowanceOutcome,
    AllowancePeriod,
    AllowancePeriodKind,
    AllowancePolicy,
    assess_allowance,
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


@pytest.mark.parametrize(
    ("category", "cap", "below", "above"),
    [
        (ReimbursementCategory.WELLNESS, "30000", "29999.99", "30000.01"),
        (ReimbursementCategory.SMARTPHONE, "100000", "99999.99", "100000.01"),
        (ReimbursementCategory.BROADBAND, "3000", "2999.99", "3000.01"),
        (ReimbursementCategory.MOBILE_BILL, "750", "749.99", "750.01"),
    ],
)
def test_capped_assessment_boundaries(category, cap, below, above):
    for requested, consumed, remaining, outcome in [
        (cap, "0", cap, AllowanceOutcome.WITHIN_ALLOWANCE),
        (above, "0", cap, AllowanceOutcome.EXCEEDS_ALLOWANCE),
        ("0.01", below, "0.01", AllowanceOutcome.WITHIN_ALLOWANCE),
        ("0.02", below, "0.01", AllowanceOutcome.EXCEEDS_ALLOWANCE),
        ("0.01", cap, "0.00", AllowanceOutcome.EXCEEDS_ALLOWANCE),
        ("0.01", above, "-0.01", AllowanceOutcome.EXCEEDS_ALLOWANCE),
    ]:
        result = assess_allowance(category, date(2024, 2, 29), requested, consumed)
        assert isinstance(result, AllowanceAssessment)
        assert result.category is category
        assert result.period == get_allowance_period(category, date(2024, 2, 29))
        assert result.cap.as_tuple() == Decimal(cap).as_tuple()
        assert result.requested.as_tuple() == Decimal(requested).as_tuple()
        assert result.consumed.as_tuple() == Decimal(consumed).as_tuple()
        assert result.remaining == Decimal(remaining)
        assert result.remaining.as_tuple().exponent == -2
        assert result.outcome is outcome
        if result.remaining.is_zero():
            assert not result.remaining.is_signed()


@pytest.mark.parametrize("category", UNCAPPED_CATEGORIES)
def test_uncapped_assessment_fields(category):
    requested = Decimal("1e10000")
    result = assess_allowance(category, date.min, requested, None)

    assert result.category is category
    assert result.requested.as_tuple() == requested.as_tuple()
    assert (result.cap, result.period, result.consumed, result.remaining) == (
        None,
        None,
        None,
        None,
    )
    assert result.outcome is AllowanceOutcome.UNCAPPED


@pytest.mark.parametrize(
    "requested", ["12.340", Decimal("12.340"), "12.0000", 12, "1e2", "1e-2"]
)
@pytest.mark.parametrize("consumed", ["0", "0.0000", Decimal("-0"), 0, "0e-999999"])
def test_input_representations_and_zero_consumption(requested, consumed):
    result = assess_allowance(
        ReimbursementCategory.WELLNESS, date(2026, 1, 1), requested, consumed
    )
    assert result.requested.as_tuple() == Decimal(requested).as_tuple()
    assert result.consumed.as_tuple() == Decimal(consumed).as_tuple()
    assert result.remaining.as_tuple() == Decimal("30000.00").as_tuple()
    assert result.outcome is AllowanceOutcome.WITHIN_ALLOWANCE


@pytest.mark.parametrize("consumed", ["12.340", Decimal("12.340"), "1e2", 100])
def test_nonzero_consumption_representations(consumed):
    result = assess_allowance(
        ReimbursementCategory.WELLNESS, date(2026, 1, 1), "1.0000", consumed
    )
    expected = "29987.66" if Decimal(consumed) == Decimal("12.34") else "29900.00"
    assert result.consumed.as_tuple() == Decimal(consumed).as_tuple()
    assert result.remaining.as_tuple() == Decimal(expected).as_tuple()


INVALID_MONEY = [
    (1.0, "type"),
    (True, "type"),
    (False, "type"),
    (b"1", "type"),
    ([], "type"),
    ({}, "type"),
    (object(), "type"),
    ("", "malformed"),
    (" ", "malformed"),
    ("no money", "malformed"),
    ("12..34", "malformed"),
    ("NaN", "domain"),
    (Decimal("sNaN"), "domain"),
    ("Infinity", "domain"),
    (Decimal("-Infinity"), "domain"),
    (-1, "domain"),
    ("-0.01", "domain"),
    ("12.345", "precision"),
    ("12.001", "precision"),
    ("1e-3", "precision"),
]
REQUEST_ERRORS = {
    "type": "Money must be decimal text, a Decimal, or an integer.",
    "malformed": "Money must be a valid decimal amount.",
    "domain": "Money must be finite and greater than zero.",
    "precision": "Money must be exactly representable with two decimal places.",
}
CONSUMED_ERRORS = {
    "type": "Consumed allowance must be decimal text, a Decimal, or an integer.",
    "malformed": "Consumed allowance must be a valid decimal amount.",
    "domain": "Consumed allowance must be finite and greater than or equal to zero.",
    "precision": REQUEST_ERRORS["precision"],
}


@pytest.mark.parametrize(("value", "failure"), INVALID_MONEY)
@pytest.mark.parametrize("field", ["requested", "consumed"])
def test_invalid_money_has_consistent_errors_and_preserves_context(
    value, failure, field
):
    with localcontext() as context:
        context.traps[InvalidOperation] = False
        context.flags[Rounded] = True
        before = repr(context)
        with pytest.raises(ValueError) as error:
            assess_allowance(
                ReimbursementCategory.WELLNESS,
                date(2026, 1, 1),
                value if field == "requested" else "1",
                value if field == "consumed" else "0",
            )
        expected = REQUEST_ERRORS if field == "requested" else CONSUMED_ERRORS
        assert str(error.value) == expected[failure]
        assert repr(context) == before


@pytest.mark.parametrize("requested", [0, "0.000", Decimal("-0"), None])
def test_requested_zero_and_none_are_invalid(requested):
    with pytest.raises(ValueError) as error:
        assess_allowance(ReimbursementCategory.WELLNESS, date.min, requested, 0)
    assert str(error.value) == REQUEST_ERRORS["type" if requested is None else "domain"]


def test_capped_consumption_is_required():
    with pytest.raises(
        ValueError, match="^Capped policies require a consumed amount\\.$"
    ):
        assess_allowance(ReimbursementCategory.WELLNESS, date.min, 1, None)


@pytest.mark.parametrize("category", UNCAPPED_CATEGORIES)
@pytest.mark.parametrize("consumed", [0, "0", Decimal("-0"), -1, "NaN", [], True])
def test_uncapped_supplied_consumption_is_forbidden(category, consumed):
    with pytest.raises(ValueError) as error:
        assess_allowance(category, date.max, 1, consumed)
    assert str(error.value) == "Consumed allowance must be None for an uncapped policy."


@pytest.mark.parametrize("category", INVALID_CATEGORIES)
def test_assessment_category_validation_precedes_other_arguments(category):
    with pytest.raises(TypeError) as error:
        assess_allowance(category, None, "bad", None)
    assert str(error.value) == "Category must be a ReimbursementCategory."


@pytest.mark.parametrize("category", list(ReimbursementCategory))
@pytest.mark.parametrize("invoice_date", ["2026-01-01", datetime(2026, 1, 1), None])
def test_assessment_date_validation_precedes_money(category, invoice_date):
    with pytest.raises(TypeError) as error:
        assess_allowance(category, invoice_date, "bad", "bad")
    assert str(error.value) == "Invoice date must be a date without a time component."


@pytest.mark.parametrize("category", list(ReimbursementCategory))
def test_requested_validation_precedes_consumption(category):
    with pytest.raises(ValueError) as error:
        assess_allowance(category, date.min, "bad", "bad")
    assert str(error.value) == REQUEST_ERRORS["malformed"]


@pytest.mark.parametrize("rounding", [ROUND_UP, ROUND_DOWN])
@pytest.mark.parametrize("precision", [1, 2, 3])
def test_restrictive_context_does_not_round_or_change_inputs(precision, rounding):
    requested = Decimal("12.3400")
    consumed = Decimal("12345678901234567890.1200")
    expected = Decimal("-12345678901234537890.12")
    inputs_before = (requested.as_tuple(), consumed.as_tuple())
    with localcontext() as context:
        context.prec = precision
        context.rounding = rounding
        context.Emax, context.Emin = 2, -2
        for signal in context.traps:
            context.traps[signal] = True
        context.flags[Rounded] = True
        before = repr(context)
        result = assess_allowance(
            ReimbursementCategory.WELLNESS,
            InvoiceDate(2024, 2, 29),
            requested,
            consumed,
        )
        assert result.remaining.as_tuple() == expected.as_tuple()
        assert result.outcome is AllowanceOutcome.EXCEEDS_ALLOWANCE
        assert (
            result.requested.as_tuple(),
            result.consumed.as_tuple(),
        ) == inputs_before
        assert repr(context) == before
    assert (requested.as_tuple(), consumed.as_tuple()) == inputs_before


@pytest.mark.parametrize("representation", ["text", "decimal", "integer"])
@pytest.mark.parametrize("field", ["requested", "consumed"])
def test_values_beyond_integer_string_threshold_are_exact(representation, field):
    digit_limit = sys.get_int_max_str_digits()
    # Independent decimal digit patterns: 10**5001 - 30000 ends in 70000.
    text = "1" + "0" * 5001
    value = {"text": text, "decimal": Decimal(text), "integer": 10**5001}[
        representation
    ]
    expected_remaining = (
        Decimal((1, tuple(int(d) for d in "9" * 4996 + "70000" + "00"), -2))
        if field == "consumed"
        else Decimal("30000.00")
    )
    with localcontext() as context:
        context.prec = 1
        result = assess_allowance(
            ReimbursementCategory.WELLNESS,
            date.max,
            value if field == "requested" else "0.01",
            value if field == "consumed" else 0,
        )
    assert result.remaining.as_tuple() == expected_remaining.as_tuple()
    assert result.outcome is AllowanceOutcome.EXCEEDS_ALLOWANCE
    actual_input = result.requested if field == "requested" else result.consumed
    assert actual_input.as_tuple() == Decimal(text).as_tuple()
    assert sys.get_int_max_str_digits() == digit_limit


def test_long_fractional_representation_and_scientific_notation():
    requested = Decimal("9" * 5001 + ".1200")
    before = requested.as_tuple()
    result = assess_allowance(
        ReimbursementCategory.WELLNESS, date.min, requested, "1e2"
    )
    assert result.requested.as_tuple() == before == requested.as_tuple()
    assert result.remaining.as_tuple() == Decimal("29900.00").as_tuple()
    result = assess_allowance(
        ReimbursementCategory.WELLNESS, date.min, "1e5001", "0e999999"
    )
    assert result.outcome is AllowanceOutcome.EXCEEDS_ALLOWANCE
    assert result.remaining.as_tuple() == Decimal("30000.00").as_tuple()


@pytest.mark.parametrize(
    "field",
    ["category", "period", "requested", "cap", "consumed", "remaining", "outcome"],
)
@pytest.mark.parametrize("operation", [setattr, delattr])
def test_assessment_records_are_frozen(field, operation):
    result = assess_allowance(ReimbursementCategory.WELLNESS, date.min, "1", "0")
    with pytest.raises(FrozenInstanceError):
        if operation is setattr:
            operation(result, field, None)
        else:
            operation(result, field)
    assert result == assess_allowance(
        ReimbursementCategory.WELLNESS, date.min, "1", "0"
    )


@pytest.mark.parametrize(
    "missing", ["category", "invoice_date", "requested", "consumed"]
)
def test_all_assessment_arguments_are_required(missing):
    arguments = dict(
        category=ReimbursementCategory.WELLNESS,
        invoice_date=date.min,
        requested="1",
        consumed="0",
    )
    del arguments[missing]
    with pytest.raises(TypeError):
        assess_allowance(**arguments)
