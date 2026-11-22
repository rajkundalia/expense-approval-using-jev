"""Slice 1 validation and opaque reads; evaluations are direct-SQL fixtures."""

import sqlite3
from datetime import date, datetime, timedelta, timezone, tzinfo

import pytest

import expense_approval.evaluation_store as store
from expense_approval.allowance_policy import get_allowance_period
from expense_approval.allowance_store import read_consumed_allowance
from expense_approval.claim_input import ReimbursementCategory
from expense_approval.claim_store import insert_initial_claim
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
