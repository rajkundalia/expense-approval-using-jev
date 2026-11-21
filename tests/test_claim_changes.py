"""Guarded changes, operation receipts, audit integrity and transaction ownership."""

import json
import sqlite3
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from uuid import uuid1, uuid4

import pytest

from expense_approval.claim_changes import (
    MalformedOperationReceipt,
    OperationIdConflict,
    UnverifiableReplayConflict,
    cancel_claim,
    correct_claim,
)
from expense_approval.claim_store import (
    get_claim,
    insert_initial_claim,
    list_claim_events,
    list_claim_revisions,
)
from expense_approval.database import (
    connect_database,
    initialize_database,
    write_transaction,
)
from expense_approval.evidence import encode_raw_evidence

SUBMITTED = datetime(2026, 10, 31, 12, tzinfo=timezone.utc)
LATER = datetime(2027, 3, 1, 12, tzinfo=timezone.utc)


def payload() -> dict[str, object]:
    return {
        "employee_id": "emp-1",
        "merchant_name": "Shop",
        "invoice_number": "INV-1",
        "invoice_date": "2026-10-31",
        "invoice_item_name": "Running shoes",
        "invoice_item_amount": "1200",
        "reimbursement_category": "WELLNESS",
        "requested_reimbursement": "1000",
        "employee_justification": "For running",
    }


@pytest.fixture
def stored(tmp_path: Path) -> tuple[Path, str]:
    path = tmp_path / "claims.sqlite3"
    initialize_database(path)
    with connect_database(path) as connection:
        with write_transaction(connection):
            claim_id = insert_initial_claim(
                connection, raw_input=payload(), submitted_at=SUBMITTED
            )
            question = str(uuid4())
            connection.execute(
                """INSERT INTO claim_events (
                    event_id, claim_id, occurred_at, event_kind, evidence_version,
                    details_json
                ) VALUES (?, ?, ?, 'QUESTION_FIXTURE', 1, '{}')""",
                (question, claim_id, SUBMITTED.isoformat()),
            )
            connection.execute(
                """UPDATE claims SET status='NEED_INFO', reason_code='FIELD_CORRECTION',
                    uncertain_item_corrections=1, reliable_item_corrections=1,
                    category_corrections=2, semantic_responses=1,
                    outstanding_question_event_id=? WHERE claim_id=?""",
                (question, claim_id),
            )
    return path, claim_id


def attempt(connection, claim_id, **overrides):
    arguments = {
        "claim_id": claim_id,
        "operation_id": str(uuid4()),
        "action_kind": "ORDINARY_CORRECTION",
        "expected_status": "NEED_INFO",
        "expected_evidence_version": 1,
        "expected_state_version": 1,
        "raw_input": {**payload(), "requested_reimbursement": "0"},
        "occurred_at": LATER,
    }
    arguments.update(overrides)
    return correct_claim(connection, **arguments)


def cancel_attempt(connection, claim_id, **overrides):
    arguments = {
        "claim_id": claim_id,
        "operation_id": str(uuid4()),
        "expected_status": "NEED_INFO",
        "expected_evidence_version": 1,
        "expected_state_version": 1,
        "occurred_at": LATER,
    }
    arguments.update(overrides)
    return cancel_claim(connection, **arguments)


def snapshot(connection):
    return {
        table: connection.execute(f"SELECT * FROM {table}").fetchall()
        for table in ("claims", "claim_revisions", "claim_events", "evaluations")
    }


def assert_integrity(connection):
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    assert connection.execute("PRAGMA integrity_check").fetchall() == [("ok",)]


@pytest.mark.parametrize(
    "changes,reason",
    [
        ({"requested_reimbursement": "0"}, "INVALID_FIELDS"),
        ({"requested_reimbursement": "1200.001"}, "INVALID_FIELDS"),
        ({"requested_reimbursement": "1300"}, "INVALID_FIELDS"),
        ({"invoice_date": "bad"}, "INVALID_FIELDS"),
        ({"invoice_date": "2026-07-30"}, "INVALID_INVOICE_DATE"),
        ({"invoice_date": "2026-11-01"}, "INVALID_INVOICE_DATE"),
        ({"extra": "not allowed"}, "INVALID_FIELDS"),
    ],
)
def test_invalid_correction_preserves_claim_and_coherent_history(
    stored, changes, reason
):
    path, claim_id = stored
    raw = {**payload(), **changes}
    before_raw = raw.copy()
    operation = str(uuid4())
    with connect_database(path) as connection:
        before = dict(get_claim(connection, claim_id))
        with write_transaction(connection):
            result = attempt(
                connection, claim_id, operation_id=operation, raw_input=raw
            )
            assert connection.in_transaction
            assert dict(get_claim(connection, claim_id)) == before
        assert result.outcome == "INVALID"
        assert result.reason_code == reason
        assert result.event_id == result.operation_id == operation
        assert result.evidence_version_after == result.state_version_after == 1
        assert result.status_after == "NEED_INFO"
        assert not result.replayed
        revision = next(
            r
            for r in list_claim_revisions(connection, claim_id)
            if r["revision_id"] == result.revision_id
        )
        assert revision["evidence_version"] is None
        assert revision["disposition"] == "INVALID"
        assert revision["raw_evidence_json"] == encode_raw_evidence(raw)
        assert revision["submitted_at"] == LATER.isoformat(timespec="microseconds")
        assert revision["invoice_date"] is None
        assert json.loads(revision["validation_details_json"])["errors"]
        event = next(
            e
            for e in list_claim_events(connection, claim_id)
            if e["event_id"] == operation
        )
        assert event["revision_id"] == result.revision_id
        assert event["evidence_version"] is event["evaluation_id"] is None
        assert event["from_status"] == event["to_status"] == "NEED_INFO"
        assert len(list_claim_revisions(connection, claim_id)) == 2
        assert raw == before_raw
        with pytest.raises(FrozenInstanceError):
            result.outcome = "STALE"
        assert_integrity(connection)


@pytest.mark.parametrize(
    "overrides,guard",
    [
        ({"expected_status": "HUMAN_REVIEW"}, "status"),
        ({"expected_status": None}, "status"),
        ({"expected_evidence_version": 2}, "evidence_version"),
        ({"expected_state_version": 2}, "state_version"),
    ],
)
def test_stale_precedes_input_validation(stored, overrides, guard):
    path, claim_id = stored
    with connect_database(path) as connection:
        before = dict(get_claim(connection, claim_id))
        with write_transaction(connection):
            result = attempt(connection, claim_id, **overrides)
        assert result.outcome == "STALE"
        assert json.loads(result.details_json)["mismatched_guards"] == [guard]
        assert dict(get_claim(connection, claim_id)) == before
        assert (
            next(
                r
                for r in list_claim_revisions(connection, claim_id)
                if r["revision_id"] == result.revision_id
            )["disposition"]
            == "STALE"
        )
        assert_integrity(connection)


@pytest.mark.parametrize(
    "status", [None, "CANCELLED", "POLICY_RESTRICTION", "PROCESSABLE"]
)
@pytest.mark.parametrize("matching", [True, False])
def test_matching_noneditable_is_event_only_and_mismatch_is_stale(
    stored, status, matching
):
    path, claim_id = stored
    with connect_database(path) as connection:
        with write_transaction(connection):
            connection.execute(
                """UPDATE claims SET status=?, reason_code=NULL,
                    outstanding_question_event_id=NULL, uncertain_item_corrections=0,
                    reliable_item_corrections=0, category_corrections=0,
                    semantic_responses=0 WHERE claim_id=?""",
                (status, claim_id),
            )
        before = dict(get_claim(connection, claim_id))
        with write_transaction(connection):
            result = attempt(
                connection,
                claim_id,
                expected_status=status if matching else "NEED_INFO",
            )
        assert result.outcome == ("NOT_EDITABLE" if matching else "STALE")
        assert (result.revision_id is None) == matching
        assert result.evidence_version_after == result.state_version_after == 1
        assert result.status_after == status
        assert dict(get_claim(connection, claim_id)) == before
        event = next(
            e
            for e in list_claim_events(connection, claim_id)
            if e["event_id"] == result.event_id
        )
        assert event["from_status"] == event["to_status"] == status
        receipt = json.loads(event["details_json"])
        assert receipt["request"]["raw_evidence_json"] == encode_raw_evidence(
            {**payload(), "requested_reimbursement": "0"}
        )
        if matching:
            assert result.reason_code == "STATE_NOT_EDITABLE"
            assert len(list_claim_revisions(connection, claim_id)) == 1
        assert_integrity(connection)


@pytest.mark.parametrize("outcome", ["INVALID", "STALE", "NOT_EDITABLE"])
def test_replay_precedes_current_guards_and_returns_original_outcome(stored, outcome):
    path, claim_id = stored
    operation = str(uuid4())
    overrides = {"expected_state_version": 2} if outcome == "STALE" else {}
    with connect_database(path) as connection:
        if outcome == "NOT_EDITABLE":
            with write_transaction(connection):
                connection.execute(
                    "UPDATE claims SET status='CANCELLED' WHERE claim_id=?", (claim_id,)
                )
            overrides["expected_status"] = "CANCELLED"
        with write_transaction(connection):
            first = attempt(connection, claim_id, operation_id=operation, **overrides)
        assert first.outcome == outcome
        with write_transaction(connection):
            connection.execute(
                "UPDATE claims SET status='HUMAN_REVIEW', state_version=3 WHERE claim_id=?",
                (claim_id,),
            )
        before = snapshot(connection)
        with write_transaction(connection):
            replay = attempt(
                connection,
                claim_id,
                operation_id=operation,
                occurred_at=LATER + timedelta(days=1),
                **overrides,
            )
        assert replay == replace(first, replayed=True)
        assert replay.state_version_after == 1
        assert snapshot(connection) == before
        assert_integrity(connection)


@pytest.mark.parametrize(
    "changed", ["claim", "status", "evidence", "state", "input", "order"]
)
def test_reused_uuid_with_different_request_is_conflict(stored, changed):
    path, claim_id = stored
    operation = str(uuid4())
    with connect_database(path) as connection:
        with write_transaction(connection):
            attempt(connection, claim_id, operation_id=operation)
        overrides = {
            "claim": {"claim_id": "missing-other-claim"},
            "status": {"expected_status": "HUMAN_REVIEW"},
            "evidence": {"expected_evidence_version": 2},
            "state": {"expected_state_version": 2},
            "input": {"raw_input": {**payload(), "requested_reimbursement": "0.00"}},
            "order": {
                "raw_input": dict(
                    reversed(
                        list({**payload(), "requested_reimbursement": "0"}.items())
                    )
                )
            },
        }[changed]
        target = overrides.pop("claim_id", claim_id)
        before = snapshot(connection)
        with write_transaction(connection):
            with pytest.raises(OperationIdConflict):
                attempt(connection, target, operation_id=operation, **overrides)
        assert snapshot(connection) == before


@pytest.mark.parametrize("kind", ["initial", "different_action"])
def test_global_event_collision_is_never_a_successful_replay(stored, kind):
    path, claim_id = stored
    with connect_database(path) as connection:
        if kind == "initial":
            operation = connection.execute(
                "SELECT event_id FROM claim_events WHERE event_kind='INITIAL_CLAIM_STORED'"
            ).fetchone()[0]
        else:
            operation = str(uuid4())
            with write_transaction(connection):
                connection.execute(
                    """INSERT INTO claim_events (
                        event_id, claim_id, occurred_at, event_kind, details_json
                    ) VALUES (?, ?, ?, 'CLAIM_CHANGE_REJECTED', ?)""",
                    (
                        operation,
                        claim_id,
                        LATER.isoformat(),
                        json.dumps(
                            {
                                "format": "claim-change-receipt",
                                "version": 1,
                                "request": {
                                    "claim_id": claim_id,
                                    "action_kind": "CANCELLATION",
                                },
                            }
                        ),
                    ),
                )
        before = snapshot(connection)
        with write_transaction(connection):
            with pytest.raises(OperationIdConflict):
                attempt(connection, claim_id, operation_id=operation)
        assert snapshot(connection) == before


@pytest.mark.parametrize("capture", ["object", "cycle", "key", "same_object"])
def test_incomplete_capture_cannot_prove_replay(stored, capture):
    path, claim_id = stored
    operation = str(uuid4())
    original = object()

    def raw():
        value = {**payload(), "requested_reimbursement": "0"}
        if capture == "key":
            value[object()] = "extra"
        elif capture == "cycle":
            cycle = []
            cycle.append(cycle)
            value["requested_reimbursement"] = cycle
        else:
            value["requested_reimbursement"] = (
                original if capture == "same_object" else object()
            )
        return value

    with connect_database(path) as connection:
        with write_transaction(connection):
            first = attempt(
                connection, claim_id, operation_id=operation, raw_input=raw()
            )
        assert first.outcome == "INVALID"
        before = snapshot(connection)
        with write_transaction(connection):
            with pytest.raises(UnverifiableReplayConflict):
                attempt(connection, claim_id, operation_id=operation, raw_input=raw())
        assert snapshot(connection) == before
        assert_integrity(connection)


@pytest.mark.parametrize("incomplete_first", [True, False])
def test_either_side_incomplete_is_unverifiable(stored, incomplete_first):
    path, claim_id = stored
    operation = str(uuid4())
    inputs = [
        {**payload(), "requested_reimbursement": "0"},
        {**payload(), "requested_reimbursement": object()},
    ]
    if incomplete_first:
        inputs.reverse()
    with connect_database(path) as connection:
        with write_transaction(connection):
            attempt(connection, claim_id, operation_id=operation, raw_input=inputs[0])
        before = snapshot(connection)
        with write_transaction(connection):
            with pytest.raises(UnverifiableReplayConflict):
                attempt(
                    connection, claim_id, operation_id=operation, raw_input=inputs[1]
                )
        assert snapshot(connection) == before


def test_employee_text_resembling_descriptor_does_not_disable_replay(stored):
    path, claim_id = stored
    raw = {
        **payload(),
        "requested_reimbursement": "0",
        "employee_justification": '{"type":"incomplete"}',
    }
    operation = str(uuid4())
    with connect_database(path) as connection:
        with write_transaction(connection):
            first = attempt(connection, claim_id, operation_id=operation, raw_input=raw)
            replay = attempt(
                connection, claim_id, operation_id=operation, raw_input=raw
            )
        assert replay == replace(first, replayed=True)


@pytest.mark.parametrize(
    "table,noneditable",
    [
        ("claim_revisions", False),
        ("claim_events", False),
        ("claim_events", True),
    ],
)
def test_audit_failure_removes_operation_and_preserves_prior_work(
    stored, table, noneditable
):
    path, claim_id = stored
    operation = str(uuid4())
    with connect_database(path) as connection:
        with write_transaction(connection):
            other = insert_initial_claim(
                connection,
                raw_input={**payload(), "invoice_number": "other"},
                submitted_at=SUBMITTED,
            )
            if noneditable:
                connection.execute(
                    "UPDATE claims SET status='CANCELLED' WHERE claim_id=?", (claim_id,)
                )
            before = snapshot(connection)
            connection.execute(f"""CREATE TEMP TRIGGER fail_audit BEFORE INSERT ON {table}
                BEGIN SELECT RAISE(FAIL, 'forced audit failure'); END""")
            with pytest.raises(sqlite3.IntegrityError, match="forced audit failure"):
                attempt(
                    connection,
                    claim_id,
                    operation_id=operation,
                    expected_status="CANCELLED" if noneditable else "NEED_INFO",
                )
            assert connection.in_transaction
            assert snapshot(connection) == before
            connection.execute("DROP TRIGGER fail_audit")
        assert get_claim(connection, other) is not None
        with write_transaction(connection):
            result = attempt(
                connection,
                claim_id,
                operation_id=operation,
                expected_status="CANCELLED" if noneditable else "NEED_INFO",
            )
        assert not result.replayed
        assert_integrity(connection)


def test_receipt_is_provisional_and_outer_rollback_allows_fresh_attempt(stored):
    path, claim_id = stored
    operation = str(uuid4())
    with connect_database(path) as connection, connect_database(path) as observer:
        before = snapshot(connection)
        with pytest.raises(RuntimeError, match="outer rollback"):
            with write_transaction(connection):
                attempt(connection, claim_id, operation_id=operation)
                assert snapshot(observer) == before
                raise RuntimeError("outer rollback")
        assert snapshot(connection) == before
        with write_transaction(connection):
            fresh = attempt(connection, claim_id, operation_id=operation)
        assert not fresh.replayed
        assert observer.execute(
            "SELECT event_id FROM claim_events WHERE event_id=?", (operation,)
        ).fetchone() == (operation,)


def test_existing_caller_savepoint_and_connection_settings_survive(stored):
    path, claim_id = stored
    with connect_database(path) as connection:
        before = snapshot(connection)
        connection.row_factory = lambda cursor, row: tuple(row)
        factory = connection.row_factory
        with write_transaction(connection):
            connection.execute("SAVEPOINT caller_scope")
            attempt(connection, claim_id)
            assert connection.row_factory is factory
            connection.execute("ROLLBACK TO caller_scope")
            connection.execute("RELEASE caller_scope")
            assert snapshot(connection) == before
        assert_integrity(connection)


@pytest.mark.parametrize(
    "overrides",
    [
        {"operation_id": "bad"},
        {"operation_id": str(uuid1())},
        {"operation_id": str(uuid4()).upper()},
        {"operation_id": uuid4()},
        {"operation_id": "{" + str(uuid4()) + "}"},
        {"expected_state_version": True},
        {"expected_evidence_version": 0},
        {"expected_state_version": 1.0},
        {"expected_status": []},
        {"expected_status": "OTHER"},
        {"claim_id": " "},
        {"action_kind": "SEMANTIC_RESPONSE"},
        {"action_kind": "CANCELLATION"},
        {"raw_input": []},
        {"occurred_at": LATER.replace(tzinfo=None)},
        {"occurred_at": "2027-03-01"},
    ],
)
def test_invalid_internal_arguments_write_nothing(stored, overrides):
    path, claim_id = stored
    target = overrides.pop("claim_id", claim_id)
    with connect_database(path) as connection:
        before = snapshot(connection)
        with write_transaction(connection):
            with pytest.raises((ValueError, TypeError)):
                attempt(connection, target, **overrides)
        assert snapshot(connection) == before


def test_transaction_required_and_missing_claim_has_no_audit(stored):
    path, claim_id = stored
    with connect_database(path) as connection:
        before = snapshot(connection)
        with pytest.raises(ValueError, match="active caller-owned"):
            attempt(connection, claim_id)
        with write_transaction(connection):
            with pytest.raises(LookupError):
                attempt(connection, "missing")
        assert snapshot(connection) == before


@pytest.mark.parametrize("status", ["NEED_INFO", "HUMAN_REVIEW"])
def test_valid_original_date_is_accepted_against_original_submission(stored, status):
    path, claim_id = stored
    with connect_database(path) as connection:
        with write_transaction(connection):
            connection.execute(
                "UPDATE claims SET status=? WHERE claim_id=?", (status, claim_id)
            )
        before = dict(get_claim(connection, claim_id))
        with write_transaction(connection):
            result = attempt(
                connection, claim_id, raw_input=payload(), expected_status=status
            )
        assert result.outcome == "ACCEPTED"
        current = get_claim(connection, claim_id)
        assert current["submitted_at"] == before["submitted_at"]
        assert current["original_submission_date"] == before["original_submission_date"]
        assert current["current_invoice_date"] == "2026-10-31"
        assert_integrity(connection)


@pytest.mark.parametrize("commit_first", [True, False])
def test_writer_lock_then_committed_replay_or_rolled_back_fresh_attempt(
    stored, commit_first
):
    path, claim_id = stored
    operation = str(uuid4())
    with connect_database(path) as first, connect_database(path) as second:
        second.execute("PRAGMA busy_timeout=0")
        first.execute("BEGIN IMMEDIATE")
        original = attempt(first, claim_id, operation_id=operation)
        with pytest.raises(sqlite3.OperationalError, match="locked"):
            with write_transaction(second):
                pytest.fail("The second writer must not enter.")
        assert not second.in_transaction
        first.execute("COMMIT" if commit_first else "ROLLBACK")
        with write_transaction(second):
            result = attempt(second, claim_id, operation_id=operation)
        assert result.replayed == commit_first
        if commit_first:
            assert result == replace(original, replayed=True)
        else:
            assert result.revision_id != original.revision_id
        assert_integrity(second)


def test_missing_required_field_is_not_merged_from_accepted_evidence(stored):
    path, claim_id = stored
    raw = payload()
    del raw["employee_justification"]
    with connect_database(path) as connection:
        before = dict(get_claim(connection, claim_id))
        with write_transaction(connection):
            result = attempt(connection, claim_id, raw_input=raw)
        assert result.outcome == "INVALID"
        assert dict(get_claim(connection, claim_id)) == before
        assert json.loads(result.details_json)["errors"][0]["type"] == "missing"


def test_encoding_failure_propagates_without_operation_writes(stored, monkeypatch):
    path, claim_id = stored

    def fail_capture(value):
        raise RecursionError("forced capture failure")

    monkeypatch.setattr(
        "expense_approval.claim_changes.encode_raw_evidence", fail_capture
    )
    with connect_database(path) as connection:
        before = snapshot(connection)
        with write_transaction(connection):
            with pytest.raises(RecursionError, match="forced capture failure"):
                attempt(connection, claim_id)
            assert connection.in_transaction
        assert snapshot(connection) == before


def test_incomplete_capture_with_different_guards_is_definite_conflict(stored):
    path, claim_id = stored
    operation = str(uuid4())
    raw = {**payload(), "requested_reimbursement": object()}
    with connect_database(path) as connection:
        with write_transaction(connection):
            attempt(connection, claim_id, operation_id=operation, raw_input=raw)
        before = snapshot(connection)
        with write_transaction(connection):
            with pytest.raises(OperationIdConflict) as error:
                attempt(
                    connection,
                    claim_id,
                    operation_id=operation,
                    raw_input=raw,
                    expected_state_version=2,
                )
            assert type(error.value) is OperationIdConflict
        assert snapshot(connection) == before


def test_event_only_incomplete_rejection_preserves_first_audit(stored):
    path, claim_id = stored
    operation = str(uuid4())
    raw = {**payload(), "requested_reimbursement": object()}
    with connect_database(path) as connection:
        with write_transaction(connection):
            connection.execute(
                "UPDATE claims SET status='CANCELLED' WHERE claim_id=?", (claim_id,)
            )
            first = attempt(
                connection,
                claim_id,
                operation_id=operation,
                raw_input=raw,
                expected_status="CANCELLED",
            )
        assert first.revision_id is None
        before = snapshot(connection)
        with write_transaction(connection):
            with pytest.raises(UnverifiableReplayConflict):
                attempt(
                    connection,
                    claim_id,
                    operation_id=operation,
                    raw_input=raw,
                    expected_status="CANCELLED",
                )
        assert snapshot(connection) == before


def test_trusted_operation_time_is_stored_in_utc(stored):
    path, claim_id = stored
    local = LATER.astimezone(timezone(timedelta(hours=5, minutes=30)))
    with connect_database(path) as connection:
        with write_transaction(connection):
            result = attempt(connection, claim_id, occurred_at=local)
        event = next(
            e
            for e in list_claim_events(connection, claim_id)
            if e["event_id"] == result.event_id
        )
        assert event["occurred_at"] == LATER.isoformat(timespec="microseconds")


@pytest.mark.parametrize(
    "field,value",
    [
        ("request", "REMOVE"),
        ("request", None),
        ("request", []),
        ("request", "invalid"),
        ("request.expected_status", "REMOVE"),
        ("request.expected_status", []),
        ("request.expected_state_version", True),
        ("request.expected_evidence_version", "1"),
        ("request.extra", "unexpected"),
        ("request.raw_evidence_json", None),
        ("request.raw_evidence_json", "not json"),
        ("request.raw_evidence_json", "[]"),
        (
            "request.raw_evidence_json",
            '{"format":"raw-evidence","version":1,"value":{}}',
        ),
        ("result", "REMOVE"),
        ("result", None),
        ("result", []),
        ("result", "invalid"),
        ("result", {}),
        ("result.reason_code", "REMOVE"),
        ("result.extra", "unexpected"),
        ("result.outcome", "ACCEPTED"),
        ("result.outcome", []),
        ("result.reason_code", "STATE_NOT_EDITABLE"),
        ("result.state_version_after", True),
        ("result.evidence_version_after", 0),
        ("result.status_after", []),
        ("result.status_after", "CANCELLED"),
        ("result.operation_id", "wrong"),
        ("result.event_id", "wrong"),
        ("result.claim_id", "wrong"),
        ("result.action_kind", "CANCELLATION"),
        ("result.revision_id", None),
        ("result.replayed", True),
        ("result.details_json", "[]"),
        ("result.details_json", "not json"),
        ("version", True),
        ("version", 2),
    ],
)
def test_malformed_recognized_receipt_raises_explicit_error_without_writes(
    stored, field, value
):
    path, claim_id = stored
    operation = str(uuid4())
    with connect_database(path) as connection:
        with write_transaction(connection):
            original = attempt(connection, claim_id)
            event = next(
                e
                for e in list_claim_events(connection, claim_id)
                if e["event_id"] == original.event_id
            )
            receipt = json.loads(event["details_json"])
            receipt["result"]["operation_id"] = operation
            receipt["result"]["event_id"] = operation
            keys = field.split(".")
            target = receipt if len(keys) == 1 else receipt[keys[0]]
            if value == "REMOVE":
                del target[keys[-1]]
            else:
                target[keys[-1]] = value
            # Insert a separate immutable event; never alter existing history.
            connection.execute(
                """INSERT INTO claim_events (
                    event_id, claim_id, occurred_at, event_kind, revision_id,
                    from_status, to_status, details_json
                ) VALUES (?, ?, ?, 'CLAIM_CHANGE_REJECTED', ?, 'NEED_INFO', 'NEED_INFO', ?)""",
                (
                    operation,
                    claim_id,
                    LATER.isoformat(),
                    original.revision_id,
                    json.dumps(receipt),
                ),
            )
        before = snapshot(connection)
        with write_transaction(connection):
            with pytest.raises(MalformedOperationReceipt):
                attempt(connection, claim_id, operation_id=operation)
            assert connection.in_transaction
        assert snapshot(connection) == before
        assert_integrity(connection)


def test_unrecognized_receipt_format_remains_operation_id_collision(stored):
    path, claim_id = stored
    operation = str(uuid4())
    with connect_database(path) as connection:
        with write_transaction(connection):
            connection.execute(
                """INSERT INTO claim_events (
                    event_id, claim_id, occurred_at, event_kind, details_json
                ) VALUES (?, ?, ?, 'CLAIM_CHANGE_REJECTED', '{"format":"unrelated"}')""",
                (operation, claim_id, LATER.isoformat()),
            )
        before = snapshot(connection)
        with write_transaction(connection):
            with pytest.raises(OperationIdConflict):
                attempt(connection, claim_id, operation_id=operation)
        assert snapshot(connection) == before


@pytest.mark.parametrize(
    "changes,projection,value",
    [
        ({"employee_id": "  EMP-2  "}, "normalized_employee_id", "emp-2"),
        (
            {"merchant_name": " Straße  SHOP "},
            "normalized_merchant_name",
            "strasse shop",
        ),
        ({"invoice_number": " Inv  /  2 "}, "normalized_invoice_number", "inv / 2"),
        ({"invoice_line_number": 2}, "invoice_line_number", "2"),
        ({"invoice_item_name": "Other shoes"}, "normalized_invoice_number", "inv-1"),
        ({"invoice_date": "2026-07-31"}, "current_invoice_date", "2026-07-31"),
        (
            {"requested_reimbursement": "900.000"},
            "current_requested_reimbursement",
            "900.000",
        ),
        ({}, "normalized_invoice_number", "inv-1"),
    ],
)
def test_accepted_snapshot_identity_and_decision_context(
    stored, changes, projection, value
):
    path, claim_id = stored
    raw = {**payload(), **changes}
    operation = str(uuid4())
    with connect_database(path) as connection:
        before = dict(get_claim(connection, claim_id))
        history = snapshot(connection)
        with write_transaction(connection):
            result = attempt(
                connection, claim_id, raw_input=raw, operation_id=operation
            )
            assert connection.in_transaction
        assert result.outcome == "ACCEPTED"
        assert result.evidence_version_after == result.state_version_after == 2
        assert result.event_id == operation
        assert not result.replayed
        current = get_claim(connection, claim_id)
        assert current[projection] == value
        for key in (
            "status",
            "reason_code",
            "submitted_at",
            "original_submission_date",
            "outstanding_question_event_id",
            "uncertain_item_corrections",
            "reliable_item_corrections",
            "category_corrections",
            "semantic_responses",
        ):
            assert current[key] == before[key]
        revisions = list_claim_revisions(connection, claim_id)
        revision = next(r for r in revisions if r["revision_id"] == result.revision_id)
        assert revision["disposition"] == "ACCEPTED"
        assert revision["evidence_version"] == current["current_evidence_version"] == 2
        assert revision["raw_evidence_json"] == encode_raw_evidence(raw)
        assert revision["invoice_item_amount"] == "1200"
        assert revision["submitted_at"] == LATER.isoformat(timespec="microseconds")
        event = next(
            e
            for e in list_claim_events(connection, claim_id)
            if e["event_id"] == operation
        )
        assert event["event_kind"] == "CLAIM_CORRECTION_ACCEPTED"
        assert event["revision_id"] == result.revision_id
        assert event["evidence_version"] == 2
        assert event["evaluation_id"] is None
        assert event["from_status"] == event["to_status"] == "NEED_INFO"
        details = json.loads(result.details_json)
        assert (
            details["retained_question_event_id"]
            == before["outstanding_question_event_id"]
        )
        assert details["retained_reason_code"] == before["reason_code"]
        after = snapshot(connection)
        assert all(
            row in after["claim_revisions"] for row in history["claim_revisions"]
        )
        assert all(row in after["claim_events"] for row in history["claim_events"])
        assert after["evaluations"] == history["evaluations"]
        assert_integrity(connection)


def test_new_operations_accept_unchanged_values_and_old_guards_become_stale(stored):
    path, claim_id = stored
    with connect_database(path) as connection:
        with write_transaction(connection):
            first = attempt(connection, claim_id, raw_input=payload())
            stale = attempt(connection, claim_id, raw_input=payload())
            second = attempt(
                connection,
                claim_id,
                raw_input=payload(),
                expected_evidence_version=2,
                expected_state_version=2,
            )
        assert first.outcome == second.outcome == "ACCEPTED"
        assert stale.outcome == "STALE"
        assert second.evidence_version_after == second.state_version_after == 3
        assert get_claim(connection, claim_id)["current_evidence_version"] == 3
        assert len(list_claim_revisions(connection, claim_id)) == 4
        assert_integrity(connection)


@pytest.mark.parametrize("status", [None, "NEED_INFO", "HUMAN_REVIEW", "PROCESSABLE"])
def test_revised_duplicate_identity_rolls_back_candidate_and_audits_once(
    stored, status
):
    path, claim_id = stored
    raw = {**payload(), "invoice_number": "  TAKEN  "}
    operation = str(uuid4())
    with connect_database(path) as connection:
        with write_transaction(connection):
            owner = insert_initial_claim(
                connection,
                raw_input={**payload(), "invoice_number": "taken"},
                submitted_at=SUBMITTED,
            )
            connection.execute(
                "UPDATE claims SET status=? WHERE claim_id=?", (status, owner)
            )
        before = dict(get_claim(connection, claim_id))
        other_before = dict(get_claim(connection, owner))
        with write_transaction(connection):
            result = attempt(
                connection, claim_id, raw_input=raw, operation_id=operation
            )
        assert result.outcome == "DUPLICATE_CONFLICT"
        assert result.reason_code == "IDENTITY_ALREADY_OWNED"
        assert result.evidence_version_after == result.state_version_after == 1
        assert json.loads(result.details_json)["conflicting_claim_id"] == owner
        assert dict(get_claim(connection, claim_id)) == before
        assert dict(get_claim(connection, owner)) == other_before
        revisions = list_claim_revisions(connection, claim_id)
        assert len(revisions) == 2
        failed = next(r for r in revisions if r["revision_id"] == result.revision_id)
        assert failed["evidence_version"] is None
        assert failed["disposition"] == "DUPLICATE_CONFLICT"
        assert failed["raw_evidence_json"] == encode_raw_evidence(raw)
        event = next(
            e
            for e in list_claim_events(connection, claim_id)
            if e["event_id"] == operation
        )
        assert event["evidence_version"] is None
        assert event["revision_id"] == result.revision_id
        # Owner release does not change the recorded duplicate rejection.
        with write_transaction(connection):
            connection.execute(
                "UPDATE claims SET status='CANCELLED' WHERE claim_id=?", (owner,)
            )
        before_replay = snapshot(connection)
        with write_transaction(connection):
            replay = attempt(
                connection, claim_id, raw_input=raw, operation_id=operation
            )
        assert replay == replace(result, replayed=True)
        assert snapshot(connection) == before_replay
        assert_integrity(connection)


@pytest.mark.parametrize(
    "change",
    [
        {"employee_id": "emp-2"},
        {"merchant_name": "other"},
        {"invoice_number": "other"},
        {"invoice_line_number": 2},
    ],
)
def test_distinct_identity_components_do_not_conflict(stored, change):
    path, claim_id = stored
    with connect_database(path) as connection:
        with write_transaction(connection):
            insert_initial_claim(
                connection,
                raw_input={**payload(), "invoice_number": "taken"},
                submitted_at=SUBMITTED,
            )
            result = attempt(
                connection,
                claim_id,
                raw_input={**payload(), "invoice_number": "taken", **change},
            )
        assert result.outcome == "ACCEPTED"
        assert_integrity(connection)


@pytest.mark.parametrize("status", ["CANCELLED", "POLICY_RESTRICTION"])
def test_revised_identity_can_acquire_released_key(stored, status):
    path, claim_id = stored
    raw = {**payload(), "invoice_number": "taken"}
    with connect_database(path) as connection:
        with write_transaction(connection):
            owner = insert_initial_claim(
                connection, raw_input=raw, submitted_at=SUBMITTED
            )
            connection.execute(
                "UPDATE claims SET status=? WHERE claim_id=?", (status, owner)
            )
            result = attempt(connection, claim_id, raw_input=raw)
        assert result.outcome == "ACCEPTED"
        assert_integrity(connection)


@pytest.mark.parametrize("commit", [True, False])
def test_identity_ownership_is_atomic_across_connections(stored, commit):
    path, claim_id = stored
    raw = {**payload(), "invoice_number": "new"}
    with connect_database(path) as first, connect_database(path) as second:
        second.execute("PRAGMA busy_timeout=0")
        before = snapshot(second)
        first.execute("BEGIN IMMEDIATE")
        result = attempt(first, claim_id, raw_input=raw)
        assert result.outcome == "ACCEPTED"
        assert get_claim(first, claim_id)["normalized_invoice_number"] == "new"
        assert snapshot(second) == before
        with pytest.raises(sqlite3.OperationalError, match="locked"):
            with write_transaction(second):
                pytest.fail("No other writer can acquire either key mid-operation.")
        first.execute("COMMIT" if commit else "ROLLBACK")
        free = payload() if commit else raw
        blocked = raw if commit else payload()
        with write_transaction(second):
            insert_initial_claim(second, raw_input=free, submitted_at=SUBMITTED)
        with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
            with write_transaction(second):
                insert_initial_claim(second, raw_input=blocked, submitted_at=SUBMITTED)
        assert get_claim(second, claim_id)["current_evidence_version"] == (
            2 if commit else 1
        )
        assert_integrity(second)


def test_accepted_replay_after_new_evidence_and_terminal_state(stored):
    path, claim_id = stored
    operation = str(uuid4())
    raw = {**payload(), "invoice_number": "new"}
    with connect_database(path) as connection:
        with write_transaction(connection):
            first = attempt(connection, claim_id, raw_input=raw, operation_id=operation)
            attempt(
                connection,
                claim_id,
                raw_input=payload(),
                expected_evidence_version=2,
                expected_state_version=2,
            )
            connection.execute(
                "UPDATE claims SET status='CANCELLED', state_version=4 WHERE claim_id=?",
                (claim_id,),
            )
        before = snapshot(connection)
        with write_transaction(connection):
            replay = attempt(
                connection, claim_id, raw_input=raw, operation_id=operation
            )
            with pytest.raises(OperationIdConflict):
                attempt(
                    connection, claim_id, raw_input=payload(), operation_id=operation
                )
        assert replay == replace(first, replayed=True)
        assert replay.evidence_version_after == replay.state_version_after == 2
        assert snapshot(connection) == before


@pytest.mark.parametrize(
    "failure", ["revision", "update", "event", "ignored_update", "unrelated_unique"]
)
def test_accepted_operation_failure_restores_state_and_preserves_outer_work(
    stored, failure
):
    path, claim_id = stored
    operation = str(uuid4())
    with connect_database(path) as connection:
        with write_transaction(connection):
            other = insert_initial_claim(
                connection,
                raw_input={**payload(), "invoice_number": "taken"},
                submitted_at=SUBMITTED,
            )
            before = snapshot(connection)
            if failure == "unrelated_unique":
                connection.execute("CREATE TEMP TABLE unrelated (value TEXT UNIQUE)")
                connection.execute("INSERT INTO unrelated VALUES ('exists')")
                trigger = "BEFORE UPDATE ON claims BEGIN INSERT INTO unrelated VALUES ('exists'); END"
            else:
                timing = {
                    "revision": "BEFORE INSERT ON claim_revisions WHEN NEW.disposition='ACCEPTED'",
                    "update": "BEFORE UPDATE ON claims",
                    "ignored_update": "BEFORE UPDATE ON claims",
                    "event": "BEFORE INSERT ON claim_events WHEN NEW.event_kind='CLAIM_CORRECTION_ACCEPTED'",
                }[failure]
                action = (
                    "RAISE(IGNORE)"
                    if failure == "ignored_update"
                    else "RAISE(FAIL, 'forced mutation failure')"
                )
                trigger = f"{timing} BEGIN SELECT {action}; END"
            connection.execute(f"CREATE TEMP TRIGGER fail_mutation {trigger}")
            expected_error = (
                RuntimeError if failure == "ignored_update" else sqlite3.IntegrityError
            )
            with pytest.raises(expected_error):
                attempt(
                    connection,
                    claim_id,
                    raw_input={
                        **payload(),
                        "invoice_number": (
                            "taken" if failure == "unrelated_unique" else "new"
                        ),
                    },
                    operation_id=operation,
                )
            assert connection.in_transaction
            assert snapshot(connection) == before
            connection.execute("DROP TRIGGER fail_mutation")
            retry = attempt(
                connection,
                claim_id,
                raw_input={**payload(), "invoice_number": "new"},
                operation_id=operation,
            )
            assert retry.outcome == "ACCEPTED"
            assert not retry.replayed
        assert get_claim(connection, other) is not None
        assert_integrity(connection)


@pytest.mark.parametrize("failure", ["revision", "event"])
def test_duplicate_audit_failure_leaves_no_candidate_revision_or_claim_mutation(
    stored, failure
):
    path, claim_id = stored
    with connect_database(path) as connection:
        with write_transaction(connection):
            insert_initial_claim(
                connection,
                raw_input={**payload(), "invoice_number": "taken"},
                submitted_at=SUBMITTED,
            )
            before = snapshot(connection)
            table, condition = (
                ("claim_revisions", "NEW.disposition='DUPLICATE_CONFLICT'")
                if failure == "revision"
                else ("claim_events", "NEW.event_kind='CLAIM_CHANGE_REJECTED'")
            )
            connection.execute(f"""CREATE TEMP TRIGGER fail_duplicate_audit BEFORE INSERT ON {table}
                WHEN {condition} BEGIN SELECT RAISE(FAIL, 'forced duplicate audit failure'); END""")
            with pytest.raises(
                sqlite3.IntegrityError, match="forced duplicate audit failure"
            ):
                attempt(
                    connection,
                    claim_id,
                    raw_input={**payload(), "invoice_number": "taken"},
                )
            assert connection.in_transaction
            assert snapshot(connection) == before
        assert_integrity(connection)


def test_accepted_change_respects_existing_caller_savepoint(stored):
    path, claim_id = stored
    with connect_database(path) as connection:
        before = snapshot(connection)
        with write_transaction(connection):
            connection.execute("SAVEPOINT caller_scope")
            result = attempt(connection, claim_id, raw_input=payload())
            assert result.outcome == "ACCEPTED"
            connection.execute("ROLLBACK TO caller_scope")
            connection.execute("RELEASE caller_scope")
        assert snapshot(connection) == before


def test_accepted_history_is_immutable(stored):
    path, claim_id = stored
    with connect_database(path) as connection:
        with write_transaction(connection):
            result = attempt(connection, claim_id, raw_input=payload())
        before = snapshot(connection)
        for sql, identifier in (
            (
                "UPDATE claim_revisions SET requested_reimbursement='1' WHERE revision_id=?",
                result.revision_id,
            ),
            ("DELETE FROM claim_revisions WHERE revision_id=?", result.revision_id),
            ("DELETE FROM claim_events WHERE event_id=?", result.event_id),
        ):
            with pytest.raises(sqlite3.IntegrityError, match="immutable"):
                with write_transaction(connection):
                    connection.execute(sql, (identifier,))
        assert snapshot(connection) == before
        assert_integrity(connection)


@pytest.mark.parametrize("guard", ["evidence", "state"])
def test_valid_correction_with_one_stale_version_preserves_new_evidence(stored, guard):
    path, claim_id = stored
    with connect_database(path) as connection:
        with write_transaction(connection):
            attempt(
                connection, claim_id, raw_input={**payload(), "invoice_number": "new"}
            )
        before = dict(get_claim(connection, claim_id))
        with write_transaction(connection):
            result = attempt(
                connection,
                claim_id,
                raw_input=payload(),
                expected_evidence_version=1 if guard == "evidence" else 2,
                expected_state_version=1 if guard == "state" else 2,
            )
        assert result.outcome == "STALE"
        assert result.evidence_version_after == result.state_version_after == 2
        assert dict(get_claim(connection, claim_id)) == before


def test_complete_replacement_omitted_line_resets_to_default(stored):
    path, claim_id = stored
    with connect_database(path) as connection:
        with write_transaction(connection):
            attempt(
                connection, claim_id, raw_input={**payload(), "invoice_line_number": 2}
            )
            result = attempt(
                connection,
                claim_id,
                raw_input=payload(),
                expected_evidence_version=2,
                expected_state_version=2,
            )
        current = get_claim(connection, claim_id)
        assert result.outcome == "ACCEPTED"
        assert current["invoice_line_number"] == "1"
        assert current["current_raw_evidence_json"] == encode_raw_evidence(payload())


def test_large_exact_line_projection_in_correction(stored):
    path, claim_id = stored
    line = 10**5000
    with connect_database(path) as connection:
        with write_transaction(connection):
            result = attempt(
                connection,
                claim_id,
                raw_input={**payload(), "invoice_line_number": line},
            )
        assert result.outcome == "ACCEPTED"
        assert (
            get_claim(connection, claim_id)["invoice_line_number"] == "1" + "0" * 5000
        )
        assert_integrity(connection)


@pytest.mark.parametrize("commit", [True, False])
def test_competing_corrections_to_same_identity_serialize(stored, commit):
    path, claim_id = stored
    with connect_database(path) as first, connect_database(path) as second:
        with write_transaction(first):
            other = insert_initial_claim(
                first,
                raw_input={**payload(), "invoice_number": "other"},
                submitted_at=SUBMITTED,
            )
            first.execute(
                "UPDATE claims SET status='HUMAN_REVIEW' WHERE claim_id=?", (other,)
            )
        second.execute("PRAGMA busy_timeout=0")
        first.execute("BEGIN IMMEDIATE")
        attempt(first, claim_id, raw_input={**payload(), "invoice_number": "target"})
        with pytest.raises(sqlite3.OperationalError, match="locked"):
            with write_transaction(second):
                pytest.fail("Second correction cannot enter before first resolves.")
        first.execute("COMMIT" if commit else "ROLLBACK")
        with write_transaction(second):
            result = attempt(
                second,
                other,
                expected_status="HUMAN_REVIEW",
                raw_input={**payload(), "invoice_number": "target"},
            )
        assert result.outcome == ("DUPLICATE_CONFLICT" if commit else "ACCEPTED")
        assert_integrity(second)


@pytest.mark.parametrize("outcome", ["ACCEPTED", "DUPLICATE_CONFLICT"])
@pytest.mark.parametrize(
    "field,value",
    [
        ("evidence_version_after", 4),
        ("state_version_after", True),
        ("status_after", "CANCELLED"),
        ("reason_code", "INVALID_FIELDS"),
        ("outcome", "NOT_EDITABLE"),
    ],
)
def test_new_outcome_receipts_retain_malformed_data_safeguards(
    stored, outcome, field, value
):
    path, claim_id = stored
    operation = str(uuid4())
    raw = {**payload(), "invoice_number": "target"}
    with connect_database(path) as connection:
        with write_transaction(connection):
            if outcome == "DUPLICATE_CONFLICT":
                insert_initial_claim(connection, raw_input=raw, submitted_at=SUBMITTED)
            original = attempt(connection, claim_id, raw_input=raw)
            assert original.outcome == outcome
            event = next(
                e
                for e in list_claim_events(connection, claim_id)
                if e["event_id"] == original.event_id
            )
            receipt = json.loads(event["details_json"])
            receipt["result"]["operation_id"] = operation
            receipt["result"]["event_id"] = operation
            receipt["result"][field] = value
            connection.execute(
                """INSERT INTO claim_events (
                    event_id, claim_id, occurred_at, event_kind, revision_id,
                    evidence_version, from_status, to_status, details_json
                ) VALUES (?, ?, ?, ?, ?, ?, 'NEED_INFO', 'NEED_INFO', ?)""",
                (
                    operation,
                    claim_id,
                    LATER.isoformat(),
                    event["event_kind"],
                    original.revision_id,
                    event["evidence_version"],
                    json.dumps(receipt),
                ),
            )
        before = snapshot(connection)
        with write_transaction(connection):
            with pytest.raises(MalformedOperationReceipt):
                attempt(connection, claim_id, raw_input=raw, operation_id=operation)
        assert snapshot(connection) == before
        assert_integrity(connection)


def test_accepted_incomplete_raw_capture_does_not_prove_replay(stored):
    from expense_approval.claim_input import ReimbursementCategory

    path, claim_id = stored
    operation = str(uuid4())
    # The existing parser accepts the enum; the raw encoder records subclasses
    # as incomplete. Do not invent equality for this otherwise valid input.
    raw = {**payload(), "reimbursement_category": ReimbursementCategory.WELLNESS}
    with connect_database(path) as connection:
        with write_transaction(connection):
            first = attempt(connection, claim_id, raw_input=raw, operation_id=operation)
        assert first.outcome == "ACCEPTED"
        before = snapshot(connection)
        with write_transaction(connection):
            with pytest.raises(UnverifiableReplayConflict):
                attempt(connection, claim_id, raw_input=raw, operation_id=operation)
        assert snapshot(connection) == before


@pytest.mark.parametrize("status", ["NEED_INFO", "HUMAN_REVIEW"])
@pytest.mark.parametrize("revised", [False, True])
def test_cancellation_preserves_evidence_and_historical_question(
    stored, status, revised
):
    path, claim_id = stored
    operation = str(uuid4())
    explanation = "  No longer claiming — personal choice  "
    with connect_database(path) as connection:
        with write_transaction(connection):
            connection.execute(
                "UPDATE claims SET status=? WHERE claim_id=?", (status, claim_id)
            )
            if revised:
                attempt(
                    connection,
                    claim_id,
                    expected_status=status,
                    raw_input={**payload(), "invoice_number": "corrected"},
                )
        before = dict(get_claim(connection, claim_id))
        history = snapshot(connection)
        version = 2 if revised else 1
        with write_transaction(connection):
            result = cancel_attempt(
                connection,
                claim_id,
                operation_id=operation,
                expected_status=status,
                expected_evidence_version=version,
                expected_state_version=version,
                cancellation_reason=explanation,
            )
            assert connection.in_transaction
        assert result.outcome == "CANCELLED"
        assert result.reason_code == "CANCELLED_BY_EMPLOYEE"
        assert result.action_kind == "CANCELLATION"
        assert result.status_after == "CANCELLED"
        assert result.revision_id is None
        assert result.evidence_version_after == version
        assert result.state_version_after == version + 1
        current = dict(get_claim(connection, claim_id))
        expected = {
            **before,
            "status": "CANCELLED",
            "reason_code": "CANCELLED_BY_EMPLOYEE",
            "state_version": version + 1,
            "outstanding_question_event_id": None,
        }
        assert current == expected
        after = snapshot(connection)
        assert after["claim_revisions"] == history["claim_revisions"]
        assert after["evaluations"] == history["evaluations"]
        assert all(row in after["claim_events"] for row in history["claim_events"])
        events = list_claim_events(connection, claim_id)
        assert any(
            e["event_id"] == before["outstanding_question_event_id"] for e in events
        )
        event = next(e for e in events if e["event_id"] == operation)
        assert event["event_kind"] == "CLAIM_CANCELLED"
        assert event["from_status"] == status
        assert event["to_status"] == "CANCELLED"
        assert event["evidence_version"] == version
        assert event["revision_id"] is event["evaluation_id"] is None
        details = json.loads(result.details_json)
        assert details["previous_status"] == status
        assert details["previous_reason_code"] == before["reason_code"]
        assert (
            details["previous_question_event_id"]
            == before["outstanding_question_event_id"]
        )
        assert details["cancellation_reason"] == explanation
        assert_integrity(connection)


@pytest.mark.parametrize(
    "status", [None, "POLICY_RESTRICTION", "CANCELLED", "PROCESSABLE"]
)
@pytest.mark.parametrize("matching", [True, False])
def test_cancellation_noneditable_and_stale_are_distinct_event_only_rejections(
    stored, status, matching
):
    path, claim_id = stored
    with connect_database(path) as connection:
        with write_transaction(connection):
            connection.execute(
                """UPDATE claims SET status=?, reason_code=NULL,
                    outstanding_question_event_id=NULL, uncertain_item_corrections=0,
                    reliable_item_corrections=0, category_corrections=0,
                    semantic_responses=0 WHERE claim_id=?""",
                (status, claim_id),
            )
        before = snapshot(connection)
        with write_transaction(connection):
            result = cancel_attempt(
                connection,
                claim_id,
                expected_status=status if matching else "NEED_INFO",
            )
        assert result.outcome == ("NOT_EDITABLE" if matching else "STALE")
        assert result.status_after == status
        assert result.revision_id is None
        assert result.evidence_version_after == result.state_version_after == 1
        after = snapshot(connection)
        for table in ("claims", "claim_revisions", "evaluations"):
            assert after[table] == before[table]
        event = next(
            e
            for e in list_claim_events(connection, claim_id)
            if e["event_id"] == result.event_id
        )
        assert event["event_kind"] == "CLAIM_CHANGE_REJECTED"
        assert event["revision_id"] is event["evidence_version"] is None
        assert event["from_status"] == event["to_status"] == status
        assert_integrity(connection)


@pytest.mark.parametrize(
    "overrides,guard",
    [
        ({"expected_status": "HUMAN_REVIEW"}, "status"),
        ({"expected_evidence_version": 2}, "evidence_version"),
        ({"expected_state_version": 2}, "state_version"),
    ],
)
def test_cancellation_stale_guard_does_not_mutate_claim(stored, overrides, guard):
    path, claim_id = stored
    with connect_database(path) as connection:
        before = dict(get_claim(connection, claim_id))
        with write_transaction(connection):
            result = cancel_attempt(connection, claim_id, **overrides)
        assert result.outcome == "STALE"
        assert json.loads(result.details_json)["mismatched_guards"] == [guard]
        assert dict(get_claim(connection, claim_id)) == before
        assert len(list_claim_revisions(connection, claim_id)) == 1


def test_cancel_replay_after_key_is_acquired_by_another_claim(stored):
    path, claim_id = stored
    operation = str(uuid4())
    with connect_database(path) as connection:
        with write_transaction(connection):
            result = cancel_attempt(connection, claim_id, operation_id=operation)
            other = insert_initial_claim(
                connection, raw_input=payload(), submitted_at=SUBMITTED
            )
            # Direct SQL fixture: replay must not depend on later current state.
            connection.execute(
                "UPDATE claims SET state_version=3 WHERE claim_id=?", (claim_id,)
            )
        before = snapshot(connection)
        with write_transaction(connection):
            replay = cancel_attempt(
                connection,
                claim_id,
                operation_id=operation,
                occurred_at=LATER + timedelta(days=1),
            )
        assert replay == replace(result, replayed=True)
        assert replay.state_version_after == 2
        assert snapshot(connection) == before
        assert get_claim(connection, other) is not None
        assert_integrity(connection)


@pytest.mark.parametrize("outcome", ["STALE", "NOT_EDITABLE"])
def test_rejected_cancellation_replay_preserves_original_outcome(stored, outcome):
    path, claim_id = stored
    operation = str(uuid4())
    overrides = (
        {"expected_state_version": 2}
        if outcome == "STALE"
        else {"expected_status": "CANCELLED"}
    )
    with connect_database(path) as connection:
        with write_transaction(connection):
            if outcome == "NOT_EDITABLE":
                connection.execute(
                    "UPDATE claims SET status='CANCELLED' WHERE claim_id=?", (claim_id,)
                )
            result = cancel_attempt(
                connection, claim_id, operation_id=operation, **overrides
            )
        assert result.outcome == outcome
        with write_transaction(connection):
            connection.execute(
                "UPDATE claims SET status='NEED_INFO', state_version=2 WHERE claim_id=?",
                (claim_id,),
            )
        before = snapshot(connection)
        with write_transaction(connection):
            replay = cancel_attempt(
                connection, claim_id, operation_id=operation, **overrides
            )
        assert replay == replace(result, replayed=True)
        assert snapshot(connection) == before


@pytest.mark.parametrize(
    "overrides",
    [
        {"cancellation_reason": "changed"},
        {"cancellation_reason": ""},
        {"expected_status": "CANCELLED"},
        {"expected_evidence_version": 2},
        {"expected_state_version": 2},
        {"claim_id": "another-claim"},
    ],
)
def test_cancel_operation_id_reuse_with_changed_request_conflicts(stored, overrides):
    path, claim_id = stored
    operation = str(uuid4())
    target = overrides.get("claim_id", claim_id)
    arguments = {key: value for key, value in overrides.items() if key != "claim_id"}
    with connect_database(path) as connection:
        with write_transaction(connection):
            cancel_attempt(connection, claim_id, operation_id=operation)
        before = snapshot(connection)
        with write_transaction(connection):
            with pytest.raises(OperationIdConflict):
                cancel_attempt(connection, target, operation_id=operation, **arguments)
        assert snapshot(connection) == before


@pytest.mark.parametrize(
    "first_action",
    [
        "accepted_correction",
        "rejected_correction",
        "accepted_cancel",
        "rejected_cancel",
    ],
)
def test_real_cross_action_operation_id_collisions(stored, first_action):
    path, claim_id = stored
    operation = str(uuid4())
    with connect_database(path) as connection:
        with write_transaction(connection):
            if first_action.endswith("correction"):
                attempt(
                    connection,
                    claim_id,
                    operation_id=operation,
                    raw_input=payload()
                    if first_action == "accepted_correction"
                    else {**payload(), "requested_reimbursement": "0"},
                )
            else:
                cancel_attempt(
                    connection,
                    claim_id,
                    operation_id=operation,
                    expected_state_version=2
                    if first_action == "rejected_cancel"
                    else 1,
                )
        before = snapshot(connection)
        with write_transaction(connection):
            with pytest.raises(OperationIdConflict):
                if first_action.endswith("correction"):
                    cancel_attempt(connection, claim_id, operation_id=operation)
                else:
                    attempt(connection, claim_id, operation_id=operation)
        assert snapshot(connection) == before


@pytest.mark.parametrize("outcome", ["CANCELLED", "STALE", "NOT_EDITABLE"])
def test_cancel_event_failure_rolls_back_operation_preserving_outer_work(
    stored, outcome
):
    path, claim_id = stored
    operation = str(uuid4())
    overrides = {"expected_state_version": 2} if outcome == "STALE" else {}
    with connect_database(path) as connection:
        with write_transaction(connection):
            other = insert_initial_claim(
                connection,
                raw_input={**payload(), "invoice_number": "other"},
                submitted_at=SUBMITTED,
            )
            if outcome == "NOT_EDITABLE":
                connection.execute(
                    "UPDATE claims SET status='CANCELLED' WHERE claim_id=?", (claim_id,)
                )
                overrides["expected_status"] = "CANCELLED"
            before = snapshot(connection)
            connection.execute("""CREATE TEMP TRIGGER fail_cancel_event BEFORE INSERT ON claim_events
                BEGIN SELECT RAISE(FAIL, 'forced cancellation event failure'); END""")
            with pytest.raises(
                sqlite3.IntegrityError, match="forced cancellation event failure"
            ):
                cancel_attempt(
                    connection, claim_id, operation_id=operation, **overrides
                )
            assert connection.in_transaction
            assert snapshot(connection) == before
            connection.execute("DROP TRIGGER fail_cancel_event")
            retry = cancel_attempt(
                connection, claim_id, operation_id=operation, **overrides
            )
            assert retry.outcome == outcome
            assert not retry.replayed
        assert get_claim(connection, other) is not None
        assert_integrity(connection)


@pytest.mark.parametrize("ignore", [False, True])
def test_cancel_update_failure_does_not_create_receipt(stored, ignore):
    path, claim_id = stored
    with connect_database(path) as connection:
        before = snapshot(connection)
        with write_transaction(connection):
            action = (
                "RAISE(IGNORE)"
                if ignore
                else "RAISE(FAIL, 'forced cancellation update failure')"
            )
            connection.execute(
                f"CREATE TEMP TRIGGER fail_cancel_update BEFORE UPDATE ON claims BEGIN SELECT {action}; END"
            )
            with pytest.raises(RuntimeError if ignore else sqlite3.IntegrityError):
                cancel_attempt(connection, claim_id)
            assert snapshot(connection) == before
            connection.execute("DROP TRIGGER fail_cancel_update")
        assert_integrity(connection)


@pytest.mark.parametrize("commit", [True, False])
def test_cancellation_key_release_is_atomic_and_rollback_restores_ownership(
    stored, commit
):
    path, claim_id = stored
    with connect_database(path) as first, connect_database(path) as second:
        second.execute("PRAGMA busy_timeout=0")
        before = snapshot(second)
        first.execute("BEGIN IMMEDIATE")
        result = cancel_attempt(first, claim_id)
        assert result.outcome == "CANCELLED"
        assert snapshot(second) == before
        with pytest.raises(sqlite3.OperationalError, match="locked"):
            with write_transaction(second):
                pytest.fail(
                    "Other writers cannot acquire the key before transaction resolution."
                )
        first.execute("COMMIT" if commit else "ROLLBACK")
        if commit:
            with write_transaction(second):
                insert_initial_claim(
                    second, raw_input=payload(), submitted_at=SUBMITTED
                )
            assert get_claim(second, claim_id)["status"] == "CANCELLED"
        else:
            assert snapshot(second) == before
            with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
                with write_transaction(second):
                    insert_initial_claim(
                        second, raw_input=payload(), submitted_at=SUBMITTED
                    )
        assert_integrity(second)


@pytest.mark.parametrize("first_action", ["correction", "cancellation"])
@pytest.mark.parametrize("commit", [True, False])
def test_cancellation_and_correction_cannot_overwrite_each_other(
    stored, first_action, commit
):
    path, claim_id = stored
    with connect_database(path) as first, connect_database(path) as second:
        second.execute("PRAGMA busy_timeout=0")
        first.execute("BEGIN IMMEDIATE")
        if first_action == "correction":
            initial = attempt(
                first, claim_id, raw_input={**payload(), "invoice_number": "corrected"}
            )
        else:
            initial = cancel_attempt(first, claim_id)
        with pytest.raises(sqlite3.OperationalError, match="locked"):
            with write_transaction(second):
                pytest.fail("Competing operation cannot enter yet.")
        first.execute("COMMIT" if commit else "ROLLBACK")
        before = dict(get_claim(second, claim_id))
        with write_transaction(second):
            if first_action == "correction":
                result = cancel_attempt(second, claim_id)
                expected = "CANCELLED"
            else:
                result = attempt(
                    second,
                    claim_id,
                    raw_input={**payload(), "invoice_number": "corrected"},
                )
                expected = "ACCEPTED"
        assert result.outcome == ("STALE" if commit else expected)
        if commit:
            assert dict(get_claim(second, claim_id)) == before
            assert before["state_version"] == initial.state_version_after
        assert_integrity(second)


def test_cancellation_respects_existing_caller_savepoint_and_connection_settings(
    stored,
):
    path, claim_id = stored
    with connect_database(path) as connection:
        before = snapshot(connection)

        def factory(cursor, row):
            return tuple(row)

        connection.row_factory = factory
        with write_transaction(connection):
            connection.execute("SAVEPOINT caller_scope")
            cancel_attempt(connection, claim_id)
            assert connection.row_factory is factory
            connection.execute("ROLLBACK TO caller_scope")
            connection.execute("RELEASE caller_scope")
        assert snapshot(connection) == before


@pytest.mark.parametrize(
    "overrides",
    [
        {"operation_id": "bad"},
        {"operation_id": str(uuid1())},
        {"operation_id": "AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA"},
        {"operation_id": uuid4()},
        {"expected_status": []},
        {"expected_status": "OTHER"},
        {"expected_evidence_version": True},
        {"expected_state_version": 0},
        {"expected_state_version": 1.0},
        {"occurred_at": LATER.replace(tzinfo=None)},
        {"occurred_at": "not a datetime"},
        {"cancellation_reason": []},
        {"cancellation_reason": 1},
        {"claim_id": " "},
    ],
)
def test_cancellation_internal_argument_errors_leave_no_records(stored, overrides):
    path, claim_id = stored
    target = overrides.get("claim_id", claim_id)
    arguments = {key: value for key, value in overrides.items() if key != "claim_id"}
    with connect_database(path) as connection:
        before = snapshot(connection)
        with write_transaction(connection):
            with pytest.raises((ValueError, TypeError)):
                cancel_attempt(connection, target, **arguments)
        assert snapshot(connection) == before


def test_cancellation_requires_transaction_and_existing_claim(stored):
    path, claim_id = stored
    with connect_database(path) as connection:
        before = snapshot(connection)
        with pytest.raises(ValueError, match="active caller-owned"):
            cancel_attempt(connection, claim_id)
        with write_transaction(connection):
            with pytest.raises(LookupError):
                cancel_attempt(connection, "missing")
        assert snapshot(connection) == before


@pytest.mark.parametrize(
    "field,value",
    [
        ("request", None),
        ("request.cancellation_reason", []),
        ("request.cancellation_reason", "REMOVE"),
        ("request.extra", "unexpected"),
        ("result", []),
        ("result.state_version_after", True),
        ("result.state_version_after", 1),
        ("result.evidence_version_after", 2),
        ("result.outcome", "ACCEPTED"),
        ("result.reason_code", "EVIDENCE_ACCEPTED"),
        ("result.revision_id", "some-revision"),
        ("result.status_after", "NEED_INFO"),
    ],
)
def test_cancellation_receipt_validation_rejects_malformed_stored_data(
    stored, field, value
):
    path, claim_id = stored
    operation = str(uuid4())
    with connect_database(path) as connection:
        with write_transaction(connection):
            original = cancel_attempt(connection, claim_id)
            event = next(
                e
                for e in list_claim_events(connection, claim_id)
                if e["event_id"] == original.event_id
            )
            receipt = json.loads(event["details_json"])
            receipt["result"]["operation_id"] = operation
            receipt["result"]["event_id"] = operation
            keys = field.split(".")
            target = receipt if len(keys) == 1 else receipt[keys[0]]
            if value == "REMOVE":
                del target[keys[-1]]
            else:
                target[keys[-1]] = value
            connection.execute(
                """INSERT INTO claim_events (
                    event_id, claim_id, occurred_at, event_kind, evidence_version,
                    from_status, to_status, details_json
                ) VALUES (?, ?, ?, 'CLAIM_CANCELLED', 1, 'NEED_INFO', 'CANCELLED', ?)""",
                (operation, claim_id, LATER.isoformat(), json.dumps(receipt)),
            )
        before = snapshot(connection)
        with write_transaction(connection):
            with pytest.raises(MalformedOperationReceipt):
                cancel_attempt(connection, claim_id, operation_id=operation)
        assert snapshot(connection) == before


def test_new_cancellation_ids_distinguish_old_guards_from_current_terminal_state(
    stored,
):
    path, claim_id = stored
    with connect_database(path) as connection:
        with write_transaction(connection):
            first = cancel_attempt(connection, claim_id)
            stale = cancel_attempt(connection, claim_id)
            terminal = cancel_attempt(
                connection,
                claim_id,
                expected_status="CANCELLED",
                expected_state_version=2,
            )
        assert first.outcome == "CANCELLED"
        assert stale.outcome == "STALE"
        assert terminal.outcome == "NOT_EDITABLE"
        assert get_claim(connection, claim_id)["state_version"] == 2
        assert len(list_claim_revisions(connection, claim_id)) == 1
        assert_integrity(connection)


@pytest.mark.parametrize("commit", [True, False])
def test_same_cancellation_operation_across_connections_replays_only_committed_receipt(
    stored, commit
):
    path, claim_id = stored
    operation = str(uuid4())
    with connect_database(path) as first, connect_database(path) as second:
        second.execute("PRAGMA busy_timeout=0")
        first.execute("BEGIN IMMEDIATE")
        original = cancel_attempt(first, claim_id, operation_id=operation)
        with pytest.raises(sqlite3.OperationalError, match="locked"):
            with write_transaction(second):
                pytest.fail("Second caller cannot enter while the first writes.")
        first.execute("COMMIT" if commit else "ROLLBACK")
        with write_transaction(second):
            result = cancel_attempt(second, claim_id, operation_id=operation)
        assert result == replace(original, replayed=commit)
        assert get_claim(second, claim_id)["state_version"] == 2
        assert (
            len(
                [
                    e
                    for e in list_claim_events(second, claim_id)
                    if e["event_kind"] == "CLAIM_CANCELLED"
                ]
            )
            == 1
        )
        assert_integrity(second)


def test_cancellation_stores_trusted_timestamp_in_utc(stored):
    path, claim_id = stored
    local = LATER.astimezone(timezone(timedelta(hours=5, minutes=30)))
    with connect_database(path) as connection:
        with write_transaction(connection):
            result = cancel_attempt(connection, claim_id, occurred_at=local)
        event = next(
            e
            for e in list_claim_events(connection, claim_id)
            if e["event_id"] == result.event_id
        )
        assert event["occurred_at"] == LATER.isoformat(timespec="microseconds")


@pytest.mark.parametrize("first_line", [1, 2])
def test_serialized_corrections_to_distinct_lines_both_keep_ownership(
    stored, first_line
):
    path, claim_id = stored
    with connect_database(path) as first, connect_database(path) as second:
        with write_transaction(first):
            other = insert_initial_claim(
                first,
                raw_input={**payload(), "invoice_number": "other"},
                submitted_at=SUBMITTED,
            )
            first.execute(
                "UPDATE claims SET status='NEED_INFO' WHERE claim_id=?", (other,)
            )
        second.execute("PRAGMA busy_timeout=0")
        first.execute("BEGIN IMMEDIATE")
        left = attempt(
            first,
            claim_id,
            raw_input={
                **payload(),
                "invoice_number": "shared",
                "invoice_line_number": first_line,
            },
        )
        with pytest.raises(sqlite3.OperationalError, match="locked"):
            with write_transaction(second):
                pytest.fail("Different keys still require serialized SQLite writers.")
        first.execute("COMMIT")
        with write_transaction(second):
            right = attempt(
                second,
                other,
                raw_input={
                    **payload(),
                    "invoice_number": "shared",
                    "invoice_line_number": 3 - first_line,
                },
            )
        assert left.outcome == right.outcome == "ACCEPTED"
        for identifier, line in ((claim_id, first_line), (other, 3 - first_line)):
            current = get_claim(second, identifier)
            assert current["normalized_invoice_number"] == "shared"
            assert current["invoice_line_number"] == str(line)
            assert current["current_evidence_version"] == current["state_version"] == 2
            # Both distinct keys remain owned after their commits.
            with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
                with write_transaction(second):
                    insert_initial_claim(
                        second,
                        raw_input={
                            **payload(),
                            "invoice_number": "shared",
                            "invoice_line_number": line,
                        },
                        submitted_at=SUBMITTED,
                    )
        assert_integrity(second)


@pytest.mark.parametrize("commit_first", [True, False])
def test_competing_same_claim_corrections_to_different_keys_respect_versions(
    stored, commit_first
):
    path, claim_id = stored
    with connect_database(path) as first, connect_database(path) as second:
        second.execute("PRAGMA busy_timeout=0")
        first.execute("BEGIN IMMEDIATE")
        attempt(
            first, claim_id, raw_input={**payload(), "invoice_number": "first-target"}
        )
        with pytest.raises(sqlite3.OperationalError, match="locked"):
            with write_transaction(second):
                pytest.fail("Competing correction must await transaction resolution.")
        first.execute("COMMIT" if commit_first else "ROLLBACK")
        with write_transaction(second):
            result = attempt(
                second,
                claim_id,
                raw_input={**payload(), "invoice_number": "second-target"},
            )
        assert result.outcome == ("STALE" if commit_first else "ACCEPTED")
        current = get_claim(second, claim_id)
        assert current["normalized_invoice_number"] == (
            "first-target" if commit_first else "second-target"
        )
        assert current["current_evidence_version"] == current["state_version"] == 2
        assert_integrity(second)


@pytest.mark.parametrize(
    "outcome", ["ACCEPTED", "CANCELLED", "INVALID", "STALE", "DUPLICATE_CONFLICT"]
)
def test_changes_preserve_nonempty_evaluation_history_and_existing_consumption(
    stored, outcome
):
    path, claim_id = stored
    operation = str(uuid4())
    # Deliberately exceeds WELLNESS's fictional annual cap: this primitive must
    # not perform allowance admission or disguise it as structural invalidity.
    proposed = {
        **payload(),
        "invoice_number": "new",
        "invoice_item_amount": "40000",
        "requested_reimbursement": "35000",
    }
    with connect_database(path) as connection:
        with write_transaction(connection):
            consumed = insert_initial_claim(
                connection,
                raw_input={
                    **payload(),
                    "invoice_number": "already-consumed",
                    "invoice_item_amount": "30000",
                    "requested_reimbursement": "30000",
                },
                submitted_at=SUBMITTED,
            )
            connection.execute(
                "UPDATE claims SET status='PROCESSABLE' WHERE claim_id=?", (consumed,)
            )
            if outcome == "DUPLICATE_CONFLICT":
                insert_initial_claim(
                    connection, raw_input=proposed, submitted_at=SUBMITTED
                )
            original_revision = get_claim(connection, claim_id)["current_revision_id"]
            for completed in (False, True):
                evaluation = str(uuid4())
                connection.execute(
                    """INSERT INTO evaluations (
                        evaluation_id, claim_id, evidence_version, evaluation_run_id,
                        question_kind, question_revision, model_version, expected_status,
                        expected_state_version, started_at, completed_at, input_snapshot_json,
                        response_json, write_disposition
                    ) VALUES (?, ?, 1, ?, 'J1', 'fixture-v1', 'fixture-model', 'NEED_INFO',
                              1, ?, ?, ?, ?, ?)""",
                    (
                        evaluation,
                        claim_id,
                        str(uuid4()),
                        SUBMITTED.isoformat(),
                        SUBMITTED.isoformat() if completed else None,
                        encode_raw_evidence(payload()),
                        '{"fixture":true}' if completed else None,
                        "APPLIED" if completed else None,
                    ),
                )
                connection.execute(
                    """INSERT INTO claim_events (
                        event_id, claim_id, occurred_at, event_kind, evidence_version,
                        revision_id, evaluation_id, details_json
                    ) VALUES (?, ?, ?, 'EVALUATION_FIXTURE', 1, ?, ?, '{}')""",
                    (
                        str(uuid4()),
                        claim_id,
                        SUBMITTED.isoformat(),
                        original_revision,
                        evaluation,
                    ),
                )
        before = snapshot(connection)
        original_claim = dict(get_claim(connection, claim_id))
        consumed_claim = dict(get_claim(connection, consumed))
        overrides = {"operation_id": operation, "raw_input": proposed}
        if outcome == "INVALID":
            overrides["raw_input"] = {**proposed, "requested_reimbursement": "0"}
        elif outcome == "STALE":
            overrides["expected_state_version"] = 2
        with write_transaction(connection):
            if outcome == "CANCELLED":
                result = cancel_attempt(connection, claim_id, operation_id=operation)
                first_write = snapshot(connection)
                replay = cancel_attempt(connection, claim_id, operation_id=operation)
            else:
                result = attempt(connection, claim_id, **overrides)
                first_write = snapshot(connection)
                replay = attempt(connection, claim_id, **overrides)
            assert result.outcome == outcome
            assert replay == replace(result, replayed=True)
            assert snapshot(connection) == first_write
        after = snapshot(connection)
        assert after["evaluations"] == before["evaluations"]
        for table in ("claim_revisions", "claim_events"):
            assert all(row in after[table] for row in before[table])
        assert dict(get_claim(connection, consumed)) == consumed_claim
        amounts = connection.execute(
            """SELECT r.requested_reimbursement FROM claims c JOIN claim_revisions r
                ON r.claim_id=c.claim_id AND r.evidence_version=c.current_evidence_version
                WHERE c.status='PROCESSABLE'"""
        ).fetchall()
        assert sum(Decimal(row[0]) for row in amounts) == Decimal("30000")
        current = get_claim(connection, claim_id)
        assert current["status"] == (
            "CANCELLED" if outcome == "CANCELLED" else "NEED_INFO"
        )
        assert current["current_evidence_version"] == (
            2 if outcome == "ACCEPTED" else 1
        )
        assert current["state_version"] == (
            2 if outcome in ("ACCEPTED", "CANCELLED") else 1
        )
        for counter in (
            "uncertain_item_corrections",
            "reliable_item_corrections",
            "category_corrections",
            "semantic_responses",
        ):
            assert current[counter] == original_claim[counter]
        assert_integrity(connection)


@pytest.mark.parametrize("action", ["correction", "cancellation"])
def test_outer_commit_failure_rolls_back_changes_and_operation_receipt(stored, action):
    path, claim_id = stored
    operation = str(uuid4())
    with connect_database(path) as connection, connect_database(path) as observer:
        before = snapshot(connection)
        with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
            with write_transaction(connection):
                if action == "correction":
                    result = attempt(
                        connection,
                        claim_id,
                        operation_id=operation,
                        raw_input={**payload(), "invoice_number": "new"},
                    )
                else:
                    result = cancel_attempt(
                        connection, claim_id, operation_id=operation
                    )
                assert result.outcome in ("ACCEPTED", "CANCELLED")
                assert snapshot(observer) == before
                # Simulate unrelated caller work failing its deferred FK at
                # outer COMMIT, after the operation's savepoint was released.
                connection.execute(
                    "UPDATE claims SET outstanding_question_event_id=? WHERE claim_id=?",
                    (str(uuid4()), claim_id),
                )
        assert not connection.in_transaction
        assert snapshot(connection) == snapshot(observer) == before
        with write_transaction(connection):
            if action == "correction":
                retry = attempt(
                    connection,
                    claim_id,
                    operation_id=operation,
                    raw_input={**payload(), "invoice_number": "new"},
                )
            else:
                retry = cancel_attempt(connection, claim_id, operation_id=operation)
        assert not retry.replayed
        assert_integrity(observer)


@pytest.mark.parametrize(
    "action,table,verb",
    [
        ("correction", "claim_revisions", "INSERT"),
        ("correction", "claims", "UPDATE"),
        ("correction", "claim_events", "INSERT"),
        ("duplicate", "claim_revisions", "INSERT"),
        ("duplicate", "claim_events", "INSERT"),
        ("cancellation", "claims", "UPDATE"),
        ("cancellation", "claim_events", "INSERT"),
    ],
)
def test_after_write_failure_removes_partial_statement_and_keeps_prior_work(
    stored, action, table, verb
):
    path, claim_id = stored
    operation = str(uuid4())
    with connect_database(path) as connection:
        with write_transaction(connection):
            other = insert_initial_claim(
                connection,
                raw_input={**payload(), "invoice_number": "taken"},
                submitted_at=SUBMITTED,
            )
            before = snapshot(connection)
            condition = (
                "WHEN NEW.disposition='DUPLICATE_CONFLICT'"
                if action == "duplicate" and table == "claim_revisions"
                else ""
            )
            # AFTER ... RAISE(FAIL) leaves the statement's applied changes in the
            # transaction until the operation's savepoint explicitly undoes them.
            connection.execute(f"""CREATE TEMP TRIGGER fail_after_write AFTER {verb} ON {table}
                {condition} BEGIN SELECT RAISE(FAIL, 'forced after-write failure'); END""")
            with pytest.raises(
                sqlite3.IntegrityError, match="forced after-write failure"
            ):
                if action == "cancellation":
                    cancel_attempt(connection, claim_id, operation_id=operation)
                else:
                    attempt(
                        connection,
                        claim_id,
                        operation_id=operation,
                        raw_input={
                            **payload(),
                            "invoice_number": "taken"
                            if action == "duplicate"
                            else "new",
                        },
                    )
            assert connection.in_transaction
            assert snapshot(connection) == before
            connection.execute("DROP TRIGGER fail_after_write")
            if action == "cancellation":
                retry = cancel_attempt(connection, claim_id, operation_id=operation)
            else:
                retry = attempt(
                    connection,
                    claim_id,
                    operation_id=operation,
                    raw_input={
                        **payload(),
                        "invoice_number": "taken" if action == "duplicate" else "new",
                    },
                )
            assert not retry.replayed
            assert (
                retry.outcome
                == {
                    "correction": "ACCEPTED",
                    "duplicate": "DUPLICATE_CONFLICT",
                    "cancellation": "CANCELLED",
                }[action]
            )
        assert get_claim(connection, other) is not None
        assert_integrity(connection)


@pytest.mark.parametrize("action", ["correction", "cancellation"])
def test_sqlite_aborted_transaction_preserves_original_error_and_allows_fresh_retry(
    stored, action
):
    path, claim_id = stored
    operation = str(uuid4())
    with connect_database(path) as connection:
        before = snapshot(connection)
        with pytest.raises(sqlite3.IntegrityError, match="forced transaction abort"):
            with write_transaction(connection):
                insert_initial_claim(
                    connection,
                    raw_input={**payload(), "invoice_number": "outer-work"},
                    submitted_at=SUBMITTED,
                )
                connection.execute("""CREATE TEMP TRIGGER abort_change AFTER UPDATE ON claims
                    BEGIN SELECT RAISE(ROLLBACK, 'forced transaction abort'); END""")
                if action == "correction":
                    attempt(
                        connection,
                        claim_id,
                        operation_id=operation,
                        raw_input=payload(),
                    )
                else:
                    cancel_attempt(connection, claim_id, operation_id=operation)
        # SQLite ended the entire transaction. Cleanup must not mask that error
        # with 'no such savepoint'; prior caller work necessarily rolled back too.
        assert not connection.in_transaction
        assert snapshot(connection) == before
        with write_transaction(connection):
            if action == "correction":
                result = attempt(
                    connection, claim_id, operation_id=operation, raw_input=payload()
                )
            else:
                result = cancel_attempt(connection, claim_id, operation_id=operation)
        assert not result.replayed
        assert_integrity(connection)
