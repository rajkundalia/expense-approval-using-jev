"""Evaluation capture/replay, opaque reads and caller-owned transactions."""

import sqlite3
from datetime import date, datetime, timedelta, timezone, tzinfo
from uuid import uuid4

import pytest

import expense_approval.evaluation_store as store
from expense_approval.allowance_policy import get_allowance_period
from expense_approval.allowance_store import read_consumed_allowance
from expense_approval.claim_changes import cancel_claim, correct_claim
from expense_approval.claim_input import ReimbursementCategory
from expense_approval.claim_store import get_claim, insert_initial_claim
from expense_approval.database import (
    connect_database,
    initialize_database,
    write_transaction,
)

INSTANT = datetime(2026, 10, 31, 12, tzinfo=timezone.utc)
TABLES = ("claims", "claim_revisions", "claim_events", "evaluations")


@pytest.fixture
def database_path(tmp_path):
    path = tmp_path / "claims.sqlite3"
    initialize_database(path)
    return path


@pytest.fixture
def connection(database_path):
    with connect_database(database_path) as connection:
        yield connection
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert connection.execute("PRAGMA integrity_check").fetchall() == [("ok",)]


@pytest.fixture
def history(connection):
    with write_transaction(connection):
        claims = [
            insert_initial_claim(
                connection,
                raw_input={
                    "employee_id": "emp-1",
                    "merchant_name": "merchant",
                    "invoice_number": invoice,
                    "invoice_date": "2026-10-01",
                    "invoice_item_name": "Running shoes",
                    "invoice_item_amount": "100.00",
                    "requested_reimbursement": "10.01",
                    "reimbursement_category": "WELLNESS",
                    "employee_justification": "For running",
                },
                submitted_at=INSTANT,
            )
            for invoice in ("one", "two")
        ]
        connection.execute(
            """INSERT INTO claim_revisions SELECT
                'revision-v2', claim_id, 2, submitted_at, 'ORDINARY_CORRECTION',
                disposition, raw_evidence_json, invoice_date, reimbursement_category,
                invoice_item_amount, requested_reimbursement, validation_details_json
            FROM claim_revisions WHERE claim_id = ?""",
            (claims[0],),
        )
        connection.execute(
            """UPDATE claims SET current_evidence_version=2, state_version=2,
                status='PROCESSABLE' WHERE claim_id=?""",
            (claims[0],),
        )
        # Deliberately inserted out of order; SQL permits contradictory lifecycle
        # fields and noncanonical timestamps. Readers must not reinterpret them.
        for evaluation, claim, version, start, end, response, error, disposition in (
            ("b", claims[0], 2, "2026-10-31T12:00:01+00:00", None, None, None, None),
            (
                "z",
                claims[0],
                1,
                "2026-10-31T12:00:00+00:00",
                "end",
                "{}",
                None,
                "APPLIED",
            ),
            (
                "a",
                claims[0],
                1,
                "2026-10-31T12:00:01+00:00",
                None,
                '{"partial":true}',
                None,
                None,
            ),
            (
                "c",
                claims[0],
                2,
                "2026-10-31T12:00:02+00:00",
                "before-start",
                "{}",
                '{"legacy":true}',
                "STALE",
            ),
            ("other", claims[1], 1, "start", None, None, None, None),
        ):
            connection.execute(
                """INSERT INTO evaluations (
                    evaluation_id, claim_id, evidence_version, evaluation_run_id,
                    question_kind, question_revision, model_version, expected_status,
                    expected_state_version, started_at, completed_at,
                    input_snapshot_json, response_json, error_json, write_disposition
                ) VALUES (?, ?, ?, 'run', 'J1', 'q1', 'fixture-model', NULL,
                          1, ?, ?, ' { "opaque" : 1 } ', ?, ?, ?)""",
                (evaluation, claim, version, start, end, response, error, disposition),
            )
    return claims


@pytest.mark.parametrize("value", [None, object(), "connection"])
@pytest.mark.parametrize(
    "operation", [store._validate_connection, store._require_write_transaction]
)
def test_connection_type(value, operation):
    with pytest.raises(TypeError, match="sqlite3.Connection"):
        operation(value)


def test_transaction_validation_observes_activity_only(connection):
    store._validate_connection(connection)
    with pytest.raises(ValueError, match="active caller-owned"):
        store._require_write_transaction(connection)
    for begin in ("BEGIN", "BEGIN IMMEDIATE"):
        connection.execute(begin)
        store._require_write_transaction(connection)
        assert connection.in_transaction
        connection.execute("ROLLBACK")
    assert not connection.in_transaction


@pytest.mark.parametrize(
    "value,error",
    [(None, TypeError), (1, TypeError), ("", ValueError), (" \t\n", ValueError)],
)
def test_required_text_rejects_invalid(value, error):
    with pytest.raises(error):
        store._validate_required_text(value, "Metadata")


def test_opaque_text_is_preserved():
    for name in (
        "Evaluation ID",
        "Claim ID",
        "Run ID",
        "Question revision",
        "Model version",
    ):
        text = "  Opaque / NON-UUID Ω  "
        assert store._validate_required_text(text, name) is text


@pytest.mark.parametrize(
    "value,error",
    [
        (True, TypeError),
        (False, TypeError),
        (1.0, TypeError),
        ("1", TypeError),
        (None, TypeError),
        (0, ValueError),
        (-1, ValueError),
    ],
)
def test_positive_versions(value, error):
    with pytest.raises(error):
        store._validate_positive_version(value, "Evidence version")


def test_valid_versions_and_builtin_requirement():
    assert store._validate_positive_version(1, "Version") == 1

    class Version(int):
        pass

    with pytest.raises(TypeError):
        store._validate_positive_version(Version(1), "Version")


@pytest.mark.parametrize(
    "helper,values",
    [
        (store._validate_question_kind, ("J1", "J2", "J3", "J4")),
        (
            store._validate_expected_status,
            (
                None,
                "NEED_INFO",
                "HUMAN_REVIEW",
                "POLICY_RESTRICTION",
                "CANCELLED",
                "PROCESSABLE",
            ),
        ),
        (
            store._validate_failure_code,
            (
                "TIMEOUT",
                "CONNECTION_ERROR",
                "PROVIDER_ERROR",
                "INVALID_RESPONSE",
                "REMOTE_OUTCOME_UNKNOWN",
            ),
        ),
    ],
)
def test_allowlists(helper, values):
    for value in values:
        assert helper(value) == value
    for value in ("", "unknown", " J1", "timeout", "secret-provider-message"):
        with pytest.raises(ValueError) as caught:
            helper(value)
        assert "secret-provider-message" not in str(caught.value)
    for value in (True, 1, [], {}):
        with pytest.raises(TypeError):
            helper(value)


@pytest.mark.parametrize(
    "helper", [store._validate_question_kind, store._validate_failure_code]
)
def test_nonnullable_allowlists(helper):
    with pytest.raises(TypeError):
        helper(None)


def test_timestamp_canonicalization():
    offset = timezone(timedelta(hours=5, minutes=30))
    assert (
        store._normalize_timestamp(INSTANT, "Start")
        == "2026-10-31T12:00:00.000000+00:00"
    )
    assert store._normalize_timestamp(
        INSTANT.astimezone(offset), "Start"
    ) == store._normalize_timestamp(INSTANT, "Start")
    assert (
        store._normalize_timestamp(INSTANT.replace(microsecond=1), "End")
        == "2026-10-31T12:00:00.000001+00:00"
    )


class _NaiveZone(tzinfo):
    def utcoffset(self, dt):
        return None


@pytest.mark.parametrize(
    "value,error",
    [
        (None, TypeError),
        ("2026-10-31", TypeError),
        (date(2026, 10, 31), TypeError),
        (INSTANT.replace(tzinfo=None), ValueError),
        (INSTANT.replace(tzinfo=_NaiveZone()), ValueError),
        (datetime.min.replace(tzinfo=timezone(timedelta(hours=1))), ValueError),
        (datetime.max.replace(tzinfo=timezone(-timedelta(hours=1))), ValueError),
    ],
)
def test_timestamp_invalid(value, error):
    with pytest.raises(error):
        store._normalize_timestamp(value, "Timestamp")


@pytest.mark.parametrize(
    "text",
    [
        "{}",
        ' \n{ "b": [1, {"a":true}], "a": null }\t',
        '{"unicode":"Ω😀"}',
        '{"n":1e9999,"tiny":1e-9999}',
        '{"n":' + "9" * 5000 + "}",
        '{"a":{"x":1},"b":{"x":2}}',
        '{"a":1,"A":2}',
    ],
)
def test_json_preserves_accepted_text(connection, text):
    assert store._validate_json_object(text, "Snapshot") is text
    store._validate_sqlite_json(connection, text, "Snapshot")
    assert not connection.in_transaction


@pytest.mark.parametrize(
    "text",
    [
        "",
        "[]",
        "null",
        "true",
        "1",
        '"object"',
        "{",
        '{"a":1,}',
        '{/*comment*/"a":1}',
        '{"n":NaN}',
        '{"n":Infinity}',
        '{"n":-Infinity}',
        '{"a":1,"a":2}',
        '{"a":{"x":1,"x":2}}',
        '{"a":[{"x":1,"x":2}]}',
        '{"a":1,"\\u0061":2}',
        '{"s":"\ud800"}',
        '{"s":"\udfff"}',
        '{"secret-token":}',
        '{"s":"\x00"}',
        "\ufeff{}",
    ],
)
def test_invalid_json_has_safe_errors(text):
    with pytest.raises(ValueError) as caught:
        store._validate_json_object(text, "Snapshot")
    assert str(caught.value) == "Snapshot must be a UTF-8-encodable strict JSON object."
    assert caught.value.__suppress_context__


@pytest.mark.parametrize("value", [None, {}, b"{}", 1])
def test_json_requires_text(value):
    with pytest.raises(TypeError):
        store._validate_json_object(value, "Snapshot")


def test_json_parser_depth_and_sqlite_compatibility(connection):
    too_deep = '{"a":' + "[" * 2000 + "0" + "]" * 2000 + "}"
    # Python's recursion limit can vary under the test runner. Either pure
    # validation rejects depth or SQLite's parser must reject it before storage.
    try:
        store._validate_json_object(too_deep, "Snapshot")
    except ValueError:
        pass
    with pytest.raises(ValueError, match="SQLite JSON"):
        store._validate_sqlite_json(connection, too_deep, "Snapshot")
    # SQLite accepts a NUL-terminated prefix; json_valid alone is insufficient.
    with pytest.raises(ValueError, match="strict JSON object"):
        store._validate_json_object("{}\x00", "Snapshot")


@pytest.mark.parametrize(
    "reader,key",
    [
        (store.get_evaluation, "evaluation_id"),
        (store.list_claim_evaluations, "claim_id"),
    ],
)
def test_read_arguments_validated_before_sql(connection, reader, key):
    statements = []
    connection.set_trace_callback(statements.append)
    try:
        for value, error in (
            (None, TypeError),
            (1, TypeError),
            ("", ValueError),
            (" \t", ValueError),
        ):
            with pytest.raises(error):
                reader(connection, **{key: value})
        with pytest.raises(TypeError, match="sqlite3.Connection"):
            reader(None, **{key: None})
        assert statements == []
    finally:
        connection.set_trace_callback(None)


@pytest.mark.parametrize("value", [None, 0, 1, "true", []])
def test_filter_requires_actual_bool(connection, value):
    with pytest.raises(TypeError, match="boolean"):
        store.list_claim_evaluations(connection, "missing", unfinished_only=value)


def test_missing_reads(connection):
    assert store.get_evaluation(connection, "missing") is None
    assert store.list_claim_evaluations(connection, "missing") == []
    assert (
        store.list_claim_evaluations(connection, "missing", unfinished_only=True) == []
    )


def test_history_order_filter_and_opaque_rows(connection, history):
    rows = store.list_claim_evaluations(connection, history[0])
    assert all(isinstance(row, sqlite3.Row) for row in rows)
    assert [row["evaluation_id"] for row in rows] == ["z", "a", "b", "c"]
    assert [row["evidence_version"] for row in rows] == [1, 1, 2, 2]
    assert [
        row["evaluation_id"]
        for row in store.list_claim_evaluations(
            connection, history[0], unfinished_only=True
        )
    ] == ["a", "b"]
    for row in rows:
        assert dict(store.get_evaluation(connection, row["evaluation_id"])) == dict(row)
        assert row["input_snapshot_json"] == ' { "opaque" : 1 } '
    assert rows[1]["response_json"] == '{"partial":true}'
    assert rows[3]["completed_at"] == "before-start"
    assert rows[3]["response_json"] == "{}"
    assert rows[3]["error_json"] == '{"legacy":true}'
    assert store.get_evaluation(connection, "z")["write_disposition"] == "APPLIED"
    assert [
        row["evaluation_id"]
        for row in store.list_claim_evaluations(connection, history[1])
    ] == ["other"]
    assert store.get_evaluation(connection, " z ") is None
    assert store.list_claim_evaluations(connection, "' OR 1=1 --") == []


def _snapshot(connection):
    return {
        table: connection.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall()
        for table in TABLES
    }


def _consumed(connection):
    return read_consumed_allowance(
        connection,
        employee_id="emp-1",
        category=ReimbursementCategory.WELLNESS,
        period=get_allowance_period(ReimbursementCategory.WELLNESS, date(2026, 10, 1)),
    )


@pytest.mark.parametrize("transaction", [False, True])
def test_reads_preserve_settings_transactions_and_all_data(
    connection, history, transaction
):
    before = _snapshot(connection)
    allowance = _consumed(connection)
    changes = connection.total_changes
    settings = (
        connection.isolation_level,
        connection.autocommit,
        connection.execute("PRAGMA foreign_keys").fetchone(),
        connection.execute("PRAGMA recursive_triggers").fetchone(),
    )

    def factory(cursor, row):
        return tuple(row)

    connection.row_factory = factory
    connection.text_factory = bytes
    caller_cursor = connection.cursor()
    try:
        if transaction:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("SAVEPOINT caller_scope")
        assert isinstance(store.get_evaluation(connection, "z"), sqlite3.Row)
        assert store.get_evaluation(connection, "z")["evaluation_id"] == b"z"
        assert len(store.list_claim_evaluations(connection, history[0])) == 4
        assert (
            len(
                store.list_claim_evaluations(
                    connection, history[0], unfinished_only=True
                )
            )
            == 2
        )
        assert connection.in_transaction is transaction
        assert connection.row_factory is factory
        assert connection.text_factory is bytes
        assert caller_cursor.execute("SELECT 1").fetchone() == (1,)
        if transaction:
            connection.execute("ROLLBACK TO caller_scope")
            connection.execute("RELEASE caller_scope")
            connection.execute("ROLLBACK")
    finally:
        caller_cursor.close()
        connection.row_factory = None
        connection.text_factory = str
    assert _snapshot(connection) == before
    assert _consumed(connection) == allowance
    assert connection.total_changes == changes
    assert (
        connection.isolation_level,
        connection.autocommit,
        connection.execute("PRAGMA foreign_keys").fetchone(),
        connection.execute("PRAGMA recursive_triggers").fetchone(),
    ) == settings


def test_reads_observe_caller_writes_without_committing(
    connection, history, database_path
):
    with connect_database(database_path) as observer:
        with write_transaction(connection):
            connection.execute("SAVEPOINT caller_scope")
            connection.execute(
                "UPDATE evaluations SET model_version='provisional' WHERE evaluation_id='b'"
            )
            assert (
                store.get_evaluation(connection, "b")["model_version"] == "provisional"
            )
            assert (
                store.get_evaluation(observer, "b")["model_version"] == "fixture-model"
            )
            connection.execute("ROLLBACK TO caller_scope")
            connection.execute("RELEASE caller_scope")
            assert (
                store.get_evaluation(connection, "b")["model_version"]
                == "fixture-model"
            )


def test_owned_cursors_close_on_success_and_failure(database_path):
    class Cursor(sqlite3.Cursor):
        closed = False

        def close(self):
            self.closed = True
            super().close()

    class Connection(sqlite3.Connection):
        def cursor(self):
            cursor = super().cursor(factory=Cursor)
            cursors.append(cursor)
            return cursor

    cursors = []
    connection = sqlite3.connect(
        database_path, factory=Connection, isolation_level=None
    )
    try:
        assert store.get_evaluation(connection, "missing") is None
        assert store.list_claim_evaluations(connection, "missing") == []
        store._validate_sqlite_json(connection, "{}", "Snapshot")
        with pytest.raises(ValueError):
            store._validate_sqlite_json(connection, "invalid", "Snapshot")
        connection.set_authorizer(lambda *args: sqlite3.SQLITE_DENY)
        for operation in (
            lambda: store.get_evaluation(connection, "missing"),
            lambda: store.list_claim_evaluations(connection, "missing"),
            lambda: store._validate_sqlite_json(connection, "{}", "Snapshot"),
        ):
            with pytest.raises(sqlite3.DatabaseError):
                operation()
        assert len(cursors) == 7
        assert all(cursor.closed for cursor in cursors)
    finally:
        connection.close()


def test_closed_connection_errors_propagate(connection):
    closed = sqlite3.connect(":memory:")
    closed.close()
    for operation in (
        lambda: store._require_write_transaction(closed),
        lambda: store.get_evaluation(closed, "id"),
        lambda: store.list_claim_evaluations(closed, "id"),
        lambda: store._validate_sqlite_json(closed, "{}", "Snapshot"),
    ):
        with pytest.raises(sqlite3.ProgrammingError):
            operation()


@pytest.fixture
def creation(history):
    return {
        "evaluation_id": "new-evaluation",
        "claim_id": history[1],
        "evidence_version": 1,
        "evaluation_run_id": " opaque run ",
        "question_kind": "J1",
        "question_revision": " question-v1 ",
        "model_version": " model-v1 ",
        "expected_status": None,
        "expected_state_version": 1,
        "started_at": INSTANT,
        "input_snapshot_json": ' { "item" : "shoes" } ',
    }


def test_create_unfinished_and_preserve_other_tables(
    connection, creation, database_path
):
    before = _snapshot(connection)
    allowance = _consumed(connection)
    with connect_database(database_path) as observer:
        with write_transaction(connection):
            row = store.create_evaluation(connection, **creation)
            assert isinstance(row, sqlite3.Row)
            for key, value in creation.items():
                assert row[key] == (
                    "2026-10-31T12:00:00.000000+00:00" if key == "started_at" else value
                )
            assert all(
                row[key] is None
                for key in (
                    "completed_at",
                    "response_json",
                    "error_json",
                    "write_disposition",
                )
            )
            assert store.get_evaluation(observer, creation["evaluation_id"]) is None
            after = _snapshot(connection)
            assert all(
                after[table] == before[table]
                for table in TABLES
                if table != "evaluations"
            )
            assert _consumed(connection) == allowance
        assert dict(store.get_evaluation(observer, creation["evaluation_id"])) == dict(
            row
        )


@pytest.mark.parametrize(
    "field,value,error",
    [
        ("evaluation_id", None, TypeError),
        ("claim_id", "  ", ValueError),
        ("evidence_version", True, TypeError),
        ("evidence_version", 0, ValueError),
        ("evaluation_run_id", "", ValueError),
        ("question_kind", "J5", ValueError),
        ("question_revision", 1, TypeError),
        ("model_version", "", ValueError),
        ("expected_status", "NEW", ValueError),
        ("expected_state_version", False, TypeError),
        ("started_at", INSTANT.replace(tzinfo=None), ValueError),
        ("input_snapshot_json", '{"a":1,"a":2}', ValueError),
    ],
)
def test_create_argument_validation_precedes_sql(
    connection, creation, field, value, error
):
    with write_transaction(connection):
        statements = []
        connection.set_trace_callback(statements.append)
        try:
            with pytest.raises(error):
                store.create_evaluation(connection, **{**creation, field: value})
            assert statements == []
        finally:
            connection.set_trace_callback(None)


def test_create_connection_transaction_and_signature_precedence(connection, creation):
    with pytest.raises(TypeError, match="sqlite3.Connection"):
        store.create_evaluation(None, **{**creation, "evaluation_id": None})
    with pytest.raises(ValueError, match="active caller-owned"):
        store.create_evaluation(connection, **{**creation, "evaluation_id": None})
    with write_transaction(connection):
        with pytest.raises(TypeError, match="Evaluation ID"):
            store.create_evaluation(
                connection, **{**creation, "evaluation_id": None, "evidence_version": 0}
            )


def test_sqlite_json_check_precedes_identity_lookup(connection, creation):
    with write_transaction(connection):
        store.create_evaluation(connection, **creation)
        statements = []
        connection.set_trace_callback(statements.append)
        try:
            with pytest.raises(ValueError):
                store.create_evaluation(
                    connection,
                    **{
                        **creation,
                        "input_snapshot_json": '{"x":'
                        + "[" * 2000
                        + "0"
                        + "]" * 2000
                        + "}",
                    },
                )
            assert not any("FROM evaluations" in sql for sql in statements)
        finally:
            connection.set_trace_callback(None)


@pytest.mark.parametrize(
    "field,value",
    [
        ("evidence_version", 2),
        ("expected_status", "NEED_INFO"),
        ("expected_state_version", 2),
    ],
)
def test_new_creation_guard_mismatch(connection, creation, field, value):
    before = _snapshot(connection)
    with write_transaction(connection):
        with pytest.raises(store.EvaluationStateConflict):
            store.create_evaluation(connection, **{**creation, field: value})
    assert _snapshot(connection) == before


def test_missing_claim_and_cross_claim_evidence(connection, creation):
    with write_transaction(connection):
        with pytest.raises(LookupError):
            store.create_evaluation(connection, **{**creation, "claim_id": "missing"})
        # Version 2 exists only for the other claim; it must not satisfy this one.
        with pytest.raises(store.EvaluationStateConflict):
            store.create_evaluation(connection, **{**creation, "evidence_version": 2})


def test_missing_current_accepted_revision_is_malformed(connection, creation):
    with write_transaction(connection):
        connection.execute(
            "UPDATE claims SET status='NEED_INFO', current_evidence_version=99 WHERE claim_id=?",
            (creation["claim_id"],),
        )
        with pytest.raises(store.MalformedEvaluationRecord, match="anchor"):
            store.create_evaluation(connection, **creation)
        connection.execute(
            "UPDATE claims SET status=NULL, current_evidence_version=1 WHERE claim_id=?",
            (creation["claim_id"],),
        )


@pytest.mark.parametrize(
    "status",
    [
        None,
        "NEED_INFO",
        "HUMAN_REVIEW",
        "POLICY_RESTRICTION",
        "CANCELLED",
        "PROCESSABLE",
    ],
)
@pytest.mark.parametrize("kind", ["J1", "J2", "J3", "J4"])
def test_role_and_terminal_anchor_storage(connection, creation, status, kind):
    with write_transaction(connection):
        connection.execute(
            "UPDATE claims SET status=? WHERE claim_id=?",
            (status, creation["claim_id"]),
        )
        request = {**creation, "expected_status": status, "question_kind": kind}
        if status in ("POLICY_RESTRICTION", "CANCELLED", "PROCESSABLE") and kind in (
            "J1",
            "J2",
        ):
            with pytest.raises(store.EvaluationStateConflict, match="terminal"):
                store.create_evaluation(connection, **request)
        else:
            assert (
                store.create_evaluation(connection, **request)["expected_status"]
                == status
            )


@pytest.mark.parametrize("disposition", [None, "APPLIED", "STALE", "DIAGNOSTIC"])
@pytest.mark.parametrize("failed", [False, True])
def test_creation_replay_after_completed_fixture(
    connection, creation, disposition, failed
):
    with write_transaction(connection):
        store.create_evaluation(connection, **creation)
        connection.execute(
            """UPDATE evaluations SET completed_at=?, response_json=?, error_json=?, write_disposition=?
               WHERE evaluation_id=?""",
            (
                "2026-10-31T12:00:01.000000+00:00",
                None if failed else '{"opaque":true}',
                '{"code":"TIMEOUT"}' if failed else None,
                disposition,
                creation["evaluation_id"],
            ),
        )
        connection.execute(
            "UPDATE claims SET status='CANCELLED', state_version=2 WHERE claim_id=?",
            (creation["claim_id"],),
        )
        before = _snapshot(connection)
        changes = connection.total_changes
        row = store.create_evaluation(connection, **creation)
        assert row["write_disposition"] == disposition
        assert row["completed_at"] == "2026-10-31T12:00:01.000000+00:00"
        assert _snapshot(connection) == before
        assert connection.total_changes == changes


@pytest.mark.parametrize("action", ["correction", "cancellation", "state"])
def test_creation_replay_after_claim_changes(connection, creation, action):
    with write_transaction(connection):
        original = store.create_evaluation(connection, **creation)
        connection.execute(
            "UPDATE claims SET status='NEED_INFO', state_version=2 WHERE claim_id=?",
            (creation["claim_id"],),
        )
        common = dict(
            claim_id=creation["claim_id"],
            operation_id=str(uuid4()),
            expected_status="NEED_INFO",
            expected_evidence_version=1,
            expected_state_version=2,
            occurred_at=INSTANT,
        )
        if action == "correction":
            result = correct_claim(
                connection,
                **common,
                action_kind="ORDINARY_CORRECTION",
                raw_input={
                    "employee_id": "emp-1",
                    "merchant_name": "merchant",
                    "invoice_number": "two",
                    "invoice_date": "2026-10-01",
                    "invoice_item_name": "New running shoes",
                    "invoice_item_amount": "100.00",
                    "requested_reimbursement": "10.01",
                    "reimbursement_category": "WELLNESS",
                    "employee_justification": "For running",
                },
            )
            assert result.outcome == "ACCEPTED"
        elif action == "cancellation":
            assert cancel_claim(connection, **common).outcome == "CANCELLED"
        before = _snapshot(connection)
        changes = connection.total_changes
        assert dict(store.create_evaluation(connection, **creation)) == dict(original)
        assert _snapshot(connection) == before
        assert connection.total_changes == changes
        with pytest.raises(store.EvaluationStateConflict):
            store.create_evaluation(
                connection, **{**creation, "evaluation_id": "new-attempt"}
            )


@pytest.mark.parametrize(
    "field,value",
    [
        ("claim_id", "other-owner"),
        ("evidence_version", 2),
        ("evaluation_run_id", "other-run"),
        ("question_kind", "J2"),
        ("question_revision", "q2"),
        ("model_version", "model2"),
        ("expected_status", "NEED_INFO"),
        ("expected_state_version", 2),
        ("started_at", INSTANT + timedelta(microseconds=1)),
        ("input_snapshot_json", '{"item":"shoes"}'),
    ],
)
def test_creation_identity_conflicts_before_current_guards(
    connection, creation, field, value
):
    with write_transaction(connection):
        store.create_evaluation(connection, **creation)
        connection.execute(
            "UPDATE claims SET status='CANCELLED', state_version=2 WHERE claim_id=?",
            (creation["claim_id"],),
        )
        before = _snapshot(connection)
        with pytest.raises(store.EvaluationConflict):
            store.create_evaluation(connection, **{**creation, field: value})
        assert _snapshot(connection) == before


def test_timestamp_instant_replay_and_run_is_not_unique(connection, creation):
    with write_transaction(connection):
        original = store.create_evaluation(connection, **creation)
        offset = timezone(timedelta(hours=5, minutes=30))
        assert dict(
            store.create_evaluation(
                connection, **{**creation, "started_at": INSTANT.astimezone(offset)}
            )
        ) == dict(original)
        assert (
            store.create_evaluation(
                connection, **{**creation, "evaluation_id": "second-id"}
            )["evaluation_run_id"]
            == original["evaluation_run_id"]
        )


def test_historical_aware_start_is_compared_by_normalized_instant(connection, creation):
    with write_transaction(connection):
        store.create_evaluation(connection, **creation)
        stored_start = "2026-10-31T17:30:00+05:30"
        connection.execute(
            "UPDATE evaluations SET started_at=? WHERE evaluation_id=?",
            (stored_start, creation["evaluation_id"]),
        )
        changes = connection.total_changes
        assert (
            store.create_evaluation(connection, **creation)["started_at"]
            == stored_start
        )
        assert connection.total_changes == changes


@pytest.mark.parametrize(
    "assignments",
    [
        "model_version=' '",
        "started_at='not-a-timestamp'",
        "started_at='2026-10-31T12:00:00'",
        "input_snapshot_json='[]'",
        'input_snapshot_json=\'{"x":1,"x":2}\'',
        "response_json='{}'",
        'error_json=\'{"code":"TIMEOUT"}\'',
        "write_disposition='STALE'",
        "completed_at='2026-10-31T12:00:01+00:00'",
        "completed_at='2026-10-31T11:00:00+00:00', response_json='{}'",
        "completed_at='bad', response_json='{}'",
        "completed_at='2026-10-31T12:00:01+00:00', response_json='{}', error_json='{}'",
        "completed_at='2026-10-31T12:00:01+00:00', response_json='[]'",
        "completed_at='2026-10-31T12:00:01+00:00', error_json='{\"code\":\"UNKNOWN\"}'",
        'completed_at=\'2026-10-31T12:00:01+00:00\', error_json=\'{"code":"TIMEOUT","secret":"token"}\'',
    ],
)
def test_malformed_record_precedes_metadata_conflict_but_not_owner_conflict(
    connection, creation, assignments
):
    with write_transaction(connection):
        store.create_evaluation(connection, **creation)
        connection.execute(
            f"UPDATE evaluations SET {assignments} WHERE evaluation_id=?",
            (creation["evaluation_id"],),
        )
        before = _snapshot(connection)
        with pytest.raises(store.EvaluationConflict, match="another claim"):
            store.create_evaluation(connection, **{**creation, "claim_id": "missing"})
        with pytest.raises(store.MalformedEvaluationRecord) as caught:
            store.create_evaluation(
                connection, **{**creation, "evaluation_run_id": "changed"}
            )
        assert "token" not in str(caught.value)
        assert _snapshot(connection) == before
        assert store.get_evaluation(connection, creation["evaluation_id"]) is not None


@pytest.mark.parametrize("failure", ["FAIL", "IGNORE"])
def test_creation_failure_savepoint_and_transaction_abort(
    connection, creation, failure
):
    with write_transaction(connection):
        timing = "BEFORE" if failure == "IGNORE" else "AFTER"
        connection.execute(f"""CREATE TEMP TRIGGER creation_failure {timing} INSERT ON evaluations
            BEGIN SELECT RAISE({failure}{", 'forced evaluation failure'" if failure != "IGNORE" else ""}); END""")
    with write_transaction(connection):
        connection.execute(
            "UPDATE evaluations SET model_version='caller-work' WHERE evaluation_id='b'"
        )
        with pytest.raises(
            RuntimeError if failure == "IGNORE" else sqlite3.IntegrityError
        ):
            store.create_evaluation(connection, **creation)
        assert store.get_evaluation(connection, creation["evaluation_id"]) is None
        assert connection.in_transaction
        assert store.get_evaluation(connection, "b")["model_version"] == "caller-work"


def test_creation_sqlite_abort_preserves_original_failure(connection, creation):
    before = _snapshot(connection)
    with pytest.raises(sqlite3.IntegrityError, match="forced transaction abort"):
        with write_transaction(connection):
            connection.execute(
                "UPDATE evaluations SET model_version='caller-work' WHERE evaluation_id='b'"
            )
            connection.execute("""CREATE TEMP TRIGGER creation_abort AFTER INSERT ON evaluations
                BEGIN SELECT RAISE(ROLLBACK, 'forced transaction abort'); END""")
            store.create_evaluation(connection, **creation)
    assert not connection.in_transaction
    assert _snapshot(connection) == before


@pytest.mark.parametrize("failure", ["readback", "rewritten-row"])
def test_creation_failure_after_insert_is_atomic(
    connection, creation, monkeypatch, failure
):
    original_get = store.get_evaluation
    calls = 0

    def failing_get(connection, evaluation_id):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise sqlite3.OperationalError("forced readback failure")
        return original_get(connection, evaluation_id)

    with write_transaction(connection):
        connection.execute(
            "UPDATE evaluations SET model_version='caller-work' WHERE evaluation_id='b'"
        )
        before = _snapshot(connection)
        if failure == "readback":
            monkeypatch.setattr(store, "get_evaluation", failing_get)
        else:
            connection.execute("""CREATE TEMP TRIGGER rewrite_creation AFTER INSERT ON evaluations
                BEGIN UPDATE evaluations SET model_version='rewritten' WHERE evaluation_id=NEW.evaluation_id; END""")
        with pytest.raises(
            sqlite3.OperationalError if failure == "readback" else RuntimeError
        ):
            store.create_evaluation(connection, **creation)
        assert connection.in_transaction
        assert _snapshot(connection) == before


def test_creation_preserves_connection_settings_and_caller_cursor(connection, creation):
    def factory(cursor, row):
        return tuple(row)

    connection.row_factory = factory
    caller_cursor = connection.cursor()
    settings = (
        connection.isolation_level,
        connection.autocommit,
        connection.text_factory,
        connection.execute("PRAGMA foreign_keys").fetchone(),
    )
    try:
        with write_transaction(connection):
            row = store.create_evaluation(connection, **creation)
            assert isinstance(row, sqlite3.Row)
            assert connection.row_factory is factory
            assert connection.in_transaction
            assert caller_cursor.execute("SELECT 1").fetchone() == (1,)
            assert (
                connection.isolation_level,
                connection.autocommit,
                connection.text_factory,
                connection.execute("PRAGMA foreign_keys").fetchone(),
            ) == settings
    finally:
        caller_cursor.close()
        connection.row_factory = None


def test_creation_respects_caller_savepoint_and_outer_rollback(connection, creation):
    before = _snapshot(connection)
    with write_transaction(connection):
        connection.execute("SAVEPOINT caller_scope")
        store.create_evaluation(connection, **creation)
        connection.execute("ROLLBACK TO caller_scope")
        connection.execute("RELEASE caller_scope")
        assert _snapshot(connection) == before
    with pytest.raises(RuntimeError, match="caller rollback"):
        with write_transaction(connection):
            store.create_evaluation(connection, **creation)
            raise RuntimeError("caller rollback")
    assert _snapshot(connection) == before


def test_creation_deferred_commit_failure(connection, creation):
    before = _snapshot(connection)
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
        with write_transaction(connection):
            store.create_evaluation(connection, **creation)
            connection.execute(
                "UPDATE claims SET status='NEED_INFO', outstanding_question_event_id='missing-event' WHERE claim_id=?",
                (creation["claim_id"],),
            )
    assert not connection.in_transaction
    assert _snapshot(connection) == before


def test_creation_operational_failure_preserves_caller_work(connection, creation):
    with write_transaction(connection):
        connection.execute(
            "UPDATE evaluations SET model_version='caller-work' WHERE evaluation_id='b'"
        )
        connection.set_authorizer(
            lambda action, table, *args: sqlite3.SQLITE_DENY
            if action == sqlite3.SQLITE_INSERT and table == "evaluations"
            else sqlite3.SQLITE_OK
        )
        try:
            with pytest.raises(sqlite3.DatabaseError):
                store.create_evaluation(connection, **creation)
        finally:
            connection.set_authorizer(None)
        assert connection.in_transaction
        assert store.get_evaluation(connection, "b")["model_version"] == "caller-work"
        assert store.get_evaluation(connection, creation["evaluation_id"]) is None


@pytest.mark.parametrize("commit_first", [True, False])
@pytest.mark.parametrize("conflicting", [False, True])
def test_competing_creation_writers_serialize(
    connection, creation, database_path, commit_first, conflicting
):
    with connect_database(database_path) as second:
        second.execute("PRAGMA busy_timeout=0")
        connection.execute("BEGIN IMMEDIATE")
        original = store.create_evaluation(connection, **creation)
        with pytest.raises(sqlite3.OperationalError, match="locked"):
            with write_transaction(second):
                pytest.fail("Second writer must wait for the first transaction.")
        connection.execute("COMMIT" if commit_first else "ROLLBACK")
        request = (
            {**creation, "model_version": "different"} if conflicting else creation
        )
        with write_transaction(second):
            if commit_first and conflicting:
                with pytest.raises(store.EvaluationConflict):
                    store.create_evaluation(second, **request)
            else:
                result = store.create_evaluation(second, **request)
                assert result["model_version"] == request["model_version"]
                if commit_first:
                    assert dict(result) == dict(original)
        assert (
            len(
                [
                    row
                    for row in store.list_claim_evaluations(
                        second, creation["claim_id"]
                    )
                    if row["evaluation_id"] == creation["evaluation_id"]
                ]
            )
            == 1
        )


@pytest.fixture
def completion(creation):
    return {
        "evaluation_id": creation["evaluation_id"],
        "claim_id": creation["claim_id"],
        "completed_at": INSTANT + timedelta(seconds=1),
        "response_json": ' { "opaque" : true } ',
        "failure_code": None,
    }


@pytest.fixture
def unfinished(connection, creation, completion):
    with write_transaction(connection):
        store.create_evaluation(connection, **creation)
    return completion


def test_response_completion_preserves_metadata_and_other_data(
    connection, unfinished, database_path
):
    before = _snapshot(connection)
    original = dict(store.get_evaluation(connection, unfinished["evaluation_id"]))
    allowance = _consumed(connection)
    with connect_database(database_path) as observer:
        with write_transaction(connection):
            row = store.complete_evaluation(connection, **unfinished)
            assert isinstance(row, sqlite3.Row)
            assert row["completed_at"] == "2026-10-31T12:00:01.000000+00:00"
            assert row["response_json"] == unfinished["response_json"]
            assert row["error_json"] is row["write_disposition"] is None
            assert all(
                row[key] == value
                for key, value in original.items()
                if key
                not in (
                    "completed_at",
                    "response_json",
                    "error_json",
                    "write_disposition",
                )
            )
            assert (
                store.get_evaluation(observer, unfinished["evaluation_id"])[
                    "completed_at"
                ]
                is None
            )
            after = _snapshot(connection)
            assert all(
                after[table] == before[table]
                for table in TABLES
                if table != "evaluations"
            )
            assert _consumed(connection) == allowance
        assert dict(
            store.get_evaluation(observer, unfinished["evaluation_id"])
        ) == dict(row)


@pytest.mark.parametrize(
    "code",
    [
        "TIMEOUT",
        "CONNECTION_ERROR",
        "PROVIDER_ERROR",
        "INVALID_RESPONSE",
        "REMOTE_OUTCOME_UNKNOWN",
    ],
)
def test_completion_sanitized_failure_codes(connection, unfinished, code):
    with write_transaction(connection):
        request = {**unfinished, "response_json": None, "failure_code": code}
        row = store.complete_evaluation(connection, **request)
        assert row["response_json"] is None
        assert row["error_json"] == '{"code":"' + code + '"}'
        changes = connection.total_changes
        assert dict(store.complete_evaluation(connection, **request)) == dict(row)
        assert connection.total_changes == changes


@pytest.mark.parametrize("kind", ["J1", "J2", "J3", "J4"])
@pytest.mark.parametrize("failed", [False, True])
def test_current_completion_disposition(connection, creation, completion, kind, failed):
    with write_transaction(connection):
        store.create_evaluation(connection, **{**creation, "question_kind": kind})
        if failed:
            completion = {
                **completion,
                "response_json": None,
                "failure_code": "TIMEOUT",
            }
        row = store.complete_evaluation(connection, **completion)
        assert row["write_disposition"] == (
            "DIAGNOSTIC" if kind in ("J3", "J4") else None
        )


@pytest.mark.parametrize(
    "field,value,error",
    [
        ("evaluation_id", None, TypeError),
        ("claim_id", " ", ValueError),
        ("completed_at", INSTANT.replace(tzinfo=None), ValueError),
        ("response_json", {}, TypeError),
        ("response_json", '{"x":1,"x":2}', ValueError),
        ("failure_code", "secret-provider-error", ValueError),
        ("failure_code", {}, TypeError),
    ],
)
def test_completion_argument_validation_before_sql(
    connection, unfinished, field, value, error
):
    with write_transaction(connection):
        statements = []
        connection.set_trace_callback(statements.append)
        try:
            with pytest.raises(error) as caught:
                store.complete_evaluation(connection, **{**unfinished, field: value})
            assert "secret-provider-error" not in str(caught.value)
            assert statements == []
        finally:
            connection.set_trace_callback(None)


def test_completion_requires_connection_transaction_and_one_channel(
    connection, unfinished
):
    with pytest.raises(TypeError, match="sqlite3.Connection"):
        store.complete_evaluation(None, **unfinished)
    with pytest.raises(ValueError, match="active caller-owned"):
        store.complete_evaluation(connection, **unfinished)
    with write_transaction(connection):
        for response, failure in ((None, None), ("{}", "TIMEOUT")):
            with pytest.raises(ValueError, match="Exactly one"):
                store.complete_evaluation(
                    connection,
                    **{
                        **unfinished,
                        "response_json": response,
                        "failure_code": failure,
                    },
                )
        with pytest.raises(TypeError, match="Evaluation ID"):
            store.complete_evaluation(
                connection,
                **{**unfinished, "evaluation_id": None, "completed_at": None},
            )
        with pytest.raises(TypeError):
            store.complete_evaluation(
                connection,
                **{
                    key: value
                    for key, value in unfinished.items()
                    if key != "failure_code"
                },
            )


def test_completion_json_compatibility_precedes_lookup(connection, unfinished):
    with write_transaction(connection):
        statements = []
        connection.set_trace_callback(statements.append)
        try:
            with pytest.raises(ValueError):
                store.complete_evaluation(
                    connection,
                    **{
                        **unfinished,
                        "evaluation_id": "missing",
                        "response_json": '{"x":' + "[" * 2000 + "0" + "]" * 2000 + "}",
                    },
                )
            assert not any("FROM evaluations" in sql for sql in statements)
        finally:
            connection.set_trace_callback(None)


def test_completion_lookup_owner_and_malformed_precedence(connection, unfinished):
    with write_transaction(connection):
        with pytest.raises(LookupError):
            store.complete_evaluation(
                connection, **{**unfinished, "evaluation_id": "missing"}
            )
        connection.execute(
            "UPDATE evaluations SET response_json='{}' WHERE evaluation_id=?",
            (unfinished["evaluation_id"],),
        )
        with pytest.raises(store.EvaluationConflict, match="another claim"):
            store.complete_evaluation(
                connection, **{**unfinished, "claim_id": "missing"}
            )
        with pytest.raises(store.MalformedEvaluationRecord):
            store.complete_evaluation(connection, **unfinished)


def test_completion_start_order_and_utc_replay(connection, unfinished):
    with write_transaction(connection):
        before = _snapshot(connection)
        with pytest.raises(ValueError, match="precede"):
            store.complete_evaluation(
                connection,
                **{**unfinished, "completed_at": INSTANT - timedelta(microseconds=1)},
            )
        assert _snapshot(connection) == before
        request = {**unfinished, "completed_at": INSTANT}
        row = store.complete_evaluation(connection, **request)
        changes = connection.total_changes
        assert dict(
            store.complete_evaluation(
                connection,
                **{
                    **request,
                    "completed_at": INSTANT.astimezone(
                        timezone(timedelta(hours=5, minutes=30))
                    ),
                },
            )
        ) == dict(row)
        assert connection.total_changes == changes
        with pytest.raises(store.EvaluationConflict):
            store.complete_evaluation(
                connection,
                **{**request, "completed_at": INSTANT - timedelta(microseconds=1)},
            )


@pytest.mark.parametrize(
    "action", ["correction", "cancellation", "state", "processing"]
)
@pytest.mark.parametrize("after_completion", [False, True])
def test_completion_staleness_and_replay_after_claim_changes(
    connection, creation, completion, action, after_completion
):
    with write_transaction(connection):
        connection.execute(
            "UPDATE claims SET status='NEED_INFO' WHERE claim_id=?",
            (creation["claim_id"],),
        )
        store.create_evaluation(
            connection,
            **{**creation, "question_kind": "J3", "expected_status": "NEED_INFO"},
        )
        original = (
            store.complete_evaluation(connection, **completion)
            if after_completion
            else None
        )
        common = dict(
            claim_id=creation["claim_id"],
            operation_id=str(uuid4()),
            expected_status="NEED_INFO",
            expected_evidence_version=1,
            expected_state_version=1,
            occurred_at=INSTANT,
        )
        if action == "correction":
            result = correct_claim(
                connection,
                **common,
                action_kind="ORDINARY_CORRECTION",
                raw_input={
                    "employee_id": "emp-1",
                    "merchant_name": "merchant",
                    "invoice_number": "two",
                    "invoice_date": "2026-10-01",
                    "invoice_item_name": "Revised running shoes",
                    "invoice_item_amount": "100.00",
                    "requested_reimbursement": "10.01",
                    "reimbursement_category": "WELLNESS",
                    "employee_justification": "For running",
                },
            )
            assert result.outcome == "ACCEPTED"
        elif action == "cancellation":
            assert cancel_claim(connection, **common).outcome == "CANCELLED"
        else:
            connection.execute(
                "UPDATE claims SET state_version=2, status=? WHERE claim_id=?",
                (
                    "PROCESSABLE" if action == "processing" else "NEED_INFO",
                    creation["claim_id"],
                ),
            )
        before = _snapshot(connection)
        allowance = _consumed(connection)
        changes = connection.total_changes
        row = store.complete_evaluation(connection, **completion)
        assert row["write_disposition"] == (
            "DIAGNOSTIC" if after_completion else "STALE"
        )
        if after_completion:
            assert dict(row) == dict(original)
            assert _snapshot(connection) == before
            assert connection.total_changes == changes
        else:
            after = _snapshot(connection)
            assert all(
                after[table] == before[table]
                for table in TABLES
                if table != "evaluations"
            )
        assert _consumed(connection) == allowance


@pytest.mark.parametrize(
    "change", ["response", "code", "channel", "failure-to-response", "timestamp"]
)
def test_conflicting_completion_replay(connection, unfinished, change):
    with write_transaction(connection):
        request = (
            {**unfinished, "response_json": None, "failure_code": "TIMEOUT"}
            if change in ("code", "failure-to-response")
            else unfinished
        )
        store.complete_evaluation(connection, **request)
        altered = {
            "response": {"response_json": '{"opaque":true}'},
            "code": {"failure_code": "PROVIDER_ERROR"},
            "channel": {"response_json": None, "failure_code": "TIMEOUT"},
            "failure-to-response": {"response_json": "{}", "failure_code": None},
            "timestamp": {
                "completed_at": request["completed_at"] + timedelta(microseconds=1)
            },
        }[change]
        before = _snapshot(connection)
        with pytest.raises(store.EvaluationConflict):
            store.complete_evaluation(connection, **{**request, **altered})
        assert _snapshot(connection) == before


@pytest.mark.parametrize("failed", [False, True])
def test_applied_historical_completion_replay(connection, unfinished, failed):
    with write_transaction(connection):
        connection.execute(
            """UPDATE evaluations SET completed_at='2026-10-31T17:30:01+05:30',
            response_json=?, error_json=?, write_disposition='APPLIED' WHERE evaluation_id=?""",
            (
                None if failed else unfinished["response_json"],
                ' { "code" : "TIMEOUT" } ' if failed else None,
                unfinished["evaluation_id"],
            ),
        )
        connection.execute(
            "UPDATE claims SET status='CANCELLED', state_version=2 WHERE claim_id=?",
            (unfinished["claim_id"],),
        )
        changes = connection.total_changes
        row = store.complete_evaluation(
            connection,
            **(
                {**unfinished, "response_json": None, "failure_code": "TIMEOUT"}
                if failed
                else unfinished
            ),
        )
        assert row["write_disposition"] == "APPLIED"
        assert row["completed_at"] == "2026-10-31T17:30:01+05:30"
        assert connection.total_changes == changes


@pytest.mark.parametrize(
    "assignments",
    [
        "completed_at='bad', response_json='{}'",
        "completed_at='2026-10-31T12:00:01+00:00'",
        "completed_at='2026-10-31T12:00:01+00:00', response_json='{}', error_json='{}'",
        "completed_at='2026-10-31T12:00:01+00:00', error_json='{\"code\":\"UNKNOWN\"}'",
    ],
)
def test_malformed_completed_record_before_replay_conflict(
    connection, unfinished, assignments
):
    with write_transaction(connection):
        connection.execute(
            f"UPDATE evaluations SET {assignments} WHERE evaluation_id=?",
            (unfinished["evaluation_id"],),
        )
        before = _snapshot(connection)
        with pytest.raises(store.MalformedEvaluationRecord):
            store.complete_evaluation(
                connection, **{**unfinished, "response_json": '{"different":true}'}
            )
        assert _snapshot(connection) == before


@pytest.mark.parametrize("failure", ["FAIL", "IGNORE", "readback", "ROLLBACK"])
def test_completion_failure_atomicity(connection, unfinished, monkeypatch, failure):
    before = _snapshot(connection)
    original_get = store.get_evaluation
    calls = 0

    def failing_get(connection, evaluation_id):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise sqlite3.OperationalError("forced completion readback failure")
        return original_get(connection, evaluation_id)

    if failure == "readback":
        monkeypatch.setattr(store, "get_evaluation", failing_get)
    else:
        timing = "BEFORE" if failure == "IGNORE" else "AFTER"
        connection.execute(f"""CREATE TEMP TRIGGER completion_failure {timing} UPDATE ON evaluations
            WHEN OLD.evaluation_id='new-evaluation'
            BEGIN SELECT RAISE({failure}{", 'forced completion failure'" if failure != "IGNORE" else ""}); END""")
    error = (
        RuntimeError
        if failure == "IGNORE"
        else sqlite3.OperationalError
        if failure == "readback"
        else sqlite3.IntegrityError
    )
    if failure == "ROLLBACK":
        with pytest.raises(error, match="forced completion failure"):
            with write_transaction(connection):
                connection.execute(
                    "UPDATE evaluations SET model_version='caller-work' WHERE evaluation_id='b'"
                )
                store.complete_evaluation(connection, **unfinished)
        assert not connection.in_transaction
        assert _snapshot(connection) == before
    else:
        with write_transaction(connection):
            connection.execute(
                "UPDATE evaluations SET model_version='caller-work' WHERE evaluation_id='b'"
            )
            caller_before = _snapshot(connection)
            with pytest.raises(error):
                store.complete_evaluation(connection, **unfinished)
            assert connection.in_transaction
            assert _snapshot(connection) == caller_before


def test_completion_caller_savepoint_and_deferred_commit(connection, unfinished):
    before = _snapshot(connection)
    with write_transaction(connection):
        connection.execute("SAVEPOINT caller_scope")
        store.complete_evaluation(connection, **unfinished)
        connection.execute("ROLLBACK TO caller_scope")
        connection.execute("RELEASE caller_scope")
        assert _snapshot(connection) == before
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
        with write_transaction(connection):
            store.complete_evaluation(connection, **unfinished)
            connection.execute(
                "UPDATE claims SET status='NEED_INFO', outstanding_question_event_id='missing' WHERE claim_id=?",
                (unfinished["claim_id"],),
            )
    assert not connection.in_transaction
    assert _snapshot(connection) == before


@pytest.mark.parametrize("commit_first", [False, True])
@pytest.mark.parametrize("conflicting", [False, True])
def test_competing_completion_writers(
    connection, unfinished, database_path, commit_first, conflicting
):
    with connect_database(database_path) as second:
        second.execute("PRAGMA busy_timeout=0")
        connection.execute("BEGIN IMMEDIATE")
        original = store.complete_evaluation(connection, **unfinished)
        with pytest.raises(sqlite3.OperationalError, match="locked"):
            with write_transaction(second):
                pytest.fail("Second completion writer must wait.")
        connection.execute("COMMIT" if commit_first else "ROLLBACK")
        request = (
            {**unfinished, "response_json": '{"other":true}'}
            if conflicting
            else unfinished
        )
        with write_transaction(second):
            if commit_first and conflicting:
                with pytest.raises(store.EvaluationConflict):
                    store.complete_evaluation(second, **request)
            else:
                row = store.complete_evaluation(second, **request)
                assert row["response_json"] == request["response_json"]
                if commit_first:
                    assert dict(row) == dict(original)


def test_completion_immutability_and_settings(connection, unfinished):
    def factory(cursor, row):
        return tuple(row)

    connection.row_factory = factory
    caller_cursor = connection.cursor()
    settings = (
        connection.isolation_level,
        connection.autocommit,
        connection.text_factory,
        connection.execute("PRAGMA foreign_keys").fetchone(),
    )
    try:
        with write_transaction(connection):
            row = store.complete_evaluation(connection, **unfinished)
            assert isinstance(row, sqlite3.Row)
            assert connection.row_factory is factory
            assert caller_cursor.execute("SELECT 1").fetchone() == (1,)
            assert (
                connection.isolation_level,
                connection.autocommit,
                connection.text_factory,
                connection.execute("PRAGMA foreign_keys").fetchone(),
            ) == settings
            for statement in (
                "UPDATE evaluations SET completed_at=completed_at WHERE evaluation_id=?",
                "DELETE FROM evaluations WHERE evaluation_id=?",
                "INSERT OR REPLACE INTO evaluations SELECT * FROM evaluations WHERE evaluation_id=?",
            ):
                with pytest.raises(sqlite3.IntegrityError, match="immutable"):
                    connection.execute(statement, (unfinished["evaluation_id"],))
    finally:
        caller_cursor.close()
        connection.row_factory = None


@pytest.mark.parametrize("dimension", ["evidence", "status", "state"])
def test_each_anchor_dimension_makes_failure_stale(
    connection, creation, completion, dimension
):
    with write_transaction(connection):
        connection.execute(
            "UPDATE claims SET status='NEED_INFO' WHERE claim_id=?",
            (creation["claim_id"],),
        )
        store.create_evaluation(
            connection,
            **{**creation, "expected_status": "NEED_INFO", "question_kind": "J4"},
        )
        if dimension == "evidence":
            connection.execute(
                """INSERT INTO claim_revisions SELECT
                'completion-v2', claim_id, 2, submitted_at, 'ORDINARY_CORRECTION',
                disposition, raw_evidence_json, invoice_date, reimbursement_category,
                invoice_item_amount, requested_reimbursement, validation_details_json
                FROM claim_revisions WHERE claim_id=?""",
                (creation["claim_id"],),
            )
            connection.execute(
                "UPDATE claims SET current_evidence_version=2 WHERE claim_id=?",
                (creation["claim_id"],),
            )
        elif dimension == "status":
            connection.execute(
                "UPDATE claims SET status='HUMAN_REVIEW' WHERE claim_id=?",
                (creation["claim_id"],),
            )
        else:
            connection.execute(
                "UPDATE claims SET state_version=2 WHERE claim_id=?",
                (creation["claim_id"],),
            )
        before = _snapshot(connection)
        row = store.complete_evaluation(
            connection,
            **{
                **completion,
                "response_json": None,
                "failure_code": "REMOTE_OUTCOME_UNKNOWN",
            },
        )
        assert row["write_disposition"] == "STALE"
        assert row["response_json"] is None
        assert row["error_json"] == '{"code":"REMOTE_OUTCOME_UNKNOWN"}'
        after = _snapshot(connection)
        assert all(
            after[table] == before[table] for table in TABLES if table != "evaluations"
        )


def test_completion_broken_current_evidence_is_not_staleness(connection, unfinished):
    with write_transaction(connection):
        connection.execute(
            "UPDATE claims SET status='NEED_INFO', current_evidence_version=99 WHERE claim_id=?",
            (unfinished["claim_id"],),
        )
        with pytest.raises(store.MalformedEvaluationRecord, match="anchor"):
            store.complete_evaluation(connection, **unfinished)
        assert (
            store.get_evaluation(connection, unfinished["evaluation_id"])[
                "completed_at"
            ]
            is None
        )
        connection.execute(
            "UPDATE claims SET status=NULL, current_evidence_version=1 WHERE claim_id=?",
            (unfinished["claim_id"],),
        )


@pytest.mark.parametrize(
    "action,completion_first",
    [
        pytest.param("correction", False, id="correction-before-completion"),
        pytest.param("cancellation", False, id="cancellation-before-completion"),
        pytest.param("correction", True, id="completion-before-correction"),
        pytest.param("cancellation", True, id="completion-before-cancellation"),
    ],
)
def test_completion_and_claim_change_serialize_across_connections(
    connection, creation, completion, database_path, action, completion_first
):
    with write_transaction(connection):
        connection.execute(
            "UPDATE claims SET status='NEED_INFO' WHERE claim_id=?",
            (creation["claim_id"],),
        )
        store.create_evaluation(
            connection,
            **{**creation, "expected_status": "NEED_INFO", "question_kind": "J3"},
        )
    allowance = _consumed(connection)
    operation_id = str(uuid4())

    def perform(writer, operation):
        before = _snapshot(writer)
        claim_before = dict(get_claim(writer, creation["claim_id"]))
        if operation == "complete":
            original = dict(store.get_evaluation(writer, creation["evaluation_id"]))
            result = dict(store.complete_evaluation(writer, **completion))
            expected = {
                **original,
                "completed_at": "2026-10-31T12:00:01.000000+00:00",
                "response_json": completion["response_json"],
                "error_json": None,
                "write_disposition": "DIAGNOSTIC" if completion_first else "STALE",
            }
            assert result == expected
            after = _snapshot(writer)
            assert all(
                after[table] == before[table]
                for table in TABLES
                if table != "evaluations"
            )
            assert len(after["evaluations"]) == len(before["evaluations"])
            assert [
                row
                for row in after["evaluations"]
                if row[0] != creation["evaluation_id"]
            ] == [
                row
                for row in before["evaluations"]
                if row[0] != creation["evaluation_id"]
            ]
        else:
            arguments = dict(
                claim_id=creation["claim_id"],
                operation_id=operation_id,
                expected_status="NEED_INFO",
                expected_evidence_version=1,
                expected_state_version=1,
                occurred_at=INSTANT,
            )
            if action == "correction":
                result = correct_claim(
                    writer,
                    **arguments,
                    action_kind="ORDINARY_CORRECTION",
                    raw_input={
                        "employee_id": "emp-1",
                        "merchant_name": "merchant",
                        "invoice_number": "two",
                        "invoice_date": "2026-10-01",
                        "invoice_item_name": "Revised running shoes",
                        "invoice_item_amount": "100.00",
                        "requested_reimbursement": "10.01",
                        "reimbursement_category": "WELLNESS",
                        "employee_justification": "For running",
                    },
                )
                assert result.outcome == "ACCEPTED"
                allowed = {
                    "state_version",
                    "current_evidence_version",
                    "current_revision_id",
                    "current_raw_evidence_json",
                }
            else:
                result = cancel_claim(writer, **arguments)
                assert result.outcome == "CANCELLED"
                allowed = {
                    "status",
                    "reason_code",
                    "state_version",
                    "outstanding_question_event_id",
                }
            after = _snapshot(writer)
            claim_after = dict(get_claim(writer, creation["claim_id"]))
            assert claim_after["state_version"] == 2
            assert claim_after["status"] == (
                "NEED_INFO" if action == "correction" else "CANCELLED"
            )
            assert claim_after["current_evidence_version"] == (
                2 if action == "correction" else 1
            )
            assert all(
                claim_after[key] == value
                for key, value in claim_before.items()
                if key not in allowed
            )
            assert [
                row for row in after["claims"] if row[0] != creation["claim_id"]
            ] == [row for row in before["claims"] if row[0] != creation["claim_id"]]
            assert after["evaluations"] == before["evaluations"]
            assert after["claim_events"][:-1] == before["claim_events"]
            assert after["claim_events"][-1][0] == result.event_id == operation_id
            if action == "correction":
                assert after["claim_revisions"][:-1] == before["claim_revisions"]
                assert after["claim_revisions"][-1][0] == result.revision_id
            else:
                assert after["claim_revisions"] == before["claim_revisions"]
        assert _consumed(writer) == allowance
        return result

    with connect_database(database_path) as second:
        second.execute("PRAGMA busy_timeout=0")
        committed_before = _snapshot(second)
        first_operation = "complete" if completion_first else "change"
        with write_transaction(connection):
            assert connection.in_transaction
            first_result = perform(connection, first_operation)
            assert _snapshot(second) == committed_before
            with pytest.raises(sqlite3.OperationalError, match="locked"):
                with write_transaction(second):
                    pytest.fail("The second writer must await the first commit.")
            assert not second.in_transaction
        assert not connection.in_transaction
        with write_transaction(second):
            second_result = perform(
                second, "change" if completion_first else "complete"
            )
        completed = first_result if completion_first else second_result
        with write_transaction(second):
            before = _snapshot(second)
            changes = second.total_changes
            assert dict(store.complete_evaluation(second, **completion)) == completed
            assert _snapshot(second) == before
            assert second.total_changes == changes
        assert _snapshot(connection) == _snapshot(second)
        assert second.execute("PRAGMA foreign_key_check").fetchall() == []
        assert second.execute("PRAGMA integrity_check").fetchall() == [("ok",)]


def test_evaluation_lifecycle_preserves_populated_claim_context(
    connection, creation, completion
):
    question_id = str(uuid4())
    with write_transaction(connection):
        connection.execute(
            """INSERT INTO claim_events (
                event_id, claim_id, occurred_at, event_kind, evidence_version, details_json
            ) VALUES (?, ?, ?, 'QUESTION_FIXTURE', 1, '{}')""",
            (question_id, creation["claim_id"], INSTANT.isoformat()),
        )
        connection.execute(
            """UPDATE claims SET status='NEED_INFO', reason_code='SEMANTIC_CLARIFICATION',
                uncertain_item_corrections=1, reliable_item_corrections=1,
                category_corrections=2, semantic_responses=1,
                outstanding_question_event_id=? WHERE claim_id=?""",
            (question_id, creation["claim_id"]),
        )
    claim = dict(get_claim(connection, creation["claim_id"]))
    assert tuple(
        claim[key]
        for key in (
            "uncertain_item_corrections",
            "reliable_item_corrections",
            "category_corrections",
            "semantic_responses",
        )
    ) == (1, 1, 2, 1)
    assert claim["status"] == "NEED_INFO"
    assert claim["state_version"] == claim["current_evidence_version"] == 1
    assert claim["outstanding_question_event_id"] == question_id
    assert connection.execute(
        "SELECT claim_id, evidence_version FROM claim_events WHERE event_id=?",
        (question_id,),
    ).fetchone() == (creation["claim_id"], 1)
    allowance = _consumed(connection)
    assert allowance > 0
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    assert connection.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
    creation = {**creation, "expected_status": "NEED_INFO", "question_kind": "J3"}
    with write_transaction(connection):
        before = _snapshot(connection)
        created = dict(store.create_evaluation(connection, **creation))
        after = _snapshot(connection)
        assert all(
            after[table] == before[table] for table in TABLES if table != "evaluations"
        )
        assert after["evaluations"][:-1] == before["evaluations"]
        assert after["evaluations"][-1][0] == creation["evaluation_id"]
        changes = connection.total_changes
        assert dict(store.create_evaluation(connection, **creation)) == created
        assert _snapshot(connection) == after
        assert connection.total_changes == changes
        completed = dict(store.complete_evaluation(connection, **completion))
        assert completed == {
            **created,
            "completed_at": "2026-10-31T12:00:01.000000+00:00",
            "response_json": completion["response_json"],
            "error_json": None,
            "write_disposition": "DIAGNOSTIC",
        }
        final = _snapshot(connection)
        assert all(
            final[table] == before[table] for table in TABLES if table != "evaluations"
        )
        assert final["evaluations"][:-1] == before["evaluations"]
        changes = connection.total_changes
        assert dict(store.complete_evaluation(connection, **completion)) == completed
        assert _snapshot(connection) == final
        assert connection.total_changes == changes
        assert dict(get_claim(connection, creation["claim_id"])) == claim
        assert _consumed(connection) == allowance
    assert _snapshot(connection) == final
    assert dict(get_claim(connection, creation["claim_id"])) == claim
    assert _consumed(connection) == allowance
