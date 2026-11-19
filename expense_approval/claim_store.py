"""Internal initial-claim storage; policy admission and lifecycle are separate."""

import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from expense_approval.claim_input import ClaimInput
from expense_approval.clock import business_date
from expense_approval.evidence import encode_raw_evidence
from expense_approval.identity import normalize_identity_text
from expense_approval.validation import validate_invoice_date


def insert_initial_claim(
    connection: sqlite3.Connection,
    *,
    raw_input: dict[str, object],
    submitted_at: datetime,
) -> str:
    """Store initial evidence and identity inside a caller-owned transaction.

    Use connect_database() and an already-active write_transaction(). The trusted
    aware submission instant supplies both the UTC timestamp and India date.
    Input must remain stable during capture and validation. Existing structural
    and date checks run here; allowance checks and complete admission do not.

    A local savepoint makes all three inserts atomic even if the caller catches
    an error. This function never commits or rolls back the outer transaction.
    The returned UUID is provisional until the caller commits that transaction.
    """
    if not connection.in_transaction:
        raise ValueError(
            "Initial insertion requires an active caller-owned transaction."
        )
    if not isinstance(submitted_at, datetime):
        raise TypeError("Submission instant must be a datetime.")
    original_submission_date = business_date(lambda: submitted_at)
    raw_evidence_json = encode_raw_evidence(raw_input)
    claim = ClaimInput.model_validate(raw_input)
    validate_invoice_date(claim.invoice_date, original_submission_date)

    claim_id = str(uuid4())
    parameters = {
        "claim_id": claim_id,
        "revision_id": str(uuid4()),
        "event_id": str(uuid4()),
        "submitted_at": submitted_at.astimezone(timezone.utc).isoformat(
            timespec="microseconds"
        ),
        "original_submission_date": original_submission_date.isoformat(),
        "employee_id": normalize_identity_text(claim.employee_id),
        "merchant_name": normalize_identity_text(claim.merchant_name),
        "invoice_number": normalize_identity_text(claim.invoice_number),
        # Decimal(int) preserves arbitrarily large line numbers without changing
        # the interpreter's integer-to-string digit limit.
        "invoice_line_number": str(Decimal(claim.invoice_line_number)),
        "raw_evidence_json": raw_evidence_json,
        "invoice_date": claim.invoice_date.isoformat(),
        "category": claim.reimbursement_category.value,
        "item_amount": str(claim.invoice_item_amount),
        "requested_amount": str(claim.requested_reimbursement),
    }

    connection.execute("SAVEPOINT initial_claim_insert")
    try:
        connection.execute(
            """INSERT INTO claims (
                claim_id, submitted_at, original_submission_date,
                current_evidence_version, state_version, normalized_employee_id,
                normalized_merchant_name, normalized_invoice_number, invoice_line_number
            ) VALUES (
                :claim_id, :submitted_at, :original_submission_date,
                1, 1, :employee_id, :merchant_name, :invoice_number, :invoice_line_number
            )""",
            parameters,
        )
        connection.execute(
            """INSERT INTO claim_revisions (
                revision_id, claim_id, evidence_version, submitted_at, action_kind,
                disposition, raw_evidence_json, invoice_date, reimbursement_category,
                invoice_item_amount, requested_reimbursement, validation_details_json
            ) VALUES (
                :revision_id, :claim_id, 1, :submitted_at, 'INITIAL', 'ACCEPTED',
                :raw_evidence_json, :invoice_date, :category, :item_amount,
                :requested_amount, '{}'
            )""",
            parameters,
        )
        connection.execute(
            """INSERT INTO claim_events (
                event_id, claim_id, occurred_at, event_kind, evidence_version,
                revision_id, details_json
            ) VALUES (
                :event_id, :claim_id, :submitted_at, 'INITIAL_CLAIM_STORED',
                1, :revision_id, '{"state_version":1}'
            )""",
            parameters,
        )
        connection.execute("RELEASE SAVEPOINT initial_claim_insert")
    except BaseException:
        # SQLite may itself end a transaction on severe errors. Do not mask that
        # original failure by attempting to roll back a nonexistent savepoint.
        if connection.in_transaction:
            connection.execute("ROLLBACK TO SAVEPOINT initial_claim_insert")
            connection.execute("RELEASE SAVEPOINT initial_claim_insert")
        raise
    return claim_id


def get_claim(connection: sqlite3.Connection, claim_id: str) -> sqlite3.Row | None:
    """Read current state and its exact accepted evidence; leave JSON as text.

    Use a cursor-local row factory without changing connection settings or
    opening/ending a transaction. Return None when the claim does not exist.
    """
    with closing(connection.cursor()) as cursor:
        cursor.row_factory = sqlite3.Row
        cursor.execute(
            """SELECT c.*,
                r.revision_id AS current_revision_id,
                r.raw_evidence_json AS current_raw_evidence_json,
                r.invoice_date AS current_invoice_date,
                r.reimbursement_category AS current_reimbursement_category,
                r.invoice_item_amount AS current_invoice_item_amount,
                r.requested_reimbursement AS current_requested_reimbursement
            FROM claims AS c
            JOIN claim_revisions AS r
              ON r.claim_id = c.claim_id
             AND r.evidence_version = c.current_evidence_version
             AND r.disposition = 'ACCEPTED'
            WHERE c.claim_id = ?""",
            (claim_id,),
        )
        return cursor.fetchone()


def list_claim_revisions(
    connection: sqlite3.Connection, claim_id: str
) -> list[sqlite3.Row]:
    """Read all accepted and failed attempts in timestamp/ID order, or [].

    Dispositions and JSON text are returned unchanged. No transaction is opened
    or ended; callers own any shared snapshot needed across separate reads.
    """
    with closing(connection.cursor()) as cursor:
        cursor.row_factory = sqlite3.Row
        cursor.execute(
            """SELECT * FROM claim_revisions WHERE claim_id = ?
            ORDER BY submitted_at, revision_id""",
            (claim_id,),
        )
        return cursor.fetchall()


def list_claim_events(
    connection: sqlite3.Connection, claim_id: str
) -> list[sqlite3.Row]:
    """Read complete audit history in timestamp/ID order, or [], without writes."""
    with closing(connection.cursor()) as cursor:
        cursor.row_factory = sqlite3.Row
        cursor.execute(
            """SELECT * FROM claim_events WHERE claim_id = ?
            ORDER BY occurred_at, event_id""",
            (claim_id,),
        )
        return cursor.fetchall()
