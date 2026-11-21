"""Exact consumption, evidence selection and caller-owned SQLite snapshots."""

import sqlite3
import sys
from contextlib import closing
from dataclasses import replace
from datetime import date, datetime, timezone
from decimal import Decimal, Inexact, InvalidOperation, Rounded, localcontext
from uuid import uuid4

import pytest

import expense_approval.allowance_store as store
from expense_approval.allowance_policy import (
    AllowancePeriod,
    AllowancePeriodKind,
    _amount_to_paise,
    _paise_to_decimal,
    get_allowance_period,
)
from expense_approval.claim_changes import cancel_claim, correct_claim
from expense_approval.claim_input import ReimbursementCategory as Category
from expense_approval.claim_store import insert_initial_claim
from expense_approval.database import (
    connect_database,
    initialize_database,
    write_transaction,
)
from expense_approval.identity import normalize_identity_text

ANNUAL = AllowancePeriod(AllowancePeriodKind.ANNUAL, 2026, None)
MONTHLY = AllowancePeriod(AllowancePeriodKind.MONTHLY, 2026, 10)
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


def seed(
    connection,
    *,
    amount="10.01",
    category=Category.WELLNESS,
    invoice="2026-10-01",
    employee="emp-1",
    status="PROCESSABLE",
):
    """SQL fixtures model stored decisions, not implemented processing logic.

    Direct projections permit malformed money and date.min/date.max cases that
    cannot be admitted through the current initial-submission helper.
    """
    claim_id = str(uuid4())
    with write_transaction(connection):
        connection.execute(
            """INSERT INTO claims (
                claim_id, status, submitted_at, original_submission_date,
                current_evidence_version, state_version, normalized_employee_id,
                normalized_merchant_name, normalized_invoice_number, invoice_line_number
            ) VALUES (?, ?, '2027-01-01', '2027-01-01', 1, 1, ?, 'shop', ?, '1')""",
            (claim_id, status, normalize_identity_text(employee), claim_id),
        )
        revision(connection, claim_id, 1, amount, category, invoice)
    return claim_id


def revision(
    connection, claim_id, version, amount, category, invoice, *, accepted=True
):
    connection.execute(
        """INSERT INTO claim_revisions (
            revision_id, claim_id, evidence_version, submitted_at, action_kind,
            disposition, raw_evidence_json, invoice_date, reimbursement_category,
            invoice_item_amount, requested_reimbursement, validation_details_json
        ) VALUES (?, ?, ?, '2028-03-01', 'FIXTURE', ?, '{}', ?, ?, '999999', ?, '{}')""",
        (
            str(uuid4()),
            claim_id,
            version,
            "ACCEPTED" if accepted else "INVALID",
            invoice,
            category.value,
            amount,
        ),
    )


def read(connection, **overrides):
    arguments = {
        "employee_id": "emp-1",
        "category": Category.WELLNESS,
        "period": ANNUAL,
    }
    arguments.update(overrides)
    return store.read_consumed_allowance(connection, **arguments)


def snapshot(connection):
    return {
        table: connection.execute(f"SELECT * FROM {table} ORDER BY 1").fetchall()
        for table in TABLES
    }


@pytest.mark.parametrize("category", list(Category)[:4])
def test_empty_and_multiple_exact_totals(connection, category):
    period = get_allowance_period(category, date(2026, 10, 1))
    assert (
        read(connection, category=category, period=period).as_tuple()
        == Decimal("0.00").as_tuple()
    )
    for amount in ("0.01", "12.34000", "1E+2", "9007199254740993.99"):
        seed(connection, amount=amount, category=category)
    result = read(connection, category=category, period=period)
    assert result.as_tuple() == Decimal("9007199254741106.34").as_tuple()


@pytest.mark.parametrize("employee", [" EMP-1 ", "\temp-1\u2003", "eMp-1"])
def test_employee_normalization_and_isolation(connection, employee):
    seed(connection)
    seed(connection, employee="emp-2", amount="777")
    assert read(connection, employee_id=employee) == Decimal("10.01")
    assert read(connection, employee_id="missing") == Decimal("0.00")


def test_unicode_identity_and_sql_parameters(connection):
    employee = " Straße  ' OR 1=1 -- "
    seed(connection, employee=employee)
    seed(connection, employee="someone else", amount="777")
    assert read(connection, employee_id="STRASSE ' OR 1=1 --") == Decimal("10.01")


@pytest.mark.parametrize("other", list(Category)[1:])
def test_category_isolation(connection, other):
    seed(connection)
    seed(connection, category=other, amount="888")
    assert read(connection) == Decimal("10.01")


@pytest.mark.parametrize(
    "period,category,inside,outside",
    [
        (
            ANNUAL,
            Category.WELLNESS,
            ["2026-01-01", "2026-12-31"],
            ["2025-12-31", "2027-01-01"],
        ),
        (
            MONTHLY,
            Category.BROADBAND,
            ["2026-10-01", "2026-10-31"],
            ["2026-09-30", "2026-11-01", "2025-10-01"],
        ),
        (
            AllowancePeriod(AllowancePeriodKind.MONTHLY, 2024, 2),
            Category.MOBILE_BILL,
            ["2024-02-01", "2024-02-29"],
            ["2024-01-31", "2024-03-01"],
        ),
        (
            AllowancePeriod(AllowancePeriodKind.MONTHLY, 2025, 2),
            Category.BROADBAND,
            ["2025-02-01", "2025-02-28"],
            ["2025-01-31", "2025-03-01"],
        ),
        (
            AllowancePeriod(AllowancePeriodKind.ANNUAL, 1, None),
            Category.SMARTPHONE,
            ["0001-01-01", "0001-12-31"],
            ["0002-01-01"],
        ),
        (
            AllowancePeriod(AllowancePeriodKind.ANNUAL, 9999, None),
            Category.WELLNESS,
            ["9999-01-01", "9999-12-31"],
            ["9998-12-31"],
        ),
        (
            AllowancePeriod(AllowancePeriodKind.MONTHLY, 1, 1),
            Category.BROADBAND,
            ["0001-01-01", "0001-01-31"],
            ["0001-02-01"],
        ),
        (
            AllowancePeriod(AllowancePeriodKind.MONTHLY, 9999, 12),
            Category.MOBILE_BILL,
            ["9999-12-01", "9999-12-31"],
            ["9999-11-30"],
        ),
    ],
)
def test_inclusive_invoice_calendar_bounds(
    connection, period, category, inside, outside
):
    for invoice in inside:
        seed(connection, invoice=invoice, category=category, amount="1.01")
    for invoice in outside:
        seed(connection, invoice=invoice, category=category, amount="not money")
    assert read(connection, category=category, period=period) == Decimal("2.02")


@pytest.mark.parametrize(
    "status", [None, "NEED_INFO", "HUMAN_REVIEW", "POLICY_RESTRICTION", "CANCELLED"]
)
def test_nonconsuming_statuses_never_parse_money(connection, status):
    seed(connection, status=status, amount="not money")
    seed(connection)
    assert read(connection) == Decimal("10.01")


def test_current_pointer_both_join_keys_and_rejected_history(connection):
    first = seed(connection, amount="11")
    second = seed(connection, amount="22")
    with write_transaction(connection):
        # Selected version 2 is deliberately not the newest history row.
        revision(connection, first, 2, "33", Category.WELLNESS, "2026-11-01")
        revision(connection, first, 3, "bad", Category.WELLNESS, "2026-11-01")
        revision(
            connection,
            first,
            None,
            "bad",
            Category.WELLNESS,
            "2026-11-01",
            accepted=False,
        )
        connection.execute(
            "UPDATE claims SET current_evidence_version=2 WHERE claim_id=?", (first,)
        )
        revision(connection, second, 2, "bad", Category.WELLNESS, "2026-11-01")
    assert read(connection) == Decimal("55.00")


@pytest.mark.parametrize(
    "category,invoice,expected",
    [
        (Category.WELLNESS, "2026-12-31", "7.50"),
        (Category.SMARTPHONE, "2026-12-31", "0.00"),
        (Category.WELLNESS, "2027-01-01", "0.00"),
    ],
)
def test_current_revision_controls_category_date_and_request(
    connection, category, invoice, expected
):
    claim_id = seed(connection, amount="123")
    with write_transaction(connection):
        revision(connection, claim_id, 2, "7.50", category, invoice)
        connection.execute(
            "UPDATE claims SET current_evidence_version=2 WHERE claim_id=?", (claim_id,)
        )
    assert read(connection) == Decimal(expected)


def payload():
    return {
        "employee_id": "emp-1",
        "merchant_name": "Shop",
        "invoice_number": "inv",
        "invoice_date": "2026-10-01",
        "invoice_item_name": "Running shoes",
        "invoice_item_amount": "1200",
        "reimbursement_category": "WELLNESS",
        "requested_reimbursement": "20",
        "employee_justification": "For running",
    }


@pytest.mark.parametrize("cancel", [False, True])
def test_public_correction_and_cancellation_history_consumes_zero(connection, cancel):
    with write_transaction(connection):
        claim_id = insert_initial_claim(
            connection,
            raw_input=payload(),
            submitted_at=datetime(2026, 11, 1, tzinfo=timezone.utc),
        )
        connection.execute(
            "UPDATE claims SET status='NEED_INFO' WHERE claim_id=?", (claim_id,)
        )
        result = correct_claim(
            connection,
            claim_id=claim_id,
            operation_id=str(uuid4()),
            action_kind="ORDINARY_CORRECTION",
            expected_status="NEED_INFO",
            expected_evidence_version=1,
            expected_state_version=1,
            raw_input={**payload(), "requested_reimbursement": "30"},
            occurred_at=datetime(2027, 1, 1, tzinfo=timezone.utc),
        )
        assert result.outcome == "ACCEPTED"
        if cancel:
            result = cancel_claim(
                connection,
                claim_id=claim_id,
                operation_id=str(uuid4()),
                expected_status="NEED_INFO",
                expected_evidence_version=2,
                expected_state_version=2,
                occurred_at=datetime(2027, 2, 1, tzinfo=timezone.utc),
            )
            assert result.outcome == "CANCELLED"
    assert read(connection) == Decimal("0.00")
    if not cancel:
        # Trusted fixture transition only: final processing is deferred.
        connection.execute(
            "UPDATE claims SET status='PROCESSABLE' WHERE claim_id=?", (claim_id,)
        )
        assert read(connection) == Decimal("30.00")


def test_extreme_helpers_and_reader_preserve_decimal_and_integer_context(connection):
    limit = sys.get_int_max_str_digits()
    huge = "9" * 6000 + ".99"
    expected = Decimal("1" + "0" * 6000 + ".00")
    seed(connection, amount=huge)
    seed(connection, amount="0.01")
    with localcontext() as context:
        context.prec = 2
        context.Emax = 9
        context.Emin = -9
        context.traps[Inexact] = context.traps[Rounded] = True
        context.traps[InvalidOperation] = False
        context.flags[Inexact] = True
        before = context.copy()
        assert (
            _paise_to_decimal(_amount_to_paise(Decimal(huge)) + 1).as_tuple()
            == expected.as_tuple()
        )
        assert read(connection).as_tuple() == expected.as_tuple()
        assert context.flags == before.flags
        assert context.traps == before.traps
        assert (context.prec, context.Emax, context.Emin) == (2, 9, -9)
    assert sys.get_int_max_str_digits() == limit


class OrderedCursor(sqlite3.Cursor):
    """Control iteration in this test; production SQL promises no row order."""

    def __iter__(self):
        rows = self.fetchall()
        return iter(sorted(rows, key=lambda row: row[0] != "1.00"))


class OrderedConnection(sqlite3.Connection):
    def cursor(self, *args, **kwargs):
        return super().cursor(factory=OrderedCursor)


@pytest.mark.parametrize(
    "bad",
    [
        "bad",
        "",
        "NaN",
        "sNaN",
        "Infinity",
        "-Infinity",
        "0",
        "-0",
        "-1",
        "1.001",
        "1E-3",
    ],
)
def test_malformed_selected_row_fails_after_valid_rows_without_partial_total(
    database_path, monkeypatch, bad
):
    with closing(
        sqlite3.connect(database_path, factory=OrderedConnection, isolation_level=None)
    ) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        seed(connection, amount="1.00")
        seed(connection, amount="1.00")
        seed(connection, amount=bad)
        before = snapshot(connection)
        changes = connection.total_changes
        processed = []
        original = store._amount_to_paise

        def record(amount):
            processed.append(amount)
            return original(amount)

        monkeypatch.setattr(store, "_amount_to_paise", record)
        with localcontext() as context:
            context.traps[InvalidOperation] = False
            flags, traps = context.flags.copy(), context.traps.copy()
            with pytest.raises(
                ValueError, match="^Stored requested reimbursement is invalid\\.$"
            ) as error:
                read(connection)
            assert context.flags == flags and context.traps == traps
        assert isinstance(error.value.__cause__, ValueError)
        assert processed == [Decimal("1.00"), Decimal("1.00")]
        assert snapshot(connection) == before
        assert connection.total_changes == changes
        assert not connection.in_transaction
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []


@pytest.mark.parametrize("factory", [bytes, lambda text: 123])
def test_nontext_decoding_rejected_without_setting_changes(connection, factory):
    seed(connection)
    connection.text_factory = factory
    with pytest.raises(ValueError, match="Stored requested reimbursement is invalid"):
        read(connection)
    assert connection.text_factory is factory
    connection.text_factory = str


@pytest.mark.parametrize(
    "overrides,error,message",
    [
        ({"employee_id": None}, TypeError, "Identity text must be a string."),
        ({"employee_id": " \u2003"}, ValueError, "Employee ID must be nonblank text."),
        (
            {"category": "WELLNESS"},
            TypeError,
            "Category must be a ReimbursementCategory.",
        ),
        *[
            (
                {"category": category},
                ValueError,
                "Consumption reads require a capped category.",
            )
            for category in (Category.BUSINESS_HOTEL, Category.BUSINESS_TRANSPORT)
        ],
        ({"period": None}, TypeError, "Period must be an AllowancePeriod."),
        ({"period": "2026"}, TypeError, "Period must be an AllowancePeriod."),
        (
            {"period": replace(ANNUAL, kind="ANNUAL")},
            TypeError,
            "Period kind must be an AllowancePeriodKind.",
        ),
        (
            {"period": replace(ANNUAL, kind=AllowancePeriodKind.MONTHLY)},
            ValueError,
            "Period kind must match the category allowance period.",
        ),
        *[
            (
                {"period": replace(ANNUAL, year=year)},
                TypeError,
                "Period year must be an integer.",
            )
            for year in (True, False, "2026", 2026.0, None)
        ],
        *[
            (
                {"period": replace(ANNUAL, year=year)},
                ValueError,
                "Period year must be between 1 and 9999.",
            )
            for year in (0, -1, 10000)
        ],
        *[
            (
                {"period": replace(ANNUAL, month=month)},
                ValueError,
                "Annual periods must have month=None.",
            )
            for month in (1, False, "1")
        ],
        *[
            (
                {
                    "category": Category.BROADBAND,
                    "period": replace(MONTHLY, month=month),
                },
                TypeError,
                "Monthly period month must be an integer.",
            )
            for month in (True, False, None, "10", 10.0)
        ],
        *[
            (
                {
                    "category": Category.BROADBAND,
                    "period": replace(MONTHLY, month=month),
                },
                ValueError,
                "Monthly period month must be between 1 and 12.",
            )
            for month in (0, -1, 13)
        ],
    ],
)
def test_argument_validation_before_sql(connection, overrides, error, message):
    statements = []
    connection.set_trace_callback(statements.append)
    with pytest.raises(error) as raised:
        read(connection, **overrides)
    assert str(raised.value) == message
    assert statements == []
    connection.set_trace_callback(None)


def test_validation_precedence(connection):
    with pytest.raises(TypeError, match="Connection must be"):
        read(object(), employee_id=None, category=None, period=None)
    for overrides, message in [
        ({"employee_id": "", "category": None, "period": None}, "Employee ID"),
        ({"category": None, "period": None}, "Category must"),
        ({"category": Category.BUSINESS_HOTEL, "period": None}, "capped category"),
        ({"period": AllowancePeriod("ANNUAL", False, False)}, "Period kind must be an"),
        (
            {"period": AllowancePeriod(AllowancePeriodKind.MONTHLY, False, False)},
            "Period kind must match",
        ),
        ({"period": replace(ANNUAL, year=False, month=1)}, "Period year must be an"),
        ({"period": replace(ANNUAL, year=0, month=1)}, "Period year must be between"),
    ]:
        with pytest.raises((TypeError, ValueError), match=message):
            read(connection, **overrides)


def test_caller_settings_query_only_factories_and_complete_preservation(connection):
    claim_id = seed(connection)
    event_id = str(uuid4())
    connection.execute(
        """INSERT INTO claim_events (
            event_id, claim_id, occurred_at, event_kind, evidence_version, details_json
        ) VALUES (?, ?, 'earlier', 'QUESTION_FIXTURE', 1, '{}')""",
        (event_id, claim_id),
    )
    connection.execute(
        "UPDATE claims SET uncertain_item_corrections=1, reliable_item_corrections=1, category_corrections=2, semantic_responses=2, outstanding_question_event_id=? WHERE claim_id=?",
        (event_id, claim_id),
    )
    connection.execute(
        "INSERT INTO evaluations (evaluation_id, claim_id, evidence_version, evaluation_run_id, question_kind, question_revision, model_version, expected_state_version, started_at, completed_at, input_snapshot_json, response_json, write_disposition) VALUES (?, ?, 1, 'run', 'J1', 'q', 'model', 1, 'start', 'end', '{}', '{}', 'APPLIED')",
        (str(uuid4()), claim_id),
    )
    before = snapshot(connection)
    changes = connection.total_changes
    pragmas = (
        "foreign_keys",
        "recursive_triggers",
        "user_version",
        "journal_mode",
        "query_only",
        "busy_timeout",
    )
    connection.execute("PRAGMA query_only=ON")
    settings = {
        name: connection.execute(f"PRAGMA {name}").fetchall() for name in pragmas
    }

    def factory(cursor, row):
        return {"custom": row}

    connection.row_factory = factory
    connection.text_factory = str
    trace = []
    connection.set_trace_callback(trace.append)
    assert read(connection) == Decimal("10.01")
    assert read(connection) == Decimal("10.01")
    assert len(trace) == 2 and all(sql.lstrip().startswith("SELECT") for sql in trace)
    assert connection.row_factory is factory and connection.text_factory is str
    assert connection.isolation_level is None
    assert connection.autocommit == sqlite3.LEGACY_TRANSACTION_CONTROL
    assert not connection.in_transaction
    connection.set_trace_callback(None)
    connection.row_factory = None
    assert snapshot(connection) == before and connection.total_changes == changes
    assert {
        name: connection.execute(f"PRAGMA {name}").fetchall() for name in pragmas
    } == settings
    connection.execute("PRAGMA query_only=OFF")


def test_caller_transaction_savepoint_read_your_writes_and_rollback(
    connection, database_path
):
    claim_id = seed(connection, status="NEED_INFO")
    before = snapshot(connection)
    with connect_database(database_path) as observer:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("SAVEPOINT caller")
        connection.execute(
            "UPDATE claims SET status='PROCESSABLE' WHERE claim_id=?", (claim_id,)
        )
        changes = connection.total_changes
        assert read(connection) == Decimal("10.01")
        assert read(observer) == Decimal("0.00")
        assert connection.in_transaction and connection.total_changes == changes
        connection.execute("ROLLBACK TO caller")
        assert read(connection) == Decimal("0.00")
        connection.execute("RELEASE caller")
        assert connection.in_transaction
        connection.rollback()
    assert snapshot(connection) == before


def test_failure_leaves_caller_savepoint_and_transaction(connection):
    seed(connection, amount="bad")
    connection.execute("BEGIN")
    connection.execute("SAVEPOINT caller")
    with pytest.raises(ValueError, match="Stored requested"):
        read(connection)
    assert connection.in_transaction
    connection.execute("ROLLBACK TO caller")
    connection.execute("RELEASE caller")
    connection.rollback()


def test_sqlite_failures_propagate(connection):
    empty = sqlite3.connect(":memory:")
    with pytest.raises(sqlite3.OperationalError, match="no such table"):
        read(empty)
    empty.close()
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        read(empty)
    connection.set_authorizer(
        lambda action, *args: sqlite3.SQLITE_DENY
        if action == sqlite3.SQLITE_READ
        else sqlite3.SQLITE_OK
    )
    with pytest.raises(sqlite3.DatabaseError):
        read(connection)
    connection.set_authorizer(None)
    assert not connection.in_transaction


@pytest.mark.parametrize("journal", ["WAL", "DELETE"])
def test_two_connection_snapshot_and_journal_specific_commit(
    connection, database_path, journal
):
    assert (
        connection.execute(f"PRAGMA journal_mode={journal}").fetchone()[0]
        == journal.lower()
    )
    claim_id = seed(connection, status="NEED_INFO")
    with connect_database(database_path) as writer:
        writer.execute("PRAGMA busy_timeout=0")
        connection.execute("BEGIN")
        assert read(connection) == Decimal("0.00")  # Establish the snapshot.
        writer.execute("BEGIN IMMEDIATE")
        writer.execute(
            "UPDATE claims SET status='PROCESSABLE' WHERE claim_id=?", (claim_id,)
        )
        assert read(writer) == Decimal("10.01")
        assert read(connection) == Decimal("0.00")
        if journal == "WAL":
            writer.commit()
            assert read(connection) == Decimal("0.00")
        else:
            # Rollback-journal readers prevent writer COMMIT, not its UPDATE.
            with pytest.raises(sqlite3.OperationalError, match="locked"):
                writer.commit()
            assert writer.in_transaction
        connection.rollback()
        if writer.in_transaction:
            writer.commit()
        assert read(connection) == Decimal("10.01")


def test_streaming_select_keeps_one_wal_snapshot(
    connection, database_path, monkeypatch
):
    assert connection.execute("PRAGMA journal_mode=WAL").fetchone() == ("wal",)
    seed(connection, amount="1")
    seed(connection, amount="1")
    seed(connection, amount="1")
    pending = seed(connection, amount="7", status="NEED_INFO")
    with connect_database(database_path) as writer:
        original = store._amount_to_paise
        processed = 0

        def commit_after_first_row(amount):
            nonlocal processed
            processed += 1
            if processed == 1:
                with write_transaction(writer):
                    writer.execute(
                        "UPDATE claims SET status='PROCESSABLE' WHERE claim_id=?",
                        (pending,),
                    )
            return original(amount)

        monkeypatch.setattr(store, "_amount_to_paise", commit_after_first_row)
        assert read(connection) == Decimal("3.00")
        assert processed == 3
        assert not connection.in_transaction
        assert read(connection) == Decimal("10.00")


@pytest.mark.parametrize("row_factory", [None, sqlite3.Row, lambda cursor, row: 42])
def test_standard_connection_defaults_and_factories(database_path, row_factory):
    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = row_factory
        before = (connection.isolation_level, connection.autocommit)
        assert read(connection).as_tuple() == Decimal("0.00").as_tuple()
        assert connection.row_factory is row_factory
        assert (connection.isolation_level, connection.autocommit) == before
        assert not connection.in_transaction


class TrackingConnection(sqlite3.Connection):
    last_cursor = None

    def cursor(self, *args, **kwargs):
        self.last_cursor = super().cursor(*args, **kwargs)
        return self.last_cursor


@pytest.mark.parametrize("failure", [None, "money", "resource", "sql"])
def test_reader_closes_only_its_cursor_on_success_and_failure(
    database_path, monkeypatch, failure
):
    with closing(
        sqlite3.connect(database_path, factory=TrackingConnection, isolation_level=None)
    ) as connection:
        seed(connection, amount="bad" if failure == "money" else "1.00")
        caller_cursor = connection.cursor()
        before = snapshot(connection)
        changes = connection.total_changes
        if failure == "resource":

            def exhausted(amount):
                raise MemoryError("resource fixture")

            monkeypatch.setattr(store, "_amount_to_paise", exhausted)
        if failure == "sql":
            connection.set_progress_handler(lambda: 1, 1)
        if failure is None:
            assert read(connection) == Decimal("1.00")
        else:
            error = {
                "money": ValueError,
                "resource": MemoryError,
                "sql": sqlite3.OperationalError,
            }[failure]
            with pytest.raises(error):
                read(connection)
        connection.set_progress_handler(None, 0)
        with pytest.raises(sqlite3.ProgrammingError, match="closed cursor"):
            connection.last_cursor.fetchone()
        assert caller_cursor.execute("SELECT 1").fetchone() == (1,)
        caller_cursor.close()
        assert snapshot(connection) == before and connection.total_changes == changes
        assert not connection.in_transaction
