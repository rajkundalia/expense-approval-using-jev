"""Structural claim validation, independent of submission dates and policy routing."""

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from expense_approval.claim_input import ClaimInput, ReimbursementCategory


@pytest.fixture
def claim_payload() -> dict[str, object]:
    return {
        "employee_id": "EMP-001",
        "merchant_name": "Example Merchant",
        "invoice_number": "INV-001",
        "invoice_date": "2026-10-31",
        "invoice_item_name": "Running shoes",
        "invoice_item_amount": "1200.00",
        "reimbursement_category": "WELLNESS",
        "requested_reimbursement": "1000.00",
        "employee_justification": "For daily running",
    }


@pytest.mark.parametrize(
    "field_name",
    [
        "employee_id",
        "merchant_name",
        "invoice_number",
        "invoice_date",
        "invoice_item_name",
        "invoice_item_amount",
        "reimbursement_category",
        "requested_reimbursement",
        "employee_justification",
    ],
)
def test_each_required_field_must_be_supplied(
    claim_payload: dict[str, object], field_name: str
) -> None:
    del claim_payload[field_name]

    with pytest.raises(ValidationError) as captured_error:
        ClaimInput.model_validate(claim_payload)

    assert captured_error.value.errors()[0]["loc"] == (field_name,)


@pytest.mark.parametrize(
    "field_name",
    [
        "employee_id",
        "merchant_name",
        "invoice_number",
        "invoice_item_name",
        "employee_justification",
    ],
)
@pytest.mark.parametrize("value", [None, "", " \t\n"])
def test_required_text_rejects_null_empty_and_whitespace(
    claim_payload: dict[str, object], field_name: str, value: object
) -> None:
    claim_payload[field_name] = value

    with pytest.raises(ValidationError) as captured_error:
        ClaimInput.model_validate(claim_payload)

    assert captured_error.value.errors()[0]["loc"] == (field_name,)


@pytest.mark.parametrize("value", [123, True, b"EMP-001"])
def test_text_is_not_coerced_from_other_types(
    claim_payload: dict[str, object], value: object
) -> None:
    claim_payload["employee_id"] = value

    with pytest.raises(ValidationError):
        ClaimInput.model_validate(claim_payload)


def test_original_text_and_caller_payload_are_preserved(
    claim_payload: dict[str, object],
) -> None:
    original_text = {
        "employee_id": " Emp-001 ",
        "merchant_name": "  Example   MERCHANT ",
        "invoice_number": " inv-001\t",
        "invoice_item_name": " Running  Shoes ",
        "employee_justification": "\tFor daily RUNNING\n",
    }
    claim_payload.update(original_text)
    claim_payload["invoice_item_amount"] = "1200.0000"
    original_payload = claim_payload.copy()

    claim = ClaimInput.model_validate(claim_payload)

    for field_name, original_value in original_text.items():
        assert getattr(claim, field_name) == original_value
    assert claim_payload == original_payload
    assert claim_payload["invoice_item_amount"] == "1200.0000"
    assert claim.invoice_item_amount.as_tuple() == Decimal("1200.0000").as_tuple()


@pytest.mark.parametrize(
    "category",
    [
        "WELLNESS",
        "SMARTPHONE",
        "BROADBAND",
        "MOBILE_BILL",
        "BUSINESS_HOTEL",
        "BUSINESS_TRANSPORT",
    ],
)
def test_all_six_employee_categories_are_accepted(
    claim_payload: dict[str, object], category: str
) -> None:
    claim_payload["reimbursement_category"] = category

    claim = ClaimInput.model_validate(claim_payload)

    assert claim.reimbursement_category is ReimbursementCategory(category)


@pytest.mark.parametrize(
    "category",
    ["OTHER", "INSUFFICIENT_INFORMATION", "MIXED_ITEMS", "UNKNOWN", "wellness", None],
)
def test_other_category_inputs_are_rejected(
    claim_payload: dict[str, object], category: object
) -> None:
    claim_payload["reimbursement_category"] = category

    with pytest.raises(ValidationError):
        ClaimInput.model_validate(claim_payload)


def test_omitted_line_number_defaults_to_one(claim_payload: dict[str, object]) -> None:
    assert ClaimInput.model_validate(claim_payload).invoice_line_number == 1


@pytest.mark.parametrize("line_number", [1, 7])
def test_positive_integer_line_numbers_are_accepted(
    claim_payload: dict[str, object], line_number: int
) -> None:
    claim_payload["invoice_line_number"] = line_number

    assert ClaimInput.model_validate(claim_payload).invoice_line_number == line_number


@pytest.mark.parametrize("line_number", [0, -1, True, False, 1.0, 1.5, "1", None])
def test_invalid_line_numbers_are_rejected(
    claim_payload: dict[str, object], line_number: object
) -> None:
    claim_payload["invoice_line_number"] = line_number

    with pytest.raises(ValidationError):
        ClaimInput.model_validate(claim_payload)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (date(2024, 2, 29), date(2024, 2, 29)),
        ("2024-02-29", date(2024, 2, 29)),
        ("2026-10-31", date(2026, 10, 31)),
        ("1900-01-01", date(1900, 1, 1)),
        ("2099-01-01", date(2099, 1, 1)),
    ],
)
def test_calendar_dates_are_accepted_without_relative_eligibility_checks(
    claim_payload: dict[str, object], value: object, expected: date
) -> None:
    claim_payload["invoice_date"] = value

    assert ClaimInput.model_validate(claim_payload).invoice_date == expected


@pytest.mark.parametrize(
    "value",
    [
        "2023-02-29",
        "2024-02-30",
        "not-a-date",
        "2026-2-01",
        "20261031",
        "2026-W44-6",
        "2026-10-31T00:00:00",
        datetime(2026, 10, 31),
        datetime(2026, 10, 31, tzinfo=timezone.utc),
        0,
        None,
    ],
)
def test_invalid_calendar_dates_and_datetime_timestamp_inputs_are_rejected(
    claim_payload: dict[str, object], value: object
) -> None:
    claim_payload["invoice_date"] = value

    with pytest.raises(ValidationError):
        ClaimInput.model_validate(claim_payload)


@pytest.mark.parametrize(
    "field_name", ["invoice_item_amount", "requested_reimbursement"]
)
@pytest.mark.parametrize("value", ["12.340", Decimal("12.0000"), 12])
def test_both_money_fields_use_exact_decimal_validation(
    claim_payload: dict[str, object], field_name: str, value: object
) -> None:
    claim_payload["requested_reimbursement"] = "1.00"
    claim_payload[field_name] = value

    claim = ClaimInput.model_validate(claim_payload)

    assert getattr(claim, field_name) == Decimal(value)
    assert isinstance(getattr(claim, field_name), Decimal)


@pytest.mark.parametrize(
    "field_name", ["invoice_item_amount", "requested_reimbursement"]
)
@pytest.mark.parametrize("value", [12.34, True, None, "12.345"])
def test_money_validation_runs_before_pydantic_coercion(
    claim_payload: dict[str, object], field_name: str, value: object
) -> None:
    claim_payload[field_name] = value

    with pytest.raises(ValidationError) as captured_error:
        ClaimInput.model_validate(claim_payload)

    assert captured_error.value.errors()[0]["loc"] == (field_name,)


@pytest.mark.parametrize("requested_amount", ["12.34", "12.33"])
def test_requested_amount_can_equal_or_be_lower_than_cost_without_adjustment(
    claim_payload: dict[str, object], requested_amount: str
) -> None:
    claim_payload["invoice_item_amount"] = "12.34"
    claim_payload["requested_reimbursement"] = requested_amount

    claim = ClaimInput.model_validate(claim_payload)

    assert claim.requested_reimbursement == Decimal(requested_amount)


@pytest.mark.parametrize(
    ("item_amount", "requested_amount"),
    [
        ("0.10", "0.11"),
        ("123456789012345678901234567890.12", "123456789012345678901234567890.13"),
    ],
)
def test_exact_requested_amount_cannot_exceed_item_cost(
    claim_payload: dict[str, object], item_amount: str, requested_amount: str
) -> None:
    claim_payload["invoice_item_amount"] = item_amount
    claim_payload["requested_reimbursement"] = requested_amount

    with pytest.raises(ValidationError):
        ClaimInput.model_validate(claim_payload)


def test_unknown_fields_are_rejected(claim_payload: dict[str, object]) -> None:
    claim_payload["claim_id"] = "not-an-employee-input"

    with pytest.raises(ValidationError) as captured_error:
        ClaimInput.model_validate(claim_payload)

    assert captured_error.value.errors()[0]["type"] == "extra_forbidden"


def test_failed_validation_does_not_modify_caller_payload(
    claim_payload: dict[str, object],
) -> None:
    claim_payload["requested_reimbursement"] = "1200.01"
    original_payload = claim_payload.copy()

    with pytest.raises(ValidationError):
        ClaimInput.model_validate(claim_payload)

    assert claim_payload == original_payload
