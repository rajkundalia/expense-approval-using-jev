"""Composition results, uncapped bypass, caller ownership and preservation."""

import sqlite3
import sys
from contextlib import closing
from datetime import date, datetime, timezone
from decimal import Decimal, Inexact, InvalidOperation, Rounded, localcontext
from uuid import uuid4

import pytest

import expense_approval.candidate_allowance as composition
from expense_approval.allowance_policy import (
    AllowanceAssessment,
    AllowanceOutcome,
    AllowancePeriod,
    AllowancePeriodKind,
)
from expense_approval.claim_changes import correct_claim
from expense_approval.claim_input import ClaimInput
from expense_approval.claim_input import ReimbursementCategory as Category
from expense_approval.claim_store import insert_initial_claim
from expense_approval.database import (
    connect_database,
    initialize_database,
    write_transaction,
)

CAPS = [
    (Category.WELLNESS, "30000", "29999.99", "30000.01"),
    (Category.SMARTPHONE, "100000", "99999.99", "100000.01"),
    (Category.BROADBAND, "3000", "2999.99", "3000.01"),
    (Category.MOBILE_BILL, "750", "749.99", "750.01"),
]
TABLES = ("claims", "claim_revisions", "claim_events", "evaluations")


def payload(**overrides):
    values = {
        "employee_id": "emp-1",
        "merchant_name": "Shop",
        "invoice_number": str(uuid4()),
        "invoice_date": "2026-10-01",
        "invoice_item_name": "Candidate item",
        "invoice_item_amount": "1000000",
        "reimbursement_category": Category.WELLNESS,
        "requested_reimbursement": "12.3400",
        "employee_justification": "Employee purpose",
    }
    values.update(overrides)
    return values


def candidate(**overrides):
    # Always use normal validation, including for prospective corrections.
    return ClaimInput.model_validate(payload(**overrides))


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


def persist(connection, *, status="PROCESSABLE", **overrides):
    """Public initial storage plus an explicit fixture-only status decision."""
    raw = payload(**overrides)
    invoice_date = ClaimInput.model_validate(raw).invoice_date
    with write_transaction(connection):
        claim_id = insert_initial_claim(
            connection,
            raw_input=raw,
            submitted_at=datetime.combine(
                invoice_date, datetime.min.time(), timezone.utc
            ),
        )
        connection.execute(
            "UPDATE claims SET status=? WHERE claim_id=?", (status, claim_id)
        )
    return claim_id


def add_history(connection, claim_id, version, amount, *, current=False):
    """Append projections without disabling immutable-history protections."""
    connection.execute(
        """INSERT INTO claim_revisions (
            revision_id, claim_id, evidence_version, submitted_at, action_kind,
            disposition, raw_evidence_json, invoice_date, reimbursement_category,
            invoice_item_amount, requested_reimbursement, validation_details_json
        ) SELECT ?, claim_id, ?, '2027-03-01', 'FIXTURE', ?, raw_evidence_json,
            invoice_date, reimbursement_category, invoice_item_amount, ?, '{}'
        FROM claim_revisions WHERE claim_id=? AND evidence_version=1""",
        (
            str(uuid4()),
            version,
            "INVALID" if version is None else "ACCEPTED",
            amount,
            claim_id,
        ),
    )
    if current:
        connection.execute(
            "UPDATE claims SET current_evidence_version=? WHERE claim_id=?",
            (version, claim_id),
        )


def snapshot(connection):
    return {
        table: connection.execute(f"SELECT * FROM {table} ORDER BY 1").fetchall()
        for table in TABLES
    }


@pytest.mark.parametrize("category,cap,below,above", CAPS)
@pytest.mark.parametrize(
    "scenario", ["empty", "within", "equal", "exceeds", "full", "overconsumed"]
)
def test_capped_results_use_existing_exact_assessment(
    connection, category, cap, below, above, scenario
):
    after_one_rupee = {
        Category.WELLNESS: "29999.00",
        Category.SMARTPHONE: "99999.00",
        Category.BROADBAND: "2999.00",
        Category.MOBILE_BILL: "749.00",
    }[category]
    consumed, requested, remaining, outcome = {
        "empty": ("0.00", cap, cap + ".00", AllowanceOutcome.WITHIN_ALLOWANCE),
        "within": ("1.00", "0.01", after_one_rupee, AllowanceOutcome.WITHIN_ALLOWANCE),
        "equal": (below, "0.0100", "0.01", AllowanceOutcome.WITHIN_ALLOWANCE),
        "exceeds": (below, "0.02", "0.01", AllowanceOutcome.EXCEEDS_ALLOWANCE),
        "full": (cap, "0.01", "0.00", AllowanceOutcome.EXCEEDS_ALLOWANCE),
        "overconsumed": (above, "0.01", "-0.01", AllowanceOutcome.EXCEEDS_ALLOWANCE),
    }[scenario]
    if scenario != "empty":
        persist(
            connection,
            reimbursement_category=category,
            requested_reimbursement=consumed,
        )
    claim = candidate(
        reimbursement_category=category, requested_reimbursement=requested
    )
    before = snapshot(connection)
    changes = connection.total_changes
    result = composition.assess_candidate_allowance(connection, candidate=claim)
    expected_period = AllowancePeriod(
        AllowancePeriodKind.ANNUAL
        if category in (Category.WELLNESS, Category.SMARTPHONE)
        else AllowancePeriodKind.MONTHLY,
        2026,
        None if category in (Category.WELLNESS, Category.SMARTPHONE) else 10,
    )
    assert result == AllowanceAssessment(
        category,
        expected_period,
        Decimal(requested),
        Decimal(cap),
        Decimal(consumed),
        Decimal(remaining),
        outcome,
    )
    assert result.requested.as_tuple() == claim.requested_reimbursement.as_tuple()
    assert (
        result.consumed.as_tuple().exponent
        == result.remaining.as_tuple().exponent
        == -2
    )
    assert not result.remaining.is_zero() or not result.remaining.is_signed()
    assert snapshot(connection) == before and connection.total_changes == changes


def test_multiple_consumption_and_literal_remaining(connection):
    persist(connection, requested_reimbursement="1200")
    persist(connection, requested_reimbursement="34.56")
    for request, outcome in [
        ("28765.44", AllowanceOutcome.WITHIN_ALLOWANCE),
        ("28765.45", AllowanceOutcome.EXCEEDS_ALLOWANCE),
    ]:
        result = composition.assess_candidate_allowance(
            connection, candidate=candidate(requested_reimbursement=request)
        )
        assert result.consumed == Decimal("1234.56")
        assert result.remaining.as_tuple() == Decimal("28765.44").as_tuple()
        assert result.outcome is outcome


@pytest.mark.parametrize(
    "category", [Category.BUSINESS_HOTEL, Category.BUSINESS_TRANSPORT]
)
@pytest.mark.parametrize("closed", [False, True])
def test_uncapped_never_accesses_sqlite_including_closed_connection(
    monkeypatch, category, closed
):
    connection = sqlite3.connect(":memory:")  # Deliberately no application schema.
    statements = []
    connection.set_trace_callback(statements.append)
    if closed:
        connection.close()
    original_assess = composition.assess_allowance
    supplied = []

    def forbidden(*args, **kwargs):
        pytest.fail("Uncapped assessment accessed the consumption reader")

    def record(category, invoice_date, requested, consumed):
        supplied.append(consumed)
        return original_assess(category, invoice_date, requested, consumed)

    monkeypatch.setattr(composition, "read_consumed_allowance", forbidden)
    monkeypatch.setattr(composition, "assess_allowance", record)
    claim = candidate(reimbursement_category=category, invoice_date=date.max)
    try:
        result = composition.assess_candidate_allowance(connection, candidate=claim)
        assert result == AllowanceAssessment(
            category,
            None,
            Decimal("12.3400"),
            None,
            None,
            None,
            AllowanceOutcome.UNCAPPED,
        )
        assert supplied == [None] and statements == []
        if not closed:
            assert not connection.in_transaction
    finally:
        connection.close()


@pytest.mark.parametrize(
    "category,inside,outside,kind,month",
    [
        (
            Category.WELLNESS,
            ["2026-01-01", "2026-12-31"],
            ["2025-12-31", "2027-01-01"],
            AllowancePeriodKind.ANNUAL,
            None,
        ),
        (
            Category.BROADBAND,
            ["2026-10-01", "2026-10-31"],
            ["2026-09-30", "2026-11-01"],
            AllowancePeriodKind.MONTHLY,
            10,
        ),
    ],
)
def test_candidate_invoice_period_and_identity_scope(
    connection, category, inside, outside, kind, month
):
    for invoice in inside:
        persist(
            connection,
            invoice_date=invoice,
            reimbursement_category=category,
            requested_reimbursement="1.01",
            employee_id=" Straße  Team ",
        )
    for invoice in outside:
        persist(
            connection,
            invoice_date=invoice,
            reimbursement_category=category,
            requested_reimbursement="777",
            employee_id="strasse team",
        )
    persist(
        connection,
        reimbursement_category=category,
        employee_id="other",
        requested_reimbursement="888",
    )
    other_category = (
        Category.SMARTPHONE if category is Category.WELLNESS else Category.MOBILE_BILL
    )
    persist(
        connection,
        reimbursement_category=other_category,
        employee_id="strasse team",
        requested_reimbursement="999",
    )
    result = composition.assess_candidate_allowance(
        connection,
        candidate=candidate(
            employee_id="\tSTRASSE\u2003TEAM ", reimbursement_category=category
        ),
    )
    assert result.consumed == Decimal("2.02")
    assert result.period == AllowancePeriod(kind, 2026, month)


def test_current_accepted_evidence_and_no_claim_exclusion(connection):
    raw = payload(requested_reimbursement="10")
    claim_id = persist(connection, **raw)
    with write_transaction(connection):
        add_history(connection, claim_id, 2, "20", current=True)
        add_history(connection, claim_id, 3, "bad")
        add_history(connection, claim_id, None, "bad")
    # Candidate represents this same already-PROCESSABLE invoice line.
    claim = ClaimInput.model_validate({**raw, "requested_reimbursement": "20"})
    before = snapshot(connection)
    for _ in range(2):
        result = composition.assess_candidate_allowance(connection, candidate=claim)
        assert result.requested == result.consumed == Decimal("20")
        assert result.remaining == Decimal("29980.00")
    assert snapshot(connection) == before


@pytest.mark.parametrize(
    "status", [None, "NEED_INFO", "HUMAN_REVIEW", "POLICY_RESTRICTION", "CANCELLED"]
)
def test_nonconsuming_candidate_statuses_are_not_transitioned(connection, status):
    persist(connection, status=status)
    before = snapshot(connection)
    result = composition.assess_candidate_allowance(connection, candidate=candidate())
    assert result.consumed == Decimal("0.00")
    assert snapshot(connection) == before


@pytest.mark.parametrize("bad", [None, {}, "claim", 1, True])
def test_type_guards_precede_database_access(connection, bad):
    statements = []
    connection.set_trace_callback(statements.append)
    with pytest.raises(TypeError, match="^Connection must be a sqlite3.Connection\\.$"):
        composition.assess_candidate_allowance(object(), candidate=bad)
    with pytest.raises(TypeError, match="^Candidate must be a ClaimInput\\.$"):
        composition.assess_candidate_allowance(connection, candidate=bad)
    assert statements == []
    connection.set_trace_callback(None)


@pytest.mark.parametrize("category", list(Category))
def test_connection_type_guard_applies_to_every_category(category):
    with pytest.raises(TypeError, match="^Connection must be a sqlite3.Connection\\.$"):
        composition.assess_candidate_allowance(
            None, candidate=candidate(reimbursement_category=category)
        )


@pytest.mark.parametrize("invoice_date", [date.min, date.max])
def test_capped_period_selection_does_not_validate_contextual_eligibility(
    connection, invoice_date
):
    claim = candidate(invoice_date=invoice_date)
    result = composition.assess_candidate_allowance(connection, candidate=claim)
    assert result.period == AllowancePeriod(
        AllowancePeriodKind.ANNUAL, invoice_date.year, None
    )
    assert result.consumed == Decimal("0.00")


@pytest.mark.parametrize(
    "dependency",
    [
        "get_allowance_policy",
        "get_allowance_period",
        "read_consumed_allowance",
        "assess_allowance",
    ],
)
def test_dependency_errors_propagate_unchanged(connection, monkeypatch, dependency):
    failure = ValueError("dependency failure")

    def fail(*args, **kwargs):
        raise failure

    monkeypatch.setattr(composition, dependency, fail)
    with pytest.raises(ValueError) as raised:
        composition.assess_candidate_allowance(connection, candidate=candidate())
    assert raised.value is failure


def test_capped_closed_and_missing_schema_errors_propagate():
    with closing(sqlite3.connect(":memory:")) as connection:
        with pytest.raises(sqlite3.OperationalError, match="no such table"):
            composition.assess_candidate_allowance(connection, candidate=candidate())
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        composition.assess_candidate_allowance(connection, candidate=candidate())


@pytest.mark.parametrize("amount", ["not money", "1.001"])
def test_malformed_consumption_stops_before_final_assessment(
    connection, monkeypatch, amount
):
    claim_id = persist(connection)
    with write_transaction(connection):
        add_history(connection, claim_id, 2, amount, current=True)
    before = snapshot(connection)
    changes = connection.total_changes

    def forbidden(*args, **kwargs):
        pytest.fail("Final assessment ran after a consumption error")

    monkeypatch.setattr(composition, "assess_allowance", forbidden)
    connection.execute("BEGIN")
    connection.execute("SAVEPOINT caller")
    with pytest.raises(
        ValueError, match="^Stored requested reimbursement is invalid\\.$"
    ) as raised:
        composition.assess_candidate_allowance(connection, candidate=candidate())
    assert isinstance(raised.value.__cause__, ValueError)
    assert connection.in_transaction
    connection.execute("ROLLBACK TO caller")
    connection.execute("RELEASE caller")
    connection.rollback()
    assert snapshot(connection) == before and connection.total_changes == changes


def test_caller_savepoint_and_uncommitted_consumption(connection, database_path):
    claim_id = persist(connection, status="NEED_INFO", requested_reimbursement="50")
    before = snapshot(connection)
    claim = candidate()
    with connect_database(database_path) as observer:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("SAVEPOINT caller")
        connection.execute(
            "UPDATE claims SET status='PROCESSABLE' WHERE claim_id=?", (claim_id,)
        )
        changes = connection.total_changes
        assert composition.assess_candidate_allowance(
            connection, candidate=claim
        ).consumed == Decimal("50.00")
        assert composition.assess_candidate_allowance(
            observer, candidate=claim
        ).consumed == Decimal("0.00")
        assert connection.in_transaction and connection.total_changes == changes
        connection.execute("ROLLBACK TO caller")
        assert composition.assess_candidate_allowance(
            connection, candidate=claim
        ).consumed == Decimal("0.00")
        connection.execute("RELEASE caller")
        assert connection.in_transaction
        connection.rollback()
    assert snapshot(connection) == before


def test_complete_data_and_connection_settings_preserved(connection):
    claim_id = persist(connection, status="NEED_INFO", requested_reimbursement="100")
    with write_transaction(connection):
        result = correct_claim(
            connection,
            claim_id=claim_id,
            operation_id=str(uuid4()),
            action_kind="ORDINARY_CORRECTION",
            expected_status="NEED_INFO",
            expected_evidence_version=1,
            expected_state_version=1,
            raw_input=payload(requested_reimbursement="125"),
            occurred_at=datetime(2027, 3, 1, tzinfo=timezone.utc),
        )
        assert result.outcome == "ACCEPTED"
        connection.execute(
            "UPDATE claims SET status='PROCESSABLE', uncertain_item_corrections=1, reliable_item_corrections=1, category_corrections=2, semantic_responses=2 WHERE claim_id=?",
            (claim_id,),
        )
        connection.execute(
            "INSERT INTO evaluations (evaluation_id, claim_id, evidence_version, evaluation_run_id, question_kind, question_revision, model_version, expected_state_version, started_at, completed_at, input_snapshot_json, response_json, write_disposition) VALUES (?, ?, 2, 'run', 'J1', 'question', 'model', 2, 'start', 'end', '{}', '{}', 'APPLIED')",
            (str(uuid4()), claim_id),
        )
    before = snapshot(connection)
    changes = connection.total_changes
    claim = candidate(requested_reimbursement="30000")
    candidate_before = claim.model_dump()
    connection.execute("PRAGMA query_only=ON")
    names = (
        "foreign_keys",
        "recursive_triggers",
        "user_version",
        "journal_mode",
        "query_only",
        "busy_timeout",
    )
    settings = {name: connection.execute(f"PRAGMA {name}").fetchall() for name in names}
    isolation, autocommit = connection.isolation_level, connection.autocommit

    def custom_factory(cursor, row):
        return {"custom": row}

    connection.row_factory = custom_factory
    statements = []
    connection.set_trace_callback(statements.append)
    for _ in range(2):
        result = composition.assess_candidate_allowance(connection, candidate=claim)
        assert result.consumed == Decimal("125.00")
        assert result.outcome is AllowanceOutcome.EXCEEDS_ALLOWANCE
    assert len(statements) == 2 and all(
        statement.lstrip().startswith("SELECT") for statement in statements
    )
    assert connection.row_factory is custom_factory and connection.text_factory is str
    assert (connection.isolation_level, connection.autocommit) == (
        isolation,
        autocommit,
    )
    assert not connection.in_transaction
    assert claim.model_dump() == candidate_before
    connection.set_trace_callback(None)
    connection.row_factory = None
    assert snapshot(connection) == before and connection.total_changes == changes
    assert {
        name: connection.execute(f"PRAGMA {name}").fetchall() for name in names
    } == settings
    connection.execute("PRAGMA query_only=OFF")


def test_extreme_exact_results_and_decimal_context_preservation(connection):
    huge = "1" + "0" * 6000
    persist(connection, requested_reimbursement=huge, invoice_item_amount=huge)
    claim = candidate(requested_reimbursement="0.0100")
    # Independent pattern for -(10**6000 - 30000), with two decimal places.
    expected = Decimal("-" + "9" * 5995 + "70000.00")
    limit = sys.get_int_max_str_digits()
    with localcontext() as context:
        context.prec = 1
        context.Emax, context.Emin = 2, -2
        context.traps[Inexact] = context.traps[Rounded] = True
        context.traps[InvalidOperation] = False
        context.flags[Inexact] = True
        before = repr(context)
        result = composition.assess_candidate_allowance(connection, candidate=claim)
        assert result.remaining.as_tuple() == expected.as_tuple()
        assert result.requested.as_tuple() == Decimal("0.0100").as_tuple()
        assert result.consumed.as_tuple() == Decimal(huge + ".00").as_tuple()
        assert result.outcome is AllowanceOutcome.EXCEEDS_ALLOWANCE
        assert repr(context) == before
    assert sys.get_int_max_str_digits() == limit
