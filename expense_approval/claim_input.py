"""Structural claim inputs; date eligibility requires separate submission context."""

import re
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Self

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StrictStr,
    field_validator,
    model_validator,
)

from expense_approval.validation import parse_money

MoneyAmount = Annotated[Decimal, BeforeValidator(parse_money)]


class ReimbursementCategory(StrEnum):
    """Employee-selectable categories; no semantic classification outcomes."""

    WELLNESS = "WELLNESS"
    SMARTPHONE = "SMARTPHONE"
    BROADBAND = "BROADBAND"
    MOBILE_BILL = "MOBILE_BILL"
    BUSINESS_HOTEL = "BUSINESS_HOTEL"
    BUSINESS_TRANSPORT = "BUSINESS_TRANSPORT"


class ClaimInput(BaseModel):
    """Validate structure and amounts, without asserting invoice-date eligibility."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    employee_id: StrictStr
    merchant_name: StrictStr
    invoice_number: StrictStr
    invoice_date: date
    invoice_item_name: StrictStr
    invoice_item_amount: MoneyAmount
    reimbursement_category: ReimbursementCategory
    requested_reimbursement: MoneyAmount
    employee_justification: StrictStr
    invoice_line_number: int = Field(default=1, strict=True, gt=0)

    @field_validator(
        "employee_id",
        "merchant_name",
        "invoice_number",
        "invoice_item_name",
        "employee_justification",
    )
    @classmethod
    def require_nonblank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Required text must not be empty or whitespace-only.")
        return value

    @field_validator("invoice_date", mode="before")
    @classmethod
    def parse_invoice_date(cls, value: object) -> date:
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        if isinstance(value, str) and re.fullmatch(
            r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value
        ):
            try:
                return date.fromisoformat(value)
            except ValueError:
                pass
        raise ValueError("Invoice date must be a date or valid YYYY-MM-DD date text.")

    @model_validator(mode="after")
    def validate_requested_amount(self) -> Self:
        if self.requested_reimbursement > self.invoice_item_amount:
            raise ValueError("Requested reimbursement must not exceed the item amount.")
        return self
