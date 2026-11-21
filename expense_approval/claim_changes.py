"""Guarded corrections and cancellation; policy admission remains separate."""

import json
import sqlite3
from contextlib import closing
from dataclasses import asdict, dataclass, replace
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Literal
from uuid import UUID, uuid4

from pydantic import ValidationError

from expense_approval.claim_input import ClaimInput
from expense_approval.claim_store import get_claim
from expense_approval.evidence import encode_raw_evidence
from expense_approval.identity import normalize_identity_text
from expense_approval.validation import validate_invoice_date

_STATUSES = {
    None,
    "NEED_INFO",
    "HUMAN_REVIEW",
    "POLICY_RESTRICTION",
    "CANCELLED",
    "PROCESSABLE",
}
_ACTION = "ORDINARY_CORRECTION"
_EVENT = "CLAIM_CHANGE_REJECTED"
_ACCEPTED_EVENT = "CLAIM_CORRECTION_ACCEPTED"
_CANCEL_ACTION = "CANCELLATION"
_CANCEL_EVENT = "CLAIM_CANCELLED"


class OperationIdConflict(ValueError):
    """An operation UUID already identifies a different request or event."""


class UnverifiableReplayConflict(OperationIdConflict):
    """Incomplete raw capture prevents proving that this is the same request."""


class MalformedOperationReceipt(ValueError):
    """A recognized operation receipt is malformed or incompatible."""


@dataclass(frozen=True)
class ChangeResult:
    """Recorded outcome, provisional until the caller commits.

    Replay returns the original observed state, not today's current state.
    Details remain detached JSON text so the frozen result has no mutable fields.
    """

    claim_id: str
    operation_id: str
    action_kind: str
    outcome: Literal[
        "ACCEPTED",
        "INVALID",
        "STALE",
        "NOT_EDITABLE",
        "DUPLICATE_CONFLICT",
        "CANCELLED",
    ]
    reason_code: str
    event_id: str
    revision_id: str | None
    evidence_version_after: int
    state_version_after: int
    status_after: str | None
    details_json: str
    replayed: bool = False


def correct_claim(
    connection: sqlite3.Connection,
    *,
    claim_id: str,
    operation_id: str,
    action_kind: Literal["ORDINARY_CORRECTION"],
    expected_status: str | None,
    expected_evidence_version: int,
    expected_state_version: int,
    raw_input: dict[str, object],
    occurred_at: datetime,
) -> ChangeResult:
    """Store full-replacement ordinary corrections in a caller-owned transaction.

    Use connect_database() inside write_transaction() (BEGIN IMMEDIATE). No
    commits, outer rollbacks, decision transitions or counter changes occur here.
    Input must remain stable during capture and validation. Capture precedes
    parsing; receipt lookup precedes current-state guards. All results become
    durable only if the caller commits. Unexpected failures propagate.

    Only explicitly declared ordinary corrections are supported. Trusted callers
    must not mislabel semantic or counted correction responses; this function
    neither infers intent nor admits those responses. Accepted evidence is not a
    fresh policy decision: retained status/reason/question may concern earlier
    evidence. Financial admission and subsequent reevaluation remain separate.
    """
    if not connection.in_transaction:
        raise ValueError("Correction requires an active caller-owned transaction.")
    if not isinstance(claim_id, str) or not claim_id.strip():
        raise ValueError("Claim ID must be nonblank text.")
    if not isinstance(operation_id, str):
        raise ValueError("Operation ID must be a canonical UUID4 string.")
    try:
        operation_uuid = UUID(operation_id)
    except ValueError:
        raise ValueError("Operation ID must be a canonical UUID4 string.") from None
    if operation_uuid.version != 4 or str(operation_uuid) != operation_id:
        raise ValueError("Operation ID must be a canonical UUID4 string.")
    if action_kind != _ACTION:
        raise ValueError("Only ORDINARY_CORRECTION is supported.")
    if expected_status is not None and (
        not isinstance(expected_status, str) or expected_status not in _STATUSES
    ):
        raise ValueError("Expected status is not supported.")
    for version in (expected_evidence_version, expected_state_version):
        if type(version) is not int or version <= 0:
            raise ValueError(
                "Expected versions must be positive integers, not booleans."
            )
    if type(raw_input) is not dict:
        raise TypeError("Raw input must be a built-in dictionary.")
    if not isinstance(occurred_at, datetime):
        raise TypeError("Operation instant must be a datetime.")
    if occurred_at.utcoffset() is None:
        raise ValueError("Operation instant must be timezone-aware.")
    timestamp = occurred_at.astimezone(timezone.utc).isoformat(timespec="microseconds")
    raw_json = encode_raw_evidence(raw_input)
    request = {
        "claim_id": claim_id,
        "action_kind": action_kind,
        "expected_status": expected_status,
        "expected_evidence_version": expected_evidence_version,
        "expected_state_version": expected_state_version,
        "raw_evidence_json": raw_json,
    }
    replay = _replay(connection, operation_id, request)
    if replay is not None:
        return replay

    claim = get_claim(connection, claim_id)
    if claim is None:
        raise LookupError("Claim does not exist.")
    observed = {
        "status": claim["status"],
        "evidence_version": claim["current_evidence_version"],
        "state_version": claim["state_version"],
    }
    mismatches = [
        key
        for key, expected in (
            ("status", expected_status),
            ("evidence_version", expected_evidence_version),
            ("state_version", expected_state_version),
        )
        if observed[key] != expected
    ]
    if mismatches:
        outcome, reason = "STALE", "EXPECTED_STATE_MISMATCH"
        details = {"observed": observed, "mismatched_guards": mismatches}
    elif claim["status"] not in ("NEED_INFO", "HUMAN_REVIEW"):
        outcome, reason = "NOT_EDITABLE", "STATE_NOT_EDITABLE"
        details = {
            "observed": observed,
            "state_kind": "UNDECIDED" if claim["status"] is None else "TERMINAL",
        }
    else:
        try:
            proposed = ClaimInput.model_validate(raw_input)
        except ValidationError as error:
            outcome, reason = "INVALID", "INVALID_FIELDS"
            details = {
                "errors": error.errors(
                    include_url=False, include_context=False, include_input=False
                )
            }
        else:
            try:
                validate_invoice_date(
                    proposed.invoice_date,
                    date.fromisoformat(claim["original_submission_date"]),
                )
            except ValueError as error:
                outcome, reason = "INVALID", "INVALID_INVOICE_DATE"
                details = {"errors": [{"field": "invoice_date", "message": str(error)}]}
            else:
                return _accept_correction(
                    connection,
                    request=request,
                    operation_id=operation_id,
                    timestamp=timestamp,
                    proposed=proposed,
                    claim=claim,
                    observed=observed,
                )

    return _record_rejection(
        connection,
        request=request,
        operation_id=operation_id,
        timestamp=timestamp,
        outcome=outcome,
        reason=reason,
        details=details,
        observed=observed,
    )


def _has_incomplete(node: dict[str, object]) -> bool:
    """Inspect encoder nodes, never employee strings or reconstructed values."""
    if node["type"] == "incomplete":
        return True
    if node["type"] == "list":
        return any(_has_incomplete(item) for item in node["items"])
    if node["type"] == "dict":
        return any(
            (isinstance(key, dict) and _has_incomplete(key)) or _has_incomplete(value)
            for key, value in node["entries"]
        )
    return False


def cancel_claim(
    connection: sqlite3.Connection,
    *,
    claim_id: str,
    operation_id: str,
    expected_status: str | None,
    expected_evidence_version: int,
    expected_state_version: int,
    occurred_at: datetime,
    cancellation_reason: str | None = None,
) -> ChangeResult:
    """Cancel an editable claim and audit it in a caller-owned write transaction.

    Use connect_database() inside write_transaction() (BEGIN IMMEDIATE). Receipt
    lookup precedes current-state guards. A local savepoint joins the status and
    question-pointer update with its event; no revision is created. Historical
    questions, evidence, identity, original submission and counters are preserved.
    All outcomes remain provisional until the caller commits. This function
    never commits or rolls back the outer transaction.
    """
    if not connection.in_transaction:
        raise ValueError("Cancellation requires an active caller-owned transaction.")
    if not isinstance(claim_id, str) or not claim_id.strip():
        raise ValueError("Claim ID must be nonblank text.")
    if not isinstance(operation_id, str):
        raise ValueError("Operation ID must be a canonical UUID4 string.")
    try:
        operation_uuid = UUID(operation_id)
    except ValueError:
        raise ValueError("Operation ID must be a canonical UUID4 string.") from None
    if operation_uuid.version != 4 or str(operation_uuid) != operation_id:
        raise ValueError("Operation ID must be a canonical UUID4 string.")
    if expected_status is not None and (
        not isinstance(expected_status, str) or expected_status not in _STATUSES
    ):
        raise ValueError("Expected status is not supported.")
    for version in (expected_evidence_version, expected_state_version):
        if type(version) is not int or version <= 0:
            raise ValueError(
                "Expected versions must be positive integers, not booleans."
            )
    if not isinstance(occurred_at, datetime):
        raise TypeError("Operation instant must be a datetime.")
    if occurred_at.utcoffset() is None:
        raise ValueError("Operation instant must be timezone-aware.")
    if cancellation_reason is not None and type(cancellation_reason) is not str:
        raise TypeError("Cancellation reason must be plain text or None.")
    timestamp = occurred_at.astimezone(timezone.utc).isoformat(timespec="microseconds")
    request = {
        "claim_id": claim_id,
        "action_kind": _CANCEL_ACTION,
        "expected_status": expected_status,
        "expected_evidence_version": expected_evidence_version,
        "expected_state_version": expected_state_version,
        "cancellation_reason": cancellation_reason,
    }
    replay = _replay(connection, operation_id, request)
    if replay is not None:
        return replay
    claim = get_claim(connection, claim_id)
    if claim is None:
        raise LookupError("Claim does not exist.")
    observed = {
        "status": claim["status"],
        "evidence_version": claim["current_evidence_version"],
        "state_version": claim["state_version"],
    }
    mismatches = [
        key
        for key, expected in (
            ("status", expected_status),
            ("evidence_version", expected_evidence_version),
            ("state_version", expected_state_version),
        )
        if observed[key] != expected
    ]
    details = {
        "previous_status": claim["status"],
        "previous_reason_code": claim["reason_code"],
        "previous_question_event_id": claim["outstanding_question_event_id"],
        "cancellation_reason": cancellation_reason,
        "observed": observed,
    }
    if mismatches:
        outcome, reason = "STALE", "EXPECTED_STATE_MISMATCH"
        details["mismatched_guards"] = mismatches
    elif claim["status"] not in ("NEED_INFO", "HUMAN_REVIEW"):
        outcome, reason = "NOT_EDITABLE", "STATE_NOT_EDITABLE"
        details["state_kind"] = "UNDECIDED" if claim["status"] is None else "TERMINAL"
    else:
        outcome, reason = "CANCELLED", "CANCELLED_BY_EMPLOYEE"
    accepted = outcome == "CANCELLED"
    result = ChangeResult(
        claim_id=claim_id,
        operation_id=operation_id,
        action_kind=_CANCEL_ACTION,
        outcome=outcome,
        reason_code=reason,
        event_id=operation_id,
        revision_id=None,
        evidence_version_after=claim["current_evidence_version"],
        state_version_after=claim["state_version"] + int(accepted),
        status_after="CANCELLED" if accepted else claim["status"],
        details_json=json.dumps(details, ensure_ascii=True, allow_nan=False),
    )
    connection.execute("SAVEPOINT claim_cancellation")
    try:
        if accepted:
            with closing(
                connection.execute(
                    """UPDATE claims SET status='CANCELLED', reason_code='CANCELLED_BY_EMPLOYEE',
                    state_version=state_version+1, outstanding_question_event_id=NULL
                WHERE claim_id=? AND status IS ?
                  AND status IN ('NEED_INFO', 'HUMAN_REVIEW')
                  AND current_evidence_version=? AND state_version=?""",
                    (
                        claim_id,
                        expected_status,
                        expected_evidence_version,
                        expected_state_version,
                    ),
                )
            ) as cursor:
                if cursor.rowcount != 1:
                    raise RuntimeError("Guarded cancellation did not update one claim.")
        connection.execute(
            """INSERT INTO claim_events (
                event_id, claim_id, occurred_at, event_kind, evidence_version,
                from_status, to_status, details_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                operation_id,
                claim_id,
                timestamp,
                _CANCEL_EVENT if accepted else _EVENT,
                claim["current_evidence_version"] if accepted else None,
                claim["status"],
                result.status_after,
                _receipt_json(request, result),
            ),
        )
        connection.execute("RELEASE SAVEPOINT claim_cancellation")
    except BaseException:
        if connection.in_transaction:
            connection.execute("ROLLBACK TO SAVEPOINT claim_cancellation")
            connection.execute("RELEASE SAVEPOINT claim_cancellation")
        raise
    return result


def _replay(
    connection: sqlite3.Connection, operation_id: str, request: dict[str, object]
) -> ChangeResult | None:
    with closing(connection.cursor()) as cursor:
        cursor.row_factory = sqlite3.Row
        event = cursor.execute(
            "SELECT * FROM claim_events WHERE event_id = ?", (operation_id,)
        ).fetchone()
    if event is None:
        return None
    receipt = json.loads(event["details_json"])
    if (
        event["event_kind"] not in (_EVENT, _ACCEPTED_EVENT, _CANCEL_EVENT)
        or event["claim_id"] != request["claim_id"]
        or not isinstance(receipt, dict)
        or receipt.get("format") != "claim-change-receipt"
    ):
        raise OperationIdConflict("Operation ID already identifies another event.")
    stored_request = receipt.get("request")
    if (
        isinstance(stored_request, dict)
        and isinstance(stored_request.get("action_kind"), str)
        and stored_request["action_kind"] != request["action_kind"]
    ):
        raise OperationIdConflict("Operation ID already identifies another action.")
    result, incomplete = _validate_receipt(receipt, event, request.keys())
    if any(
        stored_request[key] != value
        for key, value in request.items()
        if key != "raw_evidence_json"
    ):
        raise OperationIdConflict("Operation ID already identifies another request.")
    if request["action_kind"] == _ACTION and (
        incomplete or _has_incomplete(json.loads(request["raw_evidence_json"])["value"])
    ):
        raise UnverifiableReplayConflict("Incomplete capture prevents proving replay.")
    if stored_request != request:
        raise OperationIdConflict("Operation ID already identifies different input.")
    return replace(result, replayed=True)


def _validate_receipt(receipt, event, request_keys) -> tuple[ChangeResult, bool]:
    """Validate this receipt version before comparing or returning stored data."""
    try:
        request = receipt["request"]
        if (
            type(receipt["version"]) is not int
            or receipt["version"] != 1
            or not isinstance(request, dict)
            or request.keys() != request_keys
            or request["claim_id"] != event["claim_id"]
            or request["action_kind"] not in (_ACTION, _CANCEL_ACTION)
            or not (
                request["expected_status"] is None
                or isinstance(request["expected_status"], str)
                and request["expected_status"] in _STATUSES
            )
            or any(
                type(request[key]) is not int or request[key] <= 0
                for key in ("expected_evidence_version", "expected_state_version")
            )
        ):
            raise ValueError("Invalid receipt request or version.")
        cancellation = request["action_kind"] == _CANCEL_ACTION
        incomplete = False
        if cancellation:
            if (
                request["cancellation_reason"] is not None
                and type(request["cancellation_reason"]) is not str
            ):
                raise ValueError("Invalid cancellation receipt reason.")
        else:
            if not isinstance(request["raw_evidence_json"], str):
                raise ValueError("Invalid receipt raw evidence.")
            raw = json.loads(request["raw_evidence_json"])
            if (
                not isinstance(raw, dict)
                or raw.get("format") != "raw-evidence"
                or type(raw.get("version")) is not int
                or raw["version"] != 1
            ):
                raise ValueError("Invalid receipt evidence envelope.")
            incomplete = _has_incomplete(raw["value"])
        stored_result = receipt["result"]
        if not isinstance(stored_result, dict):
            raise ValueError("Invalid receipt result.")
        result = ChangeResult(**stored_result)
        reasons = {
            "ACCEPTED": ("EVIDENCE_ACCEPTED",),
            "DUPLICATE_CONFLICT": ("IDENTITY_ALREADY_OWNED",),
            "INVALID": ("INVALID_FIELDS", "INVALID_INVOICE_DATE"),
            "STALE": ("EXPECTED_STATE_MISMATCH",),
            "NOT_EDITABLE": ("STATE_NOT_EDITABLE",),
        }
        if cancellation:
            reasons = {
                "CANCELLED": ("CANCELLED_BY_EMPLOYEE",),
                "STALE": ("EXPECTED_STATE_MISMATCH",),
                "NOT_EDITABLE": ("STATE_NOT_EDITABLE",),
            }
        if (
            result.claim_id != event["claim_id"]
            or result.operation_id != event["event_id"]
            or result.event_id != event["event_id"]
            or result.action_kind != request["action_kind"]
            or not isinstance(result.outcome, str)
            or result.outcome not in reasons
            or result.reason_code not in reasons[result.outcome]
            or result.replayed is not False
            or not (
                result.status_after is None
                or isinstance(result.status_after, str)
                and result.status_after in _STATUSES
            )
            or event["from_status"]
            != (
                request["expected_status"]
                if result.outcome == "CANCELLED"
                else result.status_after
            )
            or result.status_after != event["to_status"]
            or result.revision_id != event["revision_id"]
            or (result.revision_id is None)
            != (cancellation or result.outcome == "NOT_EDITABLE")
            or any(
                type(value) is not int or value <= 0
                for value in (result.evidence_version_after, result.state_version_after)
            )
            or not isinstance(result.details_json, str)
            or not isinstance(json.loads(result.details_json), dict)
            or event["event_kind"]
            != (
                _CANCEL_EVENT
                if result.outcome == "CANCELLED"
                else _ACCEPTED_EVENT
                if result.outcome == "ACCEPTED"
                else _EVENT
            )
            or event["evaluation_id"] is not None
            or event["evidence_version"]
            != (
                result.evidence_version_after
                if result.outcome in ("ACCEPTED", "CANCELLED")
                else None
            )
        ):
            raise ValueError("Invalid or inconsistent receipt result.")
        if result.outcome in ("ACCEPTED", "DUPLICATE_CONFLICT"):
            increment = int(result.outcome == "ACCEPTED")
            if (
                result.status_after not in ("NEED_INFO", "HUMAN_REVIEW")
                or result.status_after != request["expected_status"]
                or result.evidence_version_after
                != request["expected_evidence_version"] + increment
                or result.state_version_after
                != request["expected_state_version"] + increment
            ):
                raise ValueError("Invalid correction receipt versions or status.")
        if cancellation:
            matches = (
                result.evidence_version_after == request["expected_evidence_version"]
                and result.state_version_after == request["expected_state_version"]
                and result.status_after == request["expected_status"]
            )
            if result.outcome == "CANCELLED":
                if (
                    request["expected_status"] not in ("NEED_INFO", "HUMAN_REVIEW")
                    or result.status_after != "CANCELLED"
                    or result.evidence_version_after
                    != request["expected_evidence_version"]
                    or result.state_version_after
                    != request["expected_state_version"] + 1
                ):
                    raise ValueError("Invalid accepted cancellation receipt.")
            elif result.outcome == "STALE" and matches:
                raise ValueError("Cancellation receipt has no stale guard.")
            elif result.outcome == "NOT_EDITABLE" and (
                not matches or result.status_after in ("NEED_INFO", "HUMAN_REVIEW")
            ):
                raise ValueError(
                    "Cancellation receipt does not target a matching non-editable state."
                )
    except (KeyError, TypeError, ValueError) as error:
        raise MalformedOperationReceipt(
            "Stored operation receipt is malformed or incompatible."
        ) from error
    return result, incomplete


def _receipt_json(request: dict[str, object], result: ChangeResult) -> str:
    return json.dumps(
        {
            "format": "claim-change-receipt",
            "version": 1,
            "request": request,
            "result": asdict(result),
        },
        ensure_ascii=True,
        allow_nan=False,
    )


def _accept_correction(
    connection: sqlite3.Connection,
    *,
    request: dict[str, object],
    operation_id: str,
    timestamp: str,
    proposed: ClaimInput,
    claim: sqlite3.Row,
    observed: dict[str, object],
) -> ChangeResult:
    identity = (
        normalize_identity_text(proposed.employee_id),
        normalize_identity_text(proposed.merchant_name),
        normalize_identity_text(proposed.invoice_number),
        str(Decimal(proposed.invoice_line_number)),
    )
    evidence_version = observed["evidence_version"] + 1
    state_version = observed["state_version"] + 1
    revision_id = str(uuid4())
    result = ChangeResult(
        claim_id=claim["claim_id"],
        operation_id=operation_id,
        action_kind=_ACTION,
        outcome="ACCEPTED",
        reason_code="EVIDENCE_ACCEPTED",
        event_id=operation_id,
        revision_id=revision_id,
        evidence_version_after=evidence_version,
        state_version_after=state_version,
        status_after=claim["status"],
        details_json=json.dumps(
            {
                "previous_evidence_version": observed["evidence_version"],
                "previous_state_version": observed["state_version"],
                "retained_reason_code": claim["reason_code"],
                "retained_question_event_id": claim["outstanding_question_event_id"],
            },
            ensure_ascii=True,
            allow_nan=False,
        ),
    )
    connection.execute("SAVEPOINT correction_operation")
    try:
        connection.execute("SAVEPOINT correction_mutation")
        connection.execute(
            """INSERT INTO claim_revisions (
                revision_id, claim_id, evidence_version, submitted_at, action_kind,
                disposition, raw_evidence_json, invoice_date, reimbursement_category,
                invoice_item_amount, requested_reimbursement, validation_details_json
            ) VALUES (?, ?, ?, ?, ?, 'ACCEPTED', ?, ?, ?, ?, ?, '{}')""",
            (
                revision_id,
                claim["claim_id"],
                evidence_version,
                timestamp,
                _ACTION,
                request["raw_evidence_json"],
                proposed.invoice_date.isoformat(),
                proposed.reimbursement_category.value,
                str(proposed.invoice_item_amount),
                str(proposed.requested_reimbursement),
            ),
        )
        try:
            cursor = connection.execute(
                """UPDATE claims SET
                    normalized_employee_id=?, normalized_merchant_name=?,
                    normalized_invoice_number=?, invoice_line_number=?,
                    current_evidence_version=current_evidence_version+1,
                    state_version=state_version+1
                WHERE claim_id=? AND status IS ?
                  AND status IN ('NEED_INFO', 'HUMAN_REVIEW')
                  AND current_evidence_version=? AND state_version=?""",
                (
                    *identity,
                    claim["claim_id"],
                    request["expected_status"],
                    request["expected_evidence_version"],
                    request["expected_state_version"],
                ),
            )
        except sqlite3.IntegrityError as error:
            # Only the real four-column identity constraint is a business
            # conflict. Trigger failures and other UNIQUE constraints propagate.
            if (
                error.sqlite_errorcode != sqlite3.SQLITE_CONSTRAINT_UNIQUE
                or str(error)
                != "UNIQUE constraint failed: claims.normalized_employee_id, "
                "claims.normalized_merchant_name, claims.normalized_invoice_number, "
                "claims.invoice_line_number"
            ):
                raise
            connection.execute("ROLLBACK TO SAVEPOINT correction_mutation")
            connection.execute("RELEASE SAVEPOINT correction_mutation")
            with closing(connection.cursor()) as owner_cursor:
                owner_cursor.row_factory = sqlite3.Row
                owner = owner_cursor.execute(
                    """SELECT claim_id FROM claims WHERE normalized_employee_id=?
                        AND normalized_merchant_name=? AND normalized_invoice_number=?
                        AND invoice_line_number=? AND claim_id<>?
                        AND (status IS NULL OR status IN (
                            'NEED_INFO', 'HUMAN_REVIEW', 'PROCESSABLE'))""",
                    (*identity, claim["claim_id"]),
                ).fetchone()
            if owner is None:
                raise
            result = _record_rejection(
                connection,
                request=request,
                operation_id=operation_id,
                timestamp=timestamp,
                outcome="DUPLICATE_CONFLICT",
                reason="IDENTITY_ALREADY_OWNED",
                details={
                    "conflicting_claim_id": owner["claim_id"],
                    "observed": observed,
                },
                observed=observed,
            )
        else:
            with closing(cursor):
                if cursor.rowcount != 1:
                    # Under the required serialized transaction these guards
                    # were just checked. Never accept a suppressed/altered write.
                    raise RuntimeError("Guarded correction did not update one claim.")
            connection.execute(
                """INSERT INTO claim_events (
                    event_id, claim_id, occurred_at, event_kind, evidence_version,
                    revision_id, from_status, to_status, details_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    operation_id,
                    claim["claim_id"],
                    timestamp,
                    _ACCEPTED_EVENT,
                    evidence_version,
                    revision_id,
                    claim["status"],
                    claim["status"],
                    _receipt_json(request, result),
                ),
            )
            connection.execute("RELEASE SAVEPOINT correction_mutation")
        connection.execute("RELEASE SAVEPOINT correction_operation")
    except BaseException:
        if connection.in_transaction:
            connection.execute("ROLLBACK TO SAVEPOINT correction_operation")
            connection.execute("RELEASE SAVEPOINT correction_operation")
        raise
    return result


def _record_rejection(
    connection: sqlite3.Connection,
    *,
    request: dict[str, object],
    operation_id: str,
    timestamp: str,
    outcome: str,
    reason: str,
    details: dict[str, object],
    observed: dict[str, object],
) -> ChangeResult:
    revision_id = None if outcome == "NOT_EDITABLE" else str(uuid4())
    details_json = json.dumps(details, ensure_ascii=True, allow_nan=False)
    result = ChangeResult(
        claim_id=request["claim_id"],
        operation_id=operation_id,
        action_kind=_ACTION,
        outcome=outcome,
        reason_code=reason,
        event_id=operation_id,
        revision_id=revision_id,
        evidence_version_after=observed["evidence_version"],
        state_version_after=observed["state_version"],
        status_after=observed["status"],
        details_json=details_json,
    )
    receipt_json = _receipt_json(request, result)
    connection.execute("SAVEPOINT correction_rejection")
    try:
        if revision_id is not None:
            connection.execute(
                """INSERT INTO claim_revisions (
                    revision_id, claim_id, submitted_at, action_kind, disposition,
                    raw_evidence_json, validation_details_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    revision_id,
                    request["claim_id"],
                    timestamp,
                    _ACTION,
                    outcome,
                    request["raw_evidence_json"],
                    details_json,
                ),
            )
        # Failed revisions have no evidence version. NULL avoids an inconsistent
        # composite reference between their ID and the current accepted version.
        connection.execute(
            """INSERT INTO claim_events (
                event_id, claim_id, occurred_at, event_kind, revision_id,
                from_status, to_status, details_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                operation_id,
                request["claim_id"],
                timestamp,
                _EVENT,
                revision_id,
                observed["status"],
                observed["status"],
                receipt_json,
            ),
        )
        connection.execute("RELEASE SAVEPOINT correction_rejection")
    except BaseException:
        if connection.in_transaction:
            connection.execute("ROLLBACK TO SAVEPOINT correction_rejection")
            connection.execute("RELEASE SAVEPOINT correction_rejection")
        raise
    return result
