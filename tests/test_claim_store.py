"""Initial storage, identity constraints and caller-owned transaction boundaries."""

import copy
import json
import sqlite3
import sys
from datetime import datetime, timezone
from decimal import Decimal, localcontext
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import ValidationError

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

SUBMITTED_AT = datetime(2026, 10, 31, 12, tzinfo=timezone.utc)


@pytest.fixture
def database_path(tmp_path: Path) -> Path:
    path = tmp_path / "claims.sqlite3"
    initialize_database(path)
    return path


@pytest.fixture
def raw_input() -> dict[str, object]:
    return {
        "employee_id": " Emp-001 ",
        "merchant_name": "  Straße  SHOP ",
        "invoice_number": " Inv / 001 ",
        "invoice_date": "2026-10-31",
        "invoice_item_name": " Running Shoes ",
        "invoice_item_amount": "1200.0000",
        "reimbursement_category": "WELLNESS",
        "requested_reimbursement": "1000.00",
        "employee_justification": " For daily running ",
    }


def test_initial_insert_is_linked_and_does_not_commit(
    database_path: Path, raw_input: dict[str, object]
) -> None:
    original = copy.deepcopy(raw_input)
    with (
        connect_database(database_path) as connection,
        connect_database(database_path) as observer,
    ):
        connection.row_factory = sqlite3.Row
        with write_transaction(connection):
            claim_id = insert_initial_claim(
                connection, raw_input=raw_input, submitted_at=SUBMITTED_AT
            )
            assert connection.in_transaction
            assert observer.execute("SELECT count(*) FROM claims").fetchone() == (0,)
        claim = connection.execute("SELECT * FROM claims").fetchone()
        revision = connection.execute("SELECT * FROM claim_revisions").fetchone()
        event = connection.execute("SELECT * FROM claim_events").fetchone()
        assert (
            claim["claim_id"] == revision["claim_id"] == event["claim_id"] == claim_id
        )
        identifiers = {claim_id, revision["revision_id"], event["event_id"]}
        assert len(identifiers) == 3
        assert all(UUID(identifier).version == 4 for identifier in identifiers)
        assert (claim["current_evidence_version"], claim["state_version"]) == (1, 1)
        assert (
            claim["status"],
            claim["reason_code"],
            claim["outstanding_question_event_id"],
        ) == (None, None, None)
        assert tuple(
            claim[column]
            for column in (
                "uncertain_item_corrections",
                "reliable_item_corrections",
                "category_corrections",
                "semantic_responses",
            )
        ) == (0, 0, 0, 0)
        assert (
            claim["normalized_employee_id"],
            claim["normalized_merchant_name"],
            claim["normalized_invoice_number"],
            claim["invoice_line_number"],
        ) == ("emp-001", "strasse shop", "inv / 001", "1")
        assert (
            claim["submitted_at"]
            == revision["submitted_at"]
            == event["occurred_at"]
            == "2026-10-31T12:00:00.000000+00:00"
        )
        assert (
            claim["original_submission_date"]
            == revision["invoice_date"]
            == "2026-10-31"
        )
        assert revision["evidence_version"] == event["evidence_version"] == 1
        assert revision["revision_id"] == event["revision_id"]
        assert (revision["action_kind"], revision["disposition"]) == (
            "INITIAL",
            "ACCEPTED",
        )
        assert (
            revision["invoice_item_amount"],
            revision["requested_reimbursement"],
        ) == ("1200.0000", "1000.00")
        assert revision["raw_evidence_json"] == encode_raw_evidence(original)
        assert event["event_kind"] == "INITIAL_CLAIM_STORED"
        assert (event["from_status"], event["to_status"], event["evaluation_id"]) == (
            None,
            None,
            None,
        )
        assert json.loads(event["details_json"]) == {"state_version": 1}
        assert connection.execute("SELECT count(*) FROM evaluations").fetchone()[0] == 0
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    assert raw_input == original


@pytest.mark.parametrize("explicit_line", [False, True])
def test_raw_field_presence_is_separate_from_default_projection(
    database_path: Path, raw_input: dict[str, object], explicit_line: bool
) -> None:
    if explicit_line:
        raw_input["invoice_line_number"] = 1
    with connect_database(database_path) as connection:
        with write_transaction(connection):
            insert_initial_claim(
                connection, raw_input=raw_input, submitted_at=SUBMITTED_AT
            )
        assert connection.execute(
            "SELECT invoice_line_number FROM claims"
        ).fetchone() == ("1",)
        snapshot = connection.execute(
            "SELECT raw_evidence_json FROM claim_revisions"
        ).fetchone()[0]
        entries = dict(json.loads(snapshot)["value"]["entries"])
        assert ("invoice_line_number" in entries) == explicit_line
        assert snapshot == encode_raw_evidence(raw_input)


@pytest.mark.parametrize(
    "instant,business_day",
    [
        ("2026-10-31T18:29:59.999999+00:00", "2026-10-31"),
        ("2026-11-01T00:00:00+05:30", "2026-11-01"),
    ],
)
def test_business_date_comes_from_the_single_supplied_instant(
    database_path: Path, raw_input: dict[str, object], instant: str, business_day: str
) -> None:
    submitted_at = datetime.fromisoformat(instant)
    with connect_database(database_path) as connection:
        with write_transaction(connection):
            insert_initial_claim(
                connection, raw_input=raw_input, submitted_at=submitted_at
            )
        assert connection.execute(
            "SELECT original_submission_date, submitted_at FROM claims"
        ).fetchone() == (
            business_day,
            submitted_at.astimezone(timezone.utc).isoformat(timespec="microseconds"),
        )


@pytest.mark.parametrize(
    "invoice_date,error",
    [
        ("2026-07-31", None),
        ("2026-10-31", None),
        ("2026-07-30", "too old"),
        ("2026-11-01", "after the original submission date"),
    ],
)
def test_invoice_window_is_checked_before_writing(
    database_path: Path,
    raw_input: dict[str, object],
    invoice_date: str,
    error: str | None,
) -> None:
    raw_input["invoice_date"] = invoice_date
    with connect_database(database_path) as connection:
        with write_transaction(connection):
            if error is None:
                insert_initial_claim(
                    connection, raw_input=raw_input, submitted_at=SUBMITTED_AT
                )
            else:
                with pytest.raises(ValueError, match=error):
                    insert_initial_claim(
                        connection, raw_input=raw_input, submitted_at=SUBMITTED_AT
                    )
                assert connection.in_transaction
        assert connection.execute("SELECT count(*) FROM claims").fetchone() == (
            1 if error is None else 0,
        )
        assert connection.execute("SELECT count(*) FROM claim_events").fetchone() == (
            1 if error is None else 0,
        )


def test_large_exact_projections_do_not_depend_on_decimal_context(
    database_path: Path, raw_input: dict[str, object]
) -> None:
    digit_limit = sys.get_int_max_str_digits()
    raw_input["invoice_line_number"] = 10**5000 + 1
    raw_input["invoice_item_amount"] = Decimal("9" * 100 + ".1200")
    raw_input["requested_reimbursement"] = Decimal("9" * 100 + ".12")
    with connect_database(database_path) as connection:
        with localcontext() as context:
            context.prec = 2
            with write_transaction(connection):
                insert_initial_claim(
                    connection, raw_input=raw_input, submitted_at=SUBMITTED_AT
                )
        assert connection.execute(
            "SELECT invoice_line_number FROM claims"
        ).fetchone() == ("1" + "0" * 4999 + "1",)
        assert connection.execute(
            "SELECT invoice_item_amount, requested_reimbursement FROM claim_revisions"
        ).fetchone() == ("9" * 100 + ".1200", "9" * 100 + ".12")
    assert sys.get_int_max_str_digits() == digit_limit


@pytest.mark.parametrize("status", [None, "NEED_INFO", "HUMAN_REVIEW", "PROCESSABLE"])
def test_duplicate_ownership_rejects_normalized_equivalents_without_changing_history(
    database_path: Path, raw_input: dict[str, object], status: str | None
) -> None:
    duplicate = {
        **raw_input,
        "employee_id": "emp-001",
        "merchant_name": "STRASSE\tSHOP",
        "invoice_number": "\tINV /\n001 ",
    }
    with connect_database(database_path) as connection:
        with write_transaction(connection):
            insert_initial_claim(
                connection, raw_input=raw_input, submitted_at=SUBMITTED_AT
            )
            connection.execute("UPDATE claims SET status=?", (status,))
            before = {
                table: connection.execute(f"SELECT * FROM {table}").fetchall()
                for table in ("claims", "claim_revisions", "claim_events")
            }
            with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
                insert_initial_claim(
                    connection, raw_input=duplicate, submitted_at=SUBMITTED_AT
                )
            assert connection.in_transaction
            for table, rows in before.items():
                assert connection.execute(f"SELECT * FROM {table}").fetchall() == rows


@pytest.mark.parametrize(
    "field,value",
    [
        ("employee_id", "other employee"),
        ("merchant_name", "different merchant"),
        ("invoice_number", "INV-002"),
        ("invoice_line_number", 2),
    ],
)
def test_distinct_identity_components_allow_independent_claims(
    database_path: Path, raw_input: dict[str, object], field: str, value: object
) -> None:
    with connect_database(database_path) as connection:
        with write_transaction(connection):
            first = insert_initial_claim(
                connection, raw_input=raw_input, submitted_at=SUBMITTED_AT
            )
            second = insert_initial_claim(
                connection,
                raw_input={**raw_input, field: value},
                submitted_at=SUBMITTED_AT,
            )
        assert first != second
        assert connection.execute("SELECT count(*) FROM claims").fetchone() == (2,)


@pytest.mark.parametrize("status", ["POLICY_RESTRICTION", "CANCELLED"])
def test_released_identity_can_be_acquired_by_a_new_claim(
    database_path: Path, raw_input: dict[str, object], status: str
) -> None:
    with connect_database(database_path) as connection:
        with write_transaction(connection):
            first = insert_initial_claim(
                connection, raw_input=raw_input, submitted_at=SUBMITTED_AT
            )
            # Direct SQL establishes a schema fixture, not a lifecycle service.
            connection.execute(
                "UPDATE claims SET status=? WHERE claim_id=?", (status, first)
            )
            second = insert_initial_claim(
                connection, raw_input=raw_input, submitted_at=SUBMITTED_AT
            )
        assert first != second
        assert connection.execute("SELECT count(*) FROM claims").fetchone() == (2,)


@pytest.mark.parametrize(
    "changes",
    [
        {"employee_id": ""},
        {"invoice_item_amount": 1.2},
        {"requested_reimbursement": "1200.01"},
        {"invoice_line_number": True},
        {"unexpected_field": "rejected"},
    ],
)
def test_invalid_inputs_leave_no_records(
    database_path: Path, raw_input: dict[str, object], changes: dict[str, object]
) -> None:
    value = {**raw_input, **changes}
    original = copy.deepcopy(value)
    with connect_database(database_path) as connection:
        with write_transaction(connection):
            with pytest.raises(ValidationError):
                insert_initial_claim(
                    connection, raw_input=value, submitted_at=SUBMITTED_AT
                )
            assert connection.in_transaction
        for table in ("claims", "claim_revisions", "claim_events"):
            assert connection.execute(f"SELECT count(*) FROM {table}").fetchone() == (
                0,
            )
    assert value == original


def test_naive_submission_instant_is_rejected(
    database_path: Path, raw_input: dict[str, object]
) -> None:
    with connect_database(database_path) as connection:
        with write_transaction(connection):
            with pytest.raises(ValueError, match="timezone-aware"):
                insert_initial_claim(
                    connection, raw_input=raw_input, submitted_at=datetime(2026, 10, 31)
                )
        assert connection.execute("SELECT count(*) FROM claims").fetchone() == (0,)


def test_insertion_requires_an_active_transaction(
    database_path: Path, raw_input: dict[str, object]
) -> None:
    with connect_database(database_path) as connection:
        with pytest.raises(ValueError, match="active caller-owned transaction"):
            insert_initial_claim(
                connection, raw_input=raw_input, submitted_at=SUBMITTED_AT
            )
        assert not connection.in_transaction
        assert connection.execute("SELECT count(*) FROM claims").fetchone() == (0,)


def test_final_event_failure_rolls_back_only_this_insertion_even_if_caught(
    database_path: Path, raw_input: dict[str, object]
) -> None:
    candidate = {**raw_input, "invoice_number": "candidate"}
    with connect_database(database_path) as connection:
        with write_transaction(connection):
            first = insert_initial_claim(
                connection, raw_input=raw_input, submitted_at=SUBMITTED_AT
            )
            before = {
                table: connection.execute(f"SELECT * FROM {table}").fetchall()
                for table in ("claims", "claim_revisions", "claim_events")
            }
            connection.execute("""CREATE TEMP TRIGGER fail_final_event BEFORE INSERT ON claim_events
                BEGIN SELECT RAISE(FAIL, 'forced audit failure'); END""")
            with pytest.raises(sqlite3.IntegrityError, match="forced audit failure"):
                insert_initial_claim(
                    connection, raw_input=candidate, submitted_at=SUBMITTED_AT
                )
            assert connection.in_transaction
            for table, rows in before.items():
                assert connection.execute(f"SELECT * FROM {table}").fetchall() == rows
        assert connection.execute("SELECT claim_id FROM claims").fetchall() == [
            (first,)
        ]
        connection.execute("DROP TRIGGER fail_final_event")
        with write_transaction(connection):
            insert_initial_claim(
                connection, raw_input=candidate, submitted_at=SUBMITTED_AT
            )
        assert connection.execute("SELECT count(*) FROM claims").fetchone() == (2,)


def test_outer_rollback_removes_successful_insertion(
    database_path: Path, raw_input: dict[str, object]
) -> None:
    with connect_database(database_path) as connection:
        with pytest.raises(RuntimeError, match="caller rollback"):
            with write_transaction(connection):
                insert_initial_claim(
                    connection, raw_input=raw_input, submitted_at=SUBMITTED_AT
                )
                raise RuntimeError("caller rollback")
        for table in ("claims", "claim_revisions", "claim_events"):
            assert connection.execute(f"SELECT count(*) FROM {table}").fetchone() == (
                0,
            )


def test_insertion_preserves_an_existing_caller_savepoint(
    database_path: Path, raw_input: dict[str, object]
) -> None:
    with connect_database(database_path) as connection:
        with write_transaction(connection):
            connection.execute("SAVEPOINT caller_scope")
            insert_initial_claim(
                connection, raw_input=raw_input, submitted_at=SUBMITTED_AT
            )
            connection.execute("ROLLBACK TO SAVEPOINT caller_scope")
            connection.execute("RELEASE SAVEPOINT caller_scope")
            assert connection.in_transaction
        assert connection.execute("SELECT count(*) FROM claims").fetchone() == (0,)


@pytest.mark.parametrize("commit_first", [True, False])
def test_two_connections_respect_writer_lock_and_committed_ownership(
    database_path: Path, raw_input: dict[str, object], commit_first: bool
) -> None:
    with (
        connect_database(database_path) as first,
        connect_database(database_path) as second,
    ):
        second.execute("PRAGMA busy_timeout=0")
        first.execute("BEGIN IMMEDIATE")
        first_id = insert_initial_claim(
            first, raw_input=raw_input, submitted_at=SUBMITTED_AT
        )
        with pytest.raises(sqlite3.OperationalError, match="locked"):
            with write_transaction(second):
                pytest.fail(
                    "Another writer must not enter while the first owns the lock."
                )
        if commit_first:
            first.execute("COMMIT")
            with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
                with write_transaction(second):
                    insert_initial_claim(
                        second, raw_input=raw_input, submitted_at=SUBMITTED_AT
                    )
            owner_id = first_id
        else:
            first.execute("ROLLBACK")
            with write_transaction(second):
                owner_id = insert_initial_claim(
                    second, raw_input=raw_input, submitted_at=SUBMITTED_AT
                )
            assert owner_id != first_id
        assert second.execute("SELECT claim_id FROM claims").fetchall() == [(owner_id,)]
        assert second.execute("SELECT count(*) FROM claim_revisions").fetchone() == (1,)
        assert second.execute("SELECT count(*) FROM claim_events").fetchone() == (1,)


@pytest.fixture
def history_records(
    database_path: Path, raw_input: dict[str, object]
) -> tuple[str, str, dict[tuple[str, int], str]]:
    """Create history directly; this fixture does not implement revision workflows."""
    snapshots: dict[tuple[str, int], str] = {}
    with connect_database(database_path) as connection:
        with write_transaction(connection):
            other_input = {**raw_input, "invoice_number": "other invoice"}
            other_id = insert_initial_claim(
                connection, raw_input=other_input, submitted_at=SUBMITTED_AT
            )
            claim_id = insert_initial_claim(
                connection, raw_input=raw_input, submitted_at=SUBMITTED_AT
            )
            for owner_id, original in ((other_id, other_input), (claim_id, raw_input)):
                for version in (2, 3):
                    changed = {
                        **original,
                        "invoice_date": f"2026-10-0{version}",
                        "reimbursement_category": "SMARTPHONE"
                        if version == 2
                        else "WELLNESS",
                        "invoice_item_name": "Phone"
                        if version == 2
                        else "Running shoes",
                        "invoice_item_amount": f"{version}300.0000",
                        "requested_reimbursement": f"{version}100.00",
                    }
                    snapshot = encode_raw_evidence(changed)
                    snapshots[owner_id, version] = snapshot
                    connection.execute(
                        """INSERT INTO claim_revisions (
                            revision_id, claim_id, evidence_version, submitted_at,
                            action_kind, disposition, raw_evidence_json, invoice_date,
                            reimbursement_category, invoice_item_amount,
                            requested_reimbursement, validation_details_json
                        ) VALUES (?, ?, ?, ?, 'CORRECTION', 'ACCEPTED', ?, ?, ?, ?, ?, '{}')""",
                        (
                            f"accepted-{version}-{owner_id}",
                            owner_id,
                            version,
                            f"2026-11-0{version - 1}T12:00:00.000000+00:00",
                            snapshot,
                            changed["invoice_date"],
                            changed["reimbursement_category"],
                            changed["invoice_item_amount"],
                            changed["requested_reimbursement"],
                        ),
                    )
                connection.execute(
                    """UPDATE claims SET status='NEED_INFO', current_evidence_version=2,
                        state_version=2 WHERE claim_id=?""",
                    (owner_id,),
                )
            for index, disposition in enumerate(
                ("INVALID", "DUPLICATE_CONFLICT", "ALLOWANCE_FAILURE", "STALE")
            ):
                connection.execute(
                    """INSERT INTO claim_revisions (
                        revision_id, claim_id, submitted_at, action_kind,
                        disposition, raw_evidence_json, validation_details_json
                    ) VALUES (?, ?, '2026-11-01T12:00:00.000000+00:00', 'CORRECTION',
                              ?, ?, '{"field":"invoice_item_amount"}')""",
                    (
                        f"failed-{index}",
                        claim_id,
                        disposition,
                        encode_raw_evidence({"invoice_item_amount": ["invalid"]}),
                    ),
                )
            for event_id, occurred_at, kind, version, revision_id in (
                (
                    "z-tie",
                    "2026-11-03T12:00:00.000000+00:00",
                    "FAILED_FIXTURE",
                    None,
                    "failed-0",
                ),
                (
                    "a-tie",
                    "2026-11-03T12:00:00.000000+00:00",
                    "STATE_FIXTURE",
                    None,
                    None,
                ),
                (
                    "z-earlier",
                    "2026-11-02T12:00:00.000000+00:00",
                    "EVIDENCE_FIXTURE",
                    2,
                    f"accepted-2-{claim_id}",
                ),
            ):
                connection.execute(
                    """INSERT INTO claim_events (
                        event_id, claim_id, occurred_at, event_kind, evidence_version,
                        revision_id, from_status, to_status, details_json
                    ) VALUES (?, ?, ?, ?, ?, ?, 'NEED_INFO', 'NEED_INFO', '{"source":"fixture"}')""",
                    (event_id, claim_id, occurred_at, kind, version, revision_id),
                )
    return claim_id, other_id, snapshots


def test_get_claim_returns_current_fields_and_aliased_initial_evidence(
    database_path: Path, raw_input: dict[str, object]
) -> None:
    with connect_database(database_path) as connection:
        with write_transaction(connection):
            claim_id = insert_initial_claim(
                connection, raw_input=raw_input, submitted_at=SUBMITTED_AT
            )
        row = get_claim(connection, claim_id)
        assert isinstance(row, sqlite3.Row)
        assert row["claim_id"] == claim_id
        assert (
            row["status"],
            row["current_evidence_version"],
            row["state_version"],
        ) == (None, 1, 1)
        assert row["normalized_merchant_name"] == "strasse shop"
        assert (
            row["current_revision_id"]
            == list_claim_revisions(connection, claim_id)[0]["revision_id"]
        )
        assert row["current_raw_evidence_json"] == encode_raw_evidence(raw_input)
        assert isinstance(row["current_raw_evidence_json"], str)
        assert (
            row["current_invoice_date"],
            row["current_reimbursement_category"],
            row["current_invoice_item_amount"],
            row["current_requested_reimbursement"],
        ) == ("2026-10-31", "WELLNESS", "1200.0000", "1000.00")
        claim_columns = [
            column[1] for column in connection.execute("PRAGMA table_info(claims)")
        ]
        assert all(column in row.keys() for column in claim_columns)
        assert len(row.keys()) == len(set(row.keys()))


def test_get_claim_uses_both_owner_and_current_pointer_instead_of_latest_version(
    database_path: Path, history_records: tuple[str, str, dict[tuple[str, int], str]]
) -> None:
    claim_id, other_id, snapshots = history_records
    with connect_database(database_path) as connection:
        for owner_id in (claim_id, other_id):
            row = get_claim(connection, owner_id)
            assert row is not None
            assert row["claim_id"] == owner_id
            assert row["current_evidence_version"] == 2
            assert row["current_revision_id"] == f"accepted-2-{owner_id}"
            assert row["current_raw_evidence_json"] == snapshots[owner_id, 2]
            assert (
                row["current_invoice_date"],
                row["current_reimbursement_category"],
                row["current_invoice_item_amount"],
                row["current_requested_reimbursement"],
            ) == ("2026-10-02", "SMARTPHONE", "2300.0000", "2100.00")


def test_revision_reads_include_all_dispositions_and_timestamp_id_order(
    database_path: Path, history_records: tuple[str, str, dict[tuple[str, int], str]]
) -> None:
    claim_id, _, _ = history_records
    with connect_database(database_path) as connection:
        rows = list_claim_revisions(connection, claim_id)
        assert len(rows) == 7
        assert all(
            isinstance(row, sqlite3.Row) and row["claim_id"] == claim_id for row in rows
        )
        assert [row["revision_id"] for row in rows[1:]] == [
            f"accepted-2-{claim_id}",
            "failed-0",
            "failed-1",
            "failed-2",
            "failed-3",
            f"accepted-3-{claim_id}",
        ]
        assert [row["disposition"] for row in rows] == [
            "ACCEPTED",
            "ACCEPTED",
            "INVALID",
            "DUPLICATE_CONFLICT",
            "ALLOWANCE_FAILURE",
            "STALE",
            "ACCEPTED",
        ]
        assert [row["evidence_version"] for row in rows] == [
            1,
            2,
            None,
            None,
            None,
            None,
            3,
        ]
        assert all(
            isinstance(row["raw_evidence_json"], str)
            and isinstance(row["validation_details_json"], str)
            for row in rows
        )
        assert rows[2]["validation_details_json"] == '{"field":"invoice_item_amount"}'
        assert rows[2]["raw_evidence_json"] == encode_raw_evidence(
            {"invoice_item_amount": ["invalid"]}
        )
        columns = [
            column[1]
            for column in connection.execute("PRAGMA table_info(claim_revisions)")
        ]
        assert rows[0].keys() == columns


def test_event_reads_return_complete_history_in_timestamp_id_order(
    database_path: Path, history_records: tuple[str, str, dict[tuple[str, int], str]]
) -> None:
    claim_id, _, _ = history_records
    with connect_database(database_path) as connection:
        rows = list_claim_events(connection, claim_id)
        assert len(rows) == 4
        assert all(
            isinstance(row, sqlite3.Row) and row["claim_id"] == claim_id for row in rows
        )
        assert rows[0]["event_kind"] == "INITIAL_CLAIM_STORED"
        assert [row["event_id"] for row in rows[1:]] == ["z-earlier", "a-tie", "z-tie"]
        assert rows[1]["evidence_version"] == 2
        assert rows[1]["revision_id"] == f"accepted-2-{claim_id}"
        assert (rows[3]["evidence_version"], rows[3]["revision_id"]) == (
            None,
            "failed-0",
        )
        assert rows[3]["details_json"] == '{"source":"fixture"}'
        columns = [
            column[1]
            for column in connection.execute("PRAGMA table_info(claim_events)")
        ]
        assert rows[0].keys() == columns


@pytest.mark.parametrize("missing_id", ["missing", "' OR 1=1 --"])
def test_missing_claim_and_history_return_empty_results(
    database_path: Path, raw_input: dict[str, object], missing_id: str
) -> None:
    with connect_database(database_path) as connection:
        with write_transaction(connection):
            insert_initial_claim(
                connection, raw_input=raw_input, submitted_at=SUBMITTED_AT
            )
        assert get_claim(connection, missing_id) is None
        assert list_claim_revisions(connection, missing_id) == []
        assert list_claim_events(connection, missing_id) == []


@pytest.mark.parametrize("custom_factory", [False, True])
def test_reads_use_local_rows_without_writes_or_connection_setting_changes(
    database_path: Path, raw_input: dict[str, object], custom_factory: bool
) -> None:
    def caller_factory(
        cursor: sqlite3.Cursor, row: tuple[object, ...]
    ) -> dict[str, object]:
        return {"caller_row": row}

    with connect_database(database_path) as connection:
        with write_transaction(connection):
            claim_id = insert_initial_claim(
                connection, raw_input=raw_input, submitted_at=SUBMITTED_AT
            )
        factory = caller_factory if custom_factory else None
        connection.row_factory = factory
        connection.execute("PRAGMA query_only=ON")
        changes_before = connection.total_changes
        statements: list[str] = []
        connection.set_trace_callback(statements.append)
        assert isinstance(get_claim(connection, claim_id), sqlite3.Row)
        assert isinstance(list_claim_revisions(connection, claim_id)[0], sqlite3.Row)
        assert isinstance(list_claim_events(connection, claim_id)[0], sqlite3.Row)
        assert len(statements) == 3
        assert all(
            statement.lstrip().upper().startswith("SELECT") for statement in statements
        )
        assert connection.total_changes == changes_before
        assert not connection.in_transaction
        assert connection.row_factory is factory
        result = connection.execute("SELECT 1").fetchone()
        assert result == ({"caller_row": (1,)} if custom_factory else (1,))


def test_reads_preserve_an_active_callers_transaction(
    database_path: Path, raw_input: dict[str, object]
) -> None:
    with connect_database(database_path) as connection:
        with pytest.raises(RuntimeError, match="caller rollback after reads"):
            with write_transaction(connection):
                claim_id = insert_initial_claim(
                    connection, raw_input=raw_input, submitted_at=SUBMITTED_AT
                )
                assert get_claim(connection, claim_id) is not None
                assert len(list_claim_revisions(connection, claim_id)) == 1
                assert len(list_claim_events(connection, claim_id)) == 1
                assert connection.in_transaction
                raise RuntimeError("caller rollback after reads")
        assert get_claim(connection, claim_id) is None
        assert list_claim_revisions(connection, claim_id) == []
        assert list_claim_events(connection, claim_id) == []
