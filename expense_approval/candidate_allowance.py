"""Compose candidate allowance assessment without financial admission or writes."""

import sqlite3

from expense_approval.allowance_policy import (
    AllowanceAssessment,
    assess_allowance,
    get_allowance_period,
    get_allowance_policy,
)
from expense_approval.allowance_store import read_consumed_allowance
from expense_approval.claim_input import ClaimInput


def assess_candidate_allowance(
    connection: sqlite3.Connection,
    *,
    candidate: ClaimInput,
) -> AllowanceAssessment:
    """Assess a normally validated ClaimInput using existing consumption.

    Validation-bypassing model construction or updates are outside this contract.
    Contextual invoice eligibility and selection of current candidate evidence
    remain caller responsibilities. No candidate claim ID or exclusion is used:
    every matching PROCESSABLE claim contributes, even one represented by the
    candidate. This is not an idempotent processing operation.

    Capped consumption observes the reader's SQLite snapshot and reserves nothing.
    Uncapped assessment never accesses SQLite, so a correctly typed closed
    connection is acceptable. The caller owns the connection and transaction;
    no transactions, savepoints, settings changes or persisted writes occur here.
    Future processing must serialize and recheck. Dependency errors propagate.
    """
    if not isinstance(connection, sqlite3.Connection):
        raise TypeError("Connection must be a sqlite3.Connection.")
    if not isinstance(candidate, ClaimInput):
        raise TypeError("Candidate must be a ClaimInput.")

    category = candidate.reimbursement_category
    invoice_date = candidate.invoice_date
    policy = get_allowance_policy(category)
    period = get_allowance_period(category, invoice_date)
    consumed = None
    if policy.cap is not None:
        consumed = read_consumed_allowance(
            connection,
            employee_id=candidate.employee_id,
            category=category,
            period=period,
        )
    return assess_allowance(
        category, invoice_date, candidate.requested_reimbursement, consumed
    )
