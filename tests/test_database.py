"""Direct SQLite schema tests; these do not implement or prove claim workflows."""

import sqlite3
from pathlib import Path

import pytest

from expense_approval.database import (
    SCHEMA_VERSION,
    connect_database,
    initialize_database,
    write_transaction,
)


@pytest.fixture
def database_path(tmp_path: Path) -> Path:
    path = tmp_path / "claims.sqlite3"
    initialize_database(path)
    return path


def insert_revision(
    connection: sqlite3.Connection,
    claim_id: str = "claim-1",
    overrides: dict[str, object] | None = None,
) -> None:
    values: dict[str, object] = {
        "revision_id": f"revision-{claim_id}",
        "claim_id": claim_id,
        "evidence_version": 1,
        "disposition": "ACCEPTED",
        "raw_evidence_json": '{"merchant_name":"  Example MERCHANT  "}',
        "invoice_date": "2026-10-31",
        "reimbursement_category": "WELLNESS",
        "invoice_item_amount": "1200.0000",
        "requested_reimbursement": "1000.00",
        "validation_details_json": "{}",
    }
    values.update(overrides or {})
    connection.execute(
        """INSERT INTO claim_revisions (
            revision_id, claim_id, evidence_version, submitted_at, action_kind,
            disposition, raw_evidence_json, invoice_date, reimbursement_category,
            invoice_item_amount, requested_reimbursement, validation_details_json
        ) VALUES (
            :revision_id, :claim_id, :evidence_version, '2026-10-31T12:00:00+00:00',
            'INITIAL', :disposition, :raw_evidence_json, :invoice_date,
            :reimbursement_category, :invoice_item_amount,
            :requested_reimbursement, :validation_details_json
        )""",
        values,
    )


def insert_claim(
    connection: sqlite3.Connection,
    claim_id: str = "claim-1",
    overrides: dict[str, object] | None = None,
    *,
    with_revision: bool = True,
) -> None:
    values: dict[str, object] = {
        "claim_id": claim_id,
        "status": None,
        "invoice_number": claim_id,
        "line_number": "1",
    }
    values.update(overrides or {})
    connection.execute(
        """INSERT INTO claims (
            claim_id, status, submitted_at, original_submission_date,
            current_evidence_version, state_version, normalized_employee_id,
            normalized_merchant_name, normalized_invoice_number, invoice_line_number
        ) VALUES (
            :claim_id, :status, '2026-10-31T12:00:00+00:00', '2026-10-31',
            1, 1, 'emp-1', 'example merchant', :invoice_number, :line_number
        )""",
        values,
    )
    if with_revision:
        insert_revision(connection, claim_id)


def insert_evaluation(
    connection: sqlite3.Connection,
    claim_id: str = "claim-1",
    *,
    evidence_version: int = 1,
) -> None:
    connection.execute(
        """INSERT INTO evaluations (
            evaluation_id, claim_id, evidence_version, evaluation_run_id,
            question_kind, question_revision, model_version, expected_status,
            expected_state_version, started_at, input_snapshot_json
        ) VALUES (?, ?, ?, ?, 'J1', 'question-v1', 'synthetic-model',
                  NULL, 1, '2026-10-31T12:00:00+00:00', '{}')""",
        (f"evaluation-{claim_id}", claim_id, evidence_version, f"run-{claim_id}"),
    )


def insert_event(connection: sqlite3.Connection, claim_id: str = "claim-1") -> None:
    connection.execute(
        """INSERT INTO claim_events (
            event_id, claim_id, occurred_at, event_kind, evidence_version,
            revision_id, evaluation_id, details_json
        ) VALUES (?, ?, '2026-10-31T12:00:00+00:00', 'SCHEMA_FIXTURE', 1, ?, ?, '{}')""",
        (
            f"event-{claim_id}",
            claim_id,
            f"revision-{claim_id}",
            f"evaluation-{claim_id}",
        ),
    )


def test_initialization_is_explicit_and_creates_expected_schema(
    tmp_path: Path,
) -> None:
    path = tmp_path / "explicit.sqlite3"
    assert not path.exists()
    with connect_database(path) as connection:
        assert connection.execute("SELECT name FROM sqlite_schema").fetchall() == []
    initialize_database(path)

    with connect_database(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone() == (SCHEMA_VERSION,)
        tables = connection.execute(
            "SELECT name, strict FROM pragma_table_list WHERE schema = 'main' "
            "AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
        assert dict(tables) == {
            "claims": 1,
            "claim_revisions": 1,
            "evaluations": 1,
            "claim_events": 1,
        }
        indexes = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_schema WHERE type='index'"
            )
        }
        assert {
            "claims_blocking_identity",
            "revisions_category_date",
            "evaluations_claim_history",
            "events_claim_history",
        } <= indexes
        identity_index = connection.execute("PRAGMA index_list(claims)").fetchall()
        assert any(
            row[1] == "claims_blocking_identity" and row[2:] == (1, "c", 1)
            for row in identity_index
        )
        for table, parents in {
            "claims": {"claim_revisions", "claim_events"},
            "claim_revisions": {"claims"},
            "evaluations": {"claims", "claim_revisions"},
            "claim_events": {"claims", "claim_revisions", "evaluations"},
        }.items():
            assert {
                row[2]
                for row in connection.execute(f"PRAGMA foreign_key_list({table})")
            } == parents
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []


def test_reinitialization_preserves_data_and_schema(database_path: Path) -> None:
    with connect_database(database_path) as connection:
        with write_transaction(connection):
            insert_claim(connection)
        schema_before = connection.execute(
            "SELECT type, name, sql FROM sqlite_schema ORDER BY name"
        ).fetchall()
    initialize_database(database_path)
    with connect_database(database_path) as connection:
        assert connection.execute("SELECT claim_id FROM claims").fetchall() == [
            ("claim-1",)
        ]
        assert (
            connection.execute(
                "SELECT type, name, sql FROM sqlite_schema ORDER BY name"
            ).fetchall()
            == schema_before
        )


@pytest.mark.parametrize("version", [0, 2])
def test_incompatible_databases_are_not_rebuilt(tmp_path: Path, version: int) -> None:
    path = tmp_path / "existing.sqlite3"
    with connect_database(path) as connection:
        connection.execute("CREATE TABLE retained (value TEXT)")
        connection.execute("INSERT INTO retained VALUES ('keep me')")
        if version == 2:
            connection.execute("PRAGMA user_version = 2")
    with pytest.raises(ValueError, match="unversioned|Unsupported.*version"):
        initialize_database(path)
    with connect_database(path) as connection:
        assert connection.execute("SELECT * FROM retained").fetchall() == [("keep me",)]
        assert connection.execute("PRAGMA user_version").fetchone() == (version,)


def test_initialization_failure_rolls_back_ddl_and_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "failed-initialization.sqlite3"
    read_text = Path.read_text

    def schema_with_failure(source: Path, **kwargs: object) -> str:
        schema = read_text(source, **kwargs)
        if source.name == "schema.sql":
            return schema + "\nINSERT INTO missing_table VALUES (1);\n"
        return schema

    with monkeypatch.context() as patch:
        patch.setattr(Path, "read_text", schema_with_failure)
        with pytest.raises(sqlite3.OperationalError, match="missing_table"):
            initialize_database(path)
    with connect_database(path) as connection:
        assert connection.execute("SELECT name FROM sqlite_schema").fetchall() == []
        assert connection.execute("PRAGMA user_version").fetchone() == (0,)
    initialize_database(path)


def test_foreign_keys_enabled_on_each_connection(database_path: Path) -> None:
    with (
        connect_database(database_path) as first,
        connect_database(database_path) as second,
    ):
        for connection in (first, second):
            assert connection.execute("PRAGMA foreign_keys").fetchone() == (1,)
            with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
                insert_revision(connection, "missing")


def test_deferred_pointer_resolves_at_commit_and_preserves_text(
    database_path: Path,
) -> None:
    with connect_database(database_path) as connection:
        with write_transaction(connection):
            insert_claim(
                connection, overrides={"line_number": "9" * 30}, with_revision=False
            )
            # The claim's current revision does not exist until the next statement.
            insert_revision(
                connection, overrides={"invoice_item_amount": "9" * 40 + ".00"}
            )
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert connection.execute(
            "SELECT invoice_line_number FROM claims"
        ).fetchone() == ("9" * 30,)
        assert connection.execute(
            "SELECT raw_evidence_json, invoice_item_amount, invoice_date FROM claim_revisions"
        ).fetchone() == (
            '{"merchant_name":"  Example MERCHANT  "}',
            "9" * 40 + ".00",
            "2026-10-31",
        )


def test_missing_current_revision_fails_at_commit_and_rolls_back(
    database_path: Path,
) -> None:
    with connect_database(database_path) as connection:
        with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
            with write_transaction(connection):
                insert_claim(connection, with_revision=False)
                assert connection.execute("SELECT count(*) FROM claims").fetchone() == (
                    1,
                )
        assert not connection.in_transaction
        assert connection.execute("SELECT count(*) FROM claims").fetchone() == (0,)
        with write_transaction(connection):
            insert_claim(connection)


@pytest.mark.parametrize(
    "reference",
    ["current_evidence", "event_evidence", "revision", "evaluation", "question"],
)
def test_cross_claim_history_references_are_rejected(
    database_path: Path, reference: str
) -> None:
    with connect_database(database_path) as connection:
        with write_transaction(connection):
            for claim_id in ("claim-1", "claim-2"):
                insert_claim(connection, claim_id, {"status": "NEED_INFO"})
                insert_evaluation(connection, claim_id)
                insert_event(connection, claim_id)
            insert_revision(
                connection,
                "claim-2",
                {"revision_id": "revision-2-v2", "evidence_version": 2},
            )
        with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
            with write_transaction(connection):
                if reference == "current_evidence":
                    connection.execute(
                        "UPDATE claims SET current_evidence_version=2 WHERE claim_id='claim-1'"
                    )
                elif reference == "question":
                    connection.execute(
                        "UPDATE claims SET outstanding_question_event_id='event-claim-2' "
                        "WHERE claim_id='claim-1'"
                    )
                else:
                    connection.execute(
                        """INSERT INTO claim_events (
                            event_id, claim_id, occurred_at, event_kind, details_json,
                            evidence_version, revision_id, evaluation_id
                        ) VALUES ('bad-event', 'claim-1', '2026-10-31T12:00:00+00:00',
                                  'SCHEMA_FIXTURE', '{}', ?, ?, ?)""",
                        (
                            2 if reference == "event_evidence" else None,
                            "revision-claim-2" if reference == "revision" else None,
                            "evaluation-claim-2" if reference == "evaluation" else None,
                        ),
                    )
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []


def test_evaluations_must_reference_their_own_accepted_evidence(
    database_path: Path,
) -> None:
    with connect_database(database_path) as connection:
        with write_transaction(connection):
            insert_claim(connection)
            insert_claim(connection, "claim-2")
            insert_revision(
                connection,
                "claim-2",
                {"revision_id": "revision-2-v2", "evidence_version": 2},
            )
        with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
            with write_transaction(connection):
                insert_evaluation(connection, evidence_version=2)


@pytest.mark.parametrize("reference", ["revision", "evaluation", "failed_revision"])
def test_event_rejects_inconsistent_evidence_references(
    database_path: Path, reference: str
) -> None:
    with connect_database(database_path) as connection:
        with write_transaction(connection):
            insert_claim(connection)
            insert_revision(
                connection,
                overrides={"revision_id": "revision-v2", "evidence_version": 2},
            )
            insert_revision(
                connection,
                overrides={
                    "revision_id": "failed-revision",
                    "evidence_version": None,
                    "disposition": "INVALID",
                },
            )
            insert_evaluation(connection)
        # Each identifier independently exists and belongs to this claim.
        with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
            with write_transaction(connection):
                connection.execute(
                    """INSERT INTO claim_events (
                        event_id, claim_id, occurred_at, event_kind, details_json,
                        evidence_version, revision_id, evaluation_id
                    ) VALUES ('inconsistent', 'claim-1', '2026-10-31T12:00:00+00:00',
                              'SCHEMA_FIXTURE', '{}', ?, ?, ?)""",
                    (
                        2 if reference == "evaluation" else 1,
                        "revision-v2"
                        if reference == "revision"
                        else "failed-revision"
                        if reference == "failed_revision"
                        else None,
                        "evaluation-claim-1" if reference == "evaluation" else None,
                    ),
                )
        assert connection.execute("SELECT count(*) FROM claim_events").fetchone() == (
            0,
        )


@pytest.mark.parametrize(
    "evidence_version,revision_id,evaluation_id",
    [
        (1, "revision-claim-1", "evaluation-claim-1"),
        (2, "revision-v2", None),
        (1, None, None),
        (None, "revision-v2", None),
        (None, "failed-revision", None),
        (None, None, "evaluation-claim-1"),
        (1, None, "evaluation-claim-1"),
    ],
)
def test_event_preserves_supported_optional_references(
    database_path: Path,
    evidence_version: int | None,
    revision_id: str | None,
    evaluation_id: str | None,
) -> None:
    with connect_database(database_path) as connection:
        with write_transaction(connection):
            insert_claim(connection)
            insert_revision(
                connection,
                overrides={"revision_id": "revision-v2", "evidence_version": 2},
            )
            insert_revision(
                connection,
                overrides={
                    "revision_id": "failed-revision",
                    "evidence_version": None,
                    "disposition": "INVALID",
                },
            )
            insert_evaluation(connection)
            connection.execute(
                """INSERT INTO claim_events (
                    event_id, claim_id, occurred_at, event_kind, details_json,
                    evidence_version, revision_id, evaluation_id
                ) VALUES ('valid', 'claim-1', '2026-10-31T12:00:00+00:00',
                          'SCHEMA_FIXTURE', '{}', ?, ?, ?)""",
                (evidence_version, revision_id, evaluation_id),
            )
        assert connection.execute(
            "SELECT evidence_version, revision_id, evaluation_id FROM claim_events"
        ).fetchone() == (evidence_version, revision_id, evaluation_id)
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []


def test_event_prevents_rebinding_linked_evaluation(database_path: Path) -> None:
    with connect_database(database_path) as connection:
        with write_transaction(connection):
            insert_claim(connection)
            insert_revision(
                connection,
                overrides={"revision_id": "revision-v2", "evidence_version": 2},
            )
            insert_evaluation(connection)
            insert_event(connection)
        # Even an unfinished evaluation cannot invalidate an existing audit link.
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            with write_transaction(connection):
                connection.execute("UPDATE evaluations SET evidence_version=2")
        assert connection.execute(
            "SELECT evidence_version FROM evaluations"
        ).fetchone() == (1,)


@pytest.mark.parametrize(
    "column,value", [("claim_id", "claim-2"), ("evidence_version", 2)]
)
@pytest.mark.parametrize("operation", ["update", "replace"])
@pytest.mark.parametrize("versionless_event", [False, True])
def test_unfinished_evaluation_association_is_immutable(
    database_path: Path,
    column: str,
    value: object,
    operation: str,
    versionless_event: bool,
) -> None:
    with connect_database(database_path) as connection:
        with write_transaction(connection):
            insert_claim(connection)
            insert_claim(connection, "claim-2")
            insert_revision(
                connection,
                overrides={"revision_id": "revision-v2", "evidence_version": 2},
            )
            insert_evaluation(connection)
            if versionless_event:
                connection.execute("""INSERT INTO claim_events (
                    event_id, claim_id, occurred_at, event_kind, evaluation_id, details_json
                ) VALUES ('versionless', 'claim-1', '2026-10-31T12:00:00+00:00',
                          'SCHEMA_FIXTURE', 'evaluation-claim-1', '{}')""")
        before = connection.execute("SELECT * FROM evaluations").fetchall()
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            with write_transaction(connection):
                if operation == "update":
                    connection.execute(f"UPDATE evaluations SET {column}=?", (value,))
                else:
                    connection.execute(
                        """INSERT OR REPLACE INTO evaluations (
                        evaluation_id, claim_id, evidence_version, evaluation_run_id,
                        question_kind, question_revision, model_version, expected_status,
                        expected_state_version, started_at, input_snapshot_json
                    ) VALUES ('evaluation-claim-1', ?, ?, 'run-claim-1', 'J1',
                        'question-v1', 'synthetic-model', NULL, 1,
                        '2026-10-31T12:00:00+00:00', '{}')""",
                        (
                            value if column == "claim_id" else "claim-1",
                            value if column == "evidence_version" else 1,
                        ),
                    )
        assert connection.execute("SELECT * FROM evaluations").fetchall() == before
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []


@pytest.mark.parametrize("failed", [False, True])
def test_versionless_event_allows_evaluation_completion(
    database_path: Path, failed: bool
) -> None:
    response = None if failed else '{"label":"WELLNESS"}'
    error = '{"reason":"synthetic failure"}' if failed else None
    completed_at = "2026-10-31T12:00:01+00:00"
    with connect_database(database_path) as connection:
        with write_transaction(connection):
            insert_claim(connection)
            insert_evaluation(connection)
            connection.execute("""INSERT INTO claim_events (
                event_id, claim_id, occurred_at, event_kind, evaluation_id, details_json
            ) VALUES ('versionless', 'claim-1', '2026-10-31T12:00:00+00:00',
                      'SCHEMA_FIXTURE', 'evaluation-claim-1', '{}')""")
        with write_transaction(connection):
            connection.execute(
                """UPDATE evaluations SET
                claim_id=claim_id, evidence_version=evidence_version,
                response_json=?, error_json=?, completed_at=?, write_disposition='APPLIED'
            """,
                (response, error, completed_at),
            )
        assert (
            connection.execute("""SELECT claim_id, evidence_version, response_json,
            error_json, completed_at, write_disposition FROM evaluations""").fetchone()
            == ("claim-1", 1, response, error, completed_at, "APPLIED")
        )
        assert connection.execute(
            "SELECT evidence_version FROM claim_events"
        ).fetchone() == (None,)


def test_outstanding_question_can_be_inserted_after_its_pointer(
    database_path: Path,
) -> None:
    with connect_database(database_path) as connection:
        with write_transaction(connection):
            insert_claim(connection, overrides={"status": "NEED_INFO"})
            connection.execute(
                "UPDATE claims SET outstanding_question_event_id='event-claim-1'"
            )
            insert_evaluation(connection)
            insert_event(connection)
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []


@pytest.mark.parametrize("status", [None, "NEED_INFO", "HUMAN_REVIEW", "PROCESSABLE"])
def test_blocking_statuses_exclude_duplicate_identity(
    database_path: Path, status: str | None
) -> None:
    with connect_database(database_path) as connection:
        with write_transaction(connection):
            insert_claim(
                connection, overrides={"status": status, "invoice_number": "same"}
            )
        with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
            with write_transaction(connection):
                insert_claim(connection, "claim-2", {"invoice_number": "same"})
        assert connection.execute("SELECT count(*) FROM claims").fetchone() == (1,)


@pytest.mark.parametrize("released_status", ["POLICY_RESTRICTION", "CANCELLED"])
def test_schema_key_release_and_distinct_invoice_lines(
    database_path: Path, released_status: str
) -> None:
    with connect_database(database_path) as connection:
        with write_transaction(connection):
            insert_claim(connection, overrides={"invoice_number": "same"})
            insert_claim(
                connection, "other-line", {"invoice_number": "same", "line_number": "2"}
            )
            # Direct SQL tests the index predicate, not a cancellation workflow.
            connection.execute(
                "UPDATE claims SET status=? WHERE claim_id='claim-1'",
                (released_status,),
            )
            insert_claim(connection, "new-owner", {"invoice_number": "same"})
        assert connection.execute("SELECT count(*) FROM claims").fetchone() == (3,)


def test_two_connections_serialize_writes_then_enforce_identity(
    database_path: Path,
) -> None:
    with (
        connect_database(database_path) as first,
        connect_database(database_path) as second,
    ):
        second.execute("PRAGMA busy_timeout = 0")
        with write_transaction(first):
            insert_claim(first, overrides={"invoice_number": "same"})
            with pytest.raises(sqlite3.OperationalError, match="locked"):
                with write_transaction(second):
                    pytest.fail(
                        "Second writer must not enter while the first owns the transaction."
                    )
            assert not second.in_transaction
        with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
            with write_transaction(second):
                insert_claim(second, "claim-2", {"invoice_number": "same"})
        assert second.execute("SELECT claim_id FROM claims").fetchall() == [
            ("claim-1",)
        ]


@pytest.mark.parametrize(
    "column",
    [
        "normalized_employee_id",
        "normalized_merchant_name",
        "normalized_invoice_number",
        "invoice_line_number",
    ],
)
def test_identity_columns_cannot_be_null(database_path: Path, column: str) -> None:
    with connect_database(database_path) as connection:
        with write_transaction(connection):
            insert_claim(connection)
        with pytest.raises(sqlite3.IntegrityError, match="NOT NULL"):
            with write_transaction(connection):
                connection.execute(f"UPDATE claims SET {column}=NULL")


@pytest.mark.parametrize("line_number", ["", "0", "01", "-1", "1.0", "1a", " 1"])
def test_invoice_line_text_must_be_canonical(
    database_path: Path, line_number: str
) -> None:
    with connect_database(database_path) as connection:
        with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
            with write_transaction(connection):
                insert_claim(connection, overrides={"line_number": line_number})


@pytest.mark.parametrize(
    "column,value",
    [
        ("status", "PENDING"),
        ("state_version", 0),
        ("uncertain_item_corrections", -1),
        ("uncertain_item_corrections", 2),
        ("reliable_item_corrections", -1),
        ("reliable_item_corrections", 2),
        ("category_corrections", -1),
        ("category_corrections", 3),
        ("semantic_responses", -1),
        ("semantic_responses", 3),
    ],
)
def test_status_and_counter_ranges(
    database_path: Path, column: str, value: object
) -> None:
    with connect_database(database_path) as connection:
        with write_transaction(connection):
            insert_claim(connection, overrides={"status": "NEED_INFO"})
            connection.execute("""UPDATE claims SET uncertain_item_corrections=1,
                reliable_item_corrections=1, category_corrections=2, semantic_responses=2""")
        with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
            with write_transaction(connection):
                connection.execute(f"UPDATE claims SET {column}=?", (value,))


@pytest.mark.parametrize(
    "column,value",
    [
        ("current_evidence_version", 2),
        ("uncertain_item_corrections", 1),
        ("reliable_item_corrections", 1),
        ("category_corrections", 1),
        ("semantic_responses", 1),
        ("outstanding_question_event_id", "question"),
        ("reason_code", "TECHNICAL_FAILURE"),
    ],
)
def test_undecided_invariants_are_sql_checks(
    database_path: Path, column: str, value: object
) -> None:
    with connect_database(database_path) as connection:
        with write_transaction(connection):
            insert_claim(connection)
        with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
            with write_transaction(connection):
                connection.execute(f"UPDATE claims SET {column}=?", (value,))


@pytest.mark.parametrize(
    "overrides",
    [
        {"evidence_version": None},
        {"evidence_version": 0},
        {"disposition": "INVALID", "evidence_version": 2},
        {"invoice_date": None},
        {"reimbursement_category": "OTHER"},
        {"invoice_item_amount": None},
        {"requested_reimbursement": None},
        {"raw_evidence_json": "not JSON"},
        {"validation_details_json": "{"},
    ],
)
def test_revision_constraints(
    database_path: Path, overrides: dict[str, object]
) -> None:
    with connect_database(database_path) as connection:
        with write_transaction(connection):
            insert_claim(connection)
        with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
            with write_transaction(connection):
                insert_revision(
                    connection,
                    overrides={
                        "revision_id": "bad-revision",
                        "evidence_version": 2,
                        **overrides,
                    },
                )


def test_failed_attempts_have_no_accepted_version(database_path: Path) -> None:
    with connect_database(database_path) as connection:
        with write_transaction(connection):
            insert_claim(connection)
            for disposition in (
                "INVALID",
                "DUPLICATE_CONFLICT",
                "ALLOWANCE_FAILURE",
                "STALE",
            ):
                insert_revision(
                    connection,
                    overrides={
                        "revision_id": disposition,
                        "disposition": disposition,
                        "evidence_version": None,
                        "invoice_date": None,
                    },
                )
        assert connection.execute(
            "SELECT current_evidence_version FROM claims"
        ).fetchone() == (1,)
        assert connection.execute(
            "SELECT count(*) FROM claim_revisions WHERE evidence_version IS NULL"
        ).fetchone() == (4,)


@pytest.mark.parametrize(
    "table,column",
    [
        ("evaluations", "input_snapshot_json"),
        ("evaluations", "response_json"),
        ("evaluations", "error_json"),
        ("claim_events", "details_json"),
    ],
)
def test_evaluation_and_event_json_is_checked(
    database_path: Path, table: str, column: str
) -> None:
    with connect_database(database_path) as connection:
        with write_transaction(connection):
            insert_claim(connection)
            insert_evaluation(connection)
            if table == "claim_events":
                # Insert invalid JSON directly because event history is immutable.
                with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
                    connection.execute("""INSERT INTO claim_events (
                        event_id, claim_id, occurred_at, event_kind, details_json
                    ) VALUES ('bad', 'claim-1', '2026-10-31T12:00:00+00:00', 'FIXTURE', '{')""")
            else:
                with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
                    connection.execute(f"UPDATE {table} SET {column}='{{'")


@pytest.mark.parametrize("table", ["claim_revisions", "claim_events"])
@pytest.mark.parametrize("operation", ["update", "delete", "replace"])
def test_history_cannot_be_changed(
    database_path: Path, table: str, operation: str
) -> None:
    with connect_database(database_path) as connection:
        with write_transaction(connection):
            insert_claim(connection)
            insert_evaluation(connection)
            insert_event(connection)
        before = connection.execute(f"SELECT * FROM {table}").fetchall()
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            with write_transaction(connection):
                if operation == "update":
                    connection.execute(f"UPDATE {table} SET claim_id=claim_id")
                elif operation == "delete":
                    connection.execute(f"DELETE FROM {table}")
                else:
                    connection.execute(
                        f"INSERT OR REPLACE INTO {table} SELECT * FROM {table}"
                    )
        assert connection.execute(f"SELECT * FROM {table}").fetchall() == before


def test_accepted_version_cannot_be_replaced_using_a_different_revision_id(
    database_path: Path,
) -> None:
    with connect_database(database_path) as connection:
        with write_transaction(connection):
            insert_claim(connection)
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            with write_transaction(connection):
                connection.execute("""INSERT OR REPLACE INTO claim_revisions
                    SELECT 'replacement', claim_id, evidence_version, submitted_at,
                           action_kind, disposition, raw_evidence_json, invoice_date,
                           reimbursement_category, invoice_item_amount,
                           requested_reimbursement, validation_details_json
                    FROM claim_revisions""")


@pytest.mark.parametrize("operation", ["update", "delete", "replace", "update_replace"])
def test_completed_evaluation_cannot_be_replaced(
    database_path: Path, operation: str
) -> None:
    with connect_database(database_path) as connection:
        with write_transaction(connection):
            insert_claim(connection)
            insert_evaluation(connection)
            connection.execute("""UPDATE evaluations SET response_json='{"label":"WELLNESS"}',
                completed_at='2026-10-31T12:00:01+00:00'""")
            insert_claim(connection, "claim-2")
            insert_evaluation(connection, "claim-2")
        before = connection.execute("SELECT * FROM evaluations").fetchall()
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            with write_transaction(connection):
                if operation == "update":
                    connection.execute("UPDATE evaluations SET response_json='{}'")
                elif operation == "delete":
                    connection.execute("DELETE FROM evaluations")
                elif operation == "update_replace":
                    connection.execute("""UPDATE OR REPLACE evaluations
                        SET evaluation_id='evaluation-claim-1'
                        WHERE evaluation_id='evaluation-claim-2'""")
                else:
                    connection.execute(
                        "INSERT OR REPLACE INTO evaluations SELECT * FROM evaluations"
                    )
        assert connection.execute("SELECT * FROM evaluations").fetchall() == before


def test_constraint_failure_rolls_back_all_rows_and_identity(
    database_path: Path,
) -> None:
    with connect_database(database_path) as connection:
        with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
            with write_transaction(connection):
                insert_claim(connection, overrides={"invoice_number": "same"})
                insert_claim(connection, "claim-2", {"invoice_number": "same"})
        assert connection.execute(
            "SELECT count(*) FROM claim_revisions"
        ).fetchone() == (0,)
        assert connection.execute("SELECT count(*) FROM claims").fetchone() == (0,)
        with write_transaction(connection):
            insert_claim(connection, "claim-3", {"invoice_number": "same"})


def test_nested_transactions_are_rejected_without_ending_the_outer_one(
    database_path: Path,
) -> None:
    with connect_database(database_path) as connection:
        with write_transaction(connection):
            insert_claim(connection)
            with pytest.raises(ValueError, match="nested"):
                with write_transaction(connection):
                    pytest.fail("Nested transactions must not enter.")
            assert connection.in_transaction
        assert not connection.in_transaction


@pytest.mark.parametrize("raise_error", [False, True])
def test_connection_cleanup_and_exception_rollback(
    database_path: Path, raise_error: bool
) -> None:
    connection: sqlite3.Connection
    try:
        with connect_database(database_path) as connection:
            with write_transaction(connection):
                insert_claim(connection)
                if raise_error:
                    raise RuntimeError("fixture interruption")
    except RuntimeError:
        assert raise_error
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        connection.execute("SELECT 1")
    with connect_database(database_path) as reopened:
        assert reopened.execute("SELECT count(*) FROM claims").fetchone() == (
            0 if raise_error else 1,
        )
