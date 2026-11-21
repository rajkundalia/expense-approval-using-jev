"""Read exact allowance consumption; no admission, reservation or processing."""

import sqlite3
from calendar import monthrange
from contextlib import closing
from datetime import date
from decimal import Decimal, InvalidOperation, localcontext

from expense_approval.allowance_policy import (
    AllowancePeriod,
    AllowancePeriodKind,
    _amount_to_paise,
    _paise_to_decimal,
    get_allowance_policy,
)
from expense_approval.claim_input import ReimbursementCategory
from expense_approval.identity import normalize_identity_text
from expense_approval.validation import parse_money


def read_consumed_allowance(
    connection: sqlite3.Connection,
    *,
    employee_id: str,
    category: ReimbursementCategory,
    period: AllowancePeriod,
) -> Decimal:
    """Sum current accepted PROCESSABLE requests for a capped invoice period.

    Return nonnegative INR with exactly two places, including 0.00 for no rows.
    Validate connection, employee, capped category, then period before SQL. Bad
    selected money raises ValueError instead of returning a partial total.

    One SELECT observes SQLite's statement/caller snapshot. This reader owns no
    transaction and changes no connection settings; it closes only its cursor.
    A read reserves nothing: future processing must serialize and recheck.
    Schema-valid references and canonical ISO date projections are assumed;
    this is not a database corruption scanner. Standard text decoding is required.
    """
    if not isinstance(connection, sqlite3.Connection):
        raise TypeError("Connection must be a sqlite3.Connection.")
    employee = normalize_identity_text(employee_id)
    if not employee:
        raise ValueError("Employee ID must be nonblank text.")
    policy = get_allowance_policy(category)
    if policy.cap is None:
        raise ValueError("Consumption reads require a capped category.")
    if not isinstance(period, AllowancePeriod):
        raise TypeError("Period must be an AllowancePeriod.")
    if not isinstance(period.kind, AllowancePeriodKind):
        raise TypeError("Period kind must be an AllowancePeriodKind.")
    if period.kind is not policy.period_kind:
        raise ValueError("Period kind must match the category allowance period.")
    if isinstance(period.year, bool) or not isinstance(period.year, int):
        raise TypeError("Period year must be an integer.")
    if not 1 <= period.year <= 9999:
        raise ValueError("Period year must be between 1 and 9999.")
    if period.kind is AllowancePeriodKind.ANNUAL:
        if period.month is not None:
            raise ValueError("Annual periods must have month=None.")
        start = date(period.year, 1, 1)
        end = date(period.year, 12, 31)
    else:
        if isinstance(period.month, bool) or not isinstance(period.month, int):
            raise TypeError("Monthly period month must be an integer.")
        if not 1 <= period.month <= 12:
            raise ValueError("Monthly period month must be between 1 and 12.")
        start = date(period.year, period.month, 1)
        end = date(period.year, period.month, monthrange(period.year, period.month)[1])

    total_paise = 0
    with closing(connection.cursor()) as cursor:
        cursor.row_factory = sqlite3.Row
        cursor.execute(
            """SELECT r.requested_reimbursement
            FROM claims AS c
            JOIN claim_revisions AS r
              ON r.claim_id = c.claim_id
             AND r.evidence_version = c.current_evidence_version
             AND r.disposition = 'ACCEPTED'
            WHERE c.status = 'PROCESSABLE'
              AND c.normalized_employee_id = :employee_id
              AND r.reimbursement_category = :category
              AND r.invoice_date >= :period_start
              AND r.invoice_date <= :period_end""",
            {
                "employee_id": employee,
                "category": category.value,
                "period_start": start.isoformat(),
                "period_end": end.isoformat(),
            },
        )
        # Isolate parse flags/traps. All arithmetic uses arbitrary Python ints.
        with localcontext() as context:
            context.traps[InvalidOperation] = True
            for row in cursor:
                value = row["requested_reimbursement"]
                try:
                    if not isinstance(value, str):
                        raise ValueError("Stored money must be text.")
                    amount = parse_money(value)
                except ValueError as error:
                    raise ValueError(
                        "Stored requested reimbursement is invalid."
                    ) from error
                total_paise += _amount_to_paise(amount)
    return _paise_to_decimal(total_paise)
