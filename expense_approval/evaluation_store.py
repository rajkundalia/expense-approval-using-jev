"""Guarded evaluation creation and opaque history reads; no result persistence."""

import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone

_QUESTION_KINDS = frozenset({"J1", "J2", "J3", "J4"})
_STATUSES = frozenset(
    {"NEED_INFO", "HUMAN_REVIEW", "POLICY_RESTRICTION", "CANCELLED", "PROCESSABLE"}
)
_FAILURE_CODES = frozenset(
    {
        "TIMEOUT",
        "CONNECTION_ERROR",
        "PROVIDER_ERROR",
        "INVALID_RESPONSE",
        "REMOTE_OUTCOME_UNKNOWN",
    }
)


class EvaluationConflict(ValueError):
    """An evaluation ID already identifies another owner or creation request."""


class EvaluationStateConflict(ValueError):
    """A new evaluation's anchor is stale or its decision role is terminal."""


class MalformedEvaluationRecord(ValueError):
    """Stored metadata or lifecycle data cannot support a safe write/replay."""


def _validate_connection(connection: sqlite3.Connection) -> None:
    if not isinstance(connection, sqlite3.Connection):
        raise TypeError("Connection must be a sqlite3.Connection.")


def _require_write_transaction(connection: sqlite3.Connection) -> None:
    """Check activity only; callers must use connect_database/write_transaction.

    in_transaction cannot establish BEGIN IMMEDIATE or foreign-key enforcement.
    This check never starts, commits or rolls back a transaction.
    """
    _validate_connection(connection)
    if not connection.in_transaction:
        raise ValueError(
            "Evaluation writes require an active caller-owned transaction."
        )


def _validate_required_text(value: str, name: str) -> str:
    """Validate opaque identifiers/metadata without stripping or normalizing them.

    name is an internal field label, never caller-provided evidence.
    """
    if not isinstance(value, str):
        raise TypeError(f"{name} must be text.")
    if not value.strip():
        raise ValueError(f"{name} must be nonblank text.")
    return value


def _validate_positive_version(value: int, name: str) -> int:
    if type(value) is not int:
        raise TypeError(f"{name} must be a built-in integer, not a boolean.")
    if value <= 0:
        raise ValueError(f"{name} must be positive.")
    return value


def _validate_question_kind(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError("Question kind must be text.")
    if value not in _QUESTION_KINDS:
        raise ValueError("Question kind is not supported.")
    return value


def _validate_expected_status(value: str | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError("Expected status must be text or None.")
    if value not in _STATUSES:
        raise ValueError("Expected status is not supported.")
    return value


def _validate_failure_code(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError("Failure code must be text.")
    if value not in _FAILURE_CODES:
        raise ValueError("Failure code is not supported.")
    return value


def _normalize_timestamp(value: datetime, name: str) -> str:
    if not isinstance(value, datetime):
        raise TypeError(f"{name} must be a datetime.")
    try:
        if value.utcoffset() is None:
            raise ValueError
        return value.astimezone(timezone.utc).isoformat(timespec="microseconds")
    except (ValueError, OverflowError):
        raise ValueError(
            f"{name} must be timezone-aware and representable in UTC."
        ) from None


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("JSON object keys must be unique.")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise ValueError("Nonstandard JSON numeric constants are not supported.")


def _validate_json_object(value: str, name: str) -> str:
    """Pure validation; also call _validate_sqlite_json before future persistence.

    Numbers are inspected as tokens, avoiding float overflow and integer digit
    limits. The parsed value is discarded; accepted source text is returned exact.
    No evidence provenance or semantic response validity is established.
    """
    if not isinstance(value, str):
        raise TypeError(f"{name} must be JSON text.")
    try:
        value.encode("utf-8")
        parsed = json.loads(
            value,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_json_constant,
            parse_int=str,
            parse_float=str,
        )
        if not isinstance(parsed, dict):
            raise ValueError
    except (ValueError, UnicodeError, RecursionError):
        raise ValueError(
            f"{name} must be a UTF-8-encodable strict JSON object."
        ) from None
    return value


def _validate_sqlite_json(
    connection: sqlite3.Connection, value: str, name: str
) -> None:
    """Check SQLite compatibility after all pure argument validation has passed.

    value must already have passed _validate_json_object. SQLite/resource errors
    propagate; only a false json_valid result is an argument-domain error.
    """
    _validate_connection(connection)
    with closing(connection.cursor()) as cursor:
        cursor.row_factory = None
        if cursor.execute("SELECT json_valid(?)", (value,)).fetchone()[0] != 1:
            raise ValueError(f"{name} is not compatible with SQLite JSON.")


def _stored_timestamp(value: str) -> str:
    _validate_required_text(value, "Stored timestamp")
    return _normalize_timestamp(datetime.fromisoformat(value), "Stored timestamp")


def _validate_stored_evaluation(row: sqlite3.Row) -> str:
    """Check replay-critical structure, not provenance or current eligibility.

    Return the normalized stored start for instant comparison. Completed schema
    dispositions, including APPLIED, are preserved without role/freshness checks.
    """
    try:
        for field in (
            "evaluation_id",
            "claim_id",
            "evaluation_run_id",
            "question_revision",
            "model_version",
        ):
            _validate_required_text(row[field], "Stored metadata")
        _validate_positive_version(row["evidence_version"], "Stored evidence version")
        _validate_positive_version(
            row["expected_state_version"], "Stored state version"
        )
        _validate_question_kind(row["question_kind"])
        _validate_expected_status(row["expected_status"])
        started = _stored_timestamp(row["started_at"])
        _validate_json_object(row["input_snapshot_json"], "Stored input snapshot")
        response, error = row["response_json"], row["error_json"]
        disposition = row["write_disposition"]
        if row["completed_at"] is None:
            if any(value is not None for value in (response, error, disposition)):
                raise ValueError
        else:
            if _stored_timestamp(row["completed_at"]) < started:
                raise ValueError
            if (response is None) == (error is None):
                raise ValueError
            if response is not None:
                _validate_json_object(response, "Stored response")
            else:
                _validate_json_object(error, "Stored failure")
                failure = json.loads(error)
                if set(failure) != {"code"}:
                    raise ValueError
                _validate_failure_code(failure["code"])
            if disposition is not None and disposition not in (
                "APPLIED",
                "STALE",
                "DIAGNOSTIC",
            ):
                raise ValueError
    except (TypeError, ValueError):
        raise MalformedEvaluationRecord(
            "Stored evaluation metadata or lifecycle is malformed."
        ) from None
    return started


def create_evaluation(
    connection: sqlite3.Connection,
    *,
    evaluation_id: str,
    claim_id: str,
    evidence_version: int,
    evaluation_run_id: str,
    question_kind: str,
    question_revision: str,
    model_version: str,
    expected_status: str | None,
    expected_state_version: int,
    started_at: datetime,
    input_snapshot_json: str,
) -> sqlite3.Row:
    """Capture an unfinished attempt under a current accepted-evidence anchor.

    Use connect_database() within caller-owned write_transaction() (BEGIN
    IMMEDIATE); returns are provisional until commit. Exact creation replay
    precedes current guards, including after completion or claim changes. Reuse
    the original ID, timestamp and exact JSON after a lost acknowledgment.

    Storage does not establish inference eligibility or snapshot provenance.
    New terminal J1/J2 anchors are rejected; J3/J4 storage admits no model call.
    No result, disposition, claim change or event is written. No remote execution
    guarantees, retries, outer transaction control or settings changes are made.
    """
    _require_write_transaction(connection)
    _validate_required_text(evaluation_id, "Evaluation ID")
    _validate_required_text(claim_id, "Claim ID")
    _validate_positive_version(evidence_version, "Evidence version")
    _validate_required_text(evaluation_run_id, "Evaluation run ID")
    _validate_question_kind(question_kind)
    _validate_required_text(question_revision, "Question revision")
    _validate_required_text(model_version, "Model version")
    _validate_expected_status(expected_status)
    _validate_positive_version(expected_state_version, "Expected state version")
    timestamp = _normalize_timestamp(started_at, "Start timestamp")
    _validate_json_object(input_snapshot_json, "Input snapshot")
    _validate_sqlite_json(connection, input_snapshot_json, "Input snapshot")
    metadata = {
        "evaluation_id": evaluation_id,
        "claim_id": claim_id,
        "evidence_version": evidence_version,
        "evaluation_run_id": evaluation_run_id,
        "question_kind": question_kind,
        "question_revision": question_revision,
        "model_version": model_version,
        "expected_status": expected_status,
        "expected_state_version": expected_state_version,
        "started_at": timestamp,
        "input_snapshot_json": input_snapshot_json,
    }
    existing = get_evaluation(connection, evaluation_id)
    if existing is not None:
        if existing["claim_id"] != claim_id:
            raise EvaluationConflict("Evaluation ID belongs to another claim.")
        stored_start = _validate_stored_evaluation(existing)
        if any(
            (stored_start if key == "started_at" else existing[key]) != value
            for key, value in metadata.items()
        ):
            raise EvaluationConflict(
                "Evaluation ID identifies different creation metadata."
            )
        return existing

    with closing(connection.cursor()) as cursor:
        cursor.row_factory = sqlite3.Row
        claim = cursor.execute(
            """SELECT c.status, c.state_version, c.current_evidence_version,
                      r.evidence_version AS accepted_evidence_version
            FROM claims AS c LEFT JOIN claim_revisions AS r
              ON r.claim_id = c.claim_id
             AND r.evidence_version = c.current_evidence_version
             AND r.disposition = 'ACCEPTED'
            WHERE c.claim_id = ?""",
            (claim_id,),
        ).fetchone()
    if claim is None:
        raise LookupError("Claim does not exist.")
    try:
        _validate_expected_status(claim["status"])
        _validate_positive_version(claim["state_version"], "Current state version")
        _validate_positive_version(
            claim["current_evidence_version"], "Current evidence version"
        )
        if claim["accepted_evidence_version"] is None:
            raise ValueError
    except (TypeError, ValueError):
        raise MalformedEvaluationRecord(
            "Current claim/evidence anchor is malformed."
        ) from None
    if (
        claim["current_evidence_version"] != evidence_version
        or claim["status"] != expected_status
        or claim["state_version"] != expected_state_version
    ):
        raise EvaluationStateConflict(
            "Evaluation anchor does not match the current claim."
        )
    if question_kind in ("J1", "J2") and claim["status"] in (
        "POLICY_RESTRICTION",
        "CANCELLED",
        "PROCESSABLE",
    ):
        raise EvaluationStateConflict(
            "Decision evaluations cannot start on a terminal claim."
        )

    connection.execute("SAVEPOINT evaluation_creation")
    try:
        connection.execute(
            """INSERT INTO evaluations (
                evaluation_id, claim_id, evidence_version, evaluation_run_id,
                question_kind, question_revision, model_version, expected_status,
                expected_state_version, started_at, input_snapshot_json,
                completed_at, response_json, error_json, write_disposition
            ) VALUES (
                :evaluation_id, :claim_id, :evidence_version, :evaluation_run_id,
                :question_kind, :question_revision, :model_version, :expected_status,
                :expected_state_version, :started_at, :input_snapshot_json,
                NULL, NULL, NULL, NULL
            )""",
            metadata,
        )
        persisted = get_evaluation(connection, evaluation_id)
        if (
            persisted is None
            or any(persisted[key] != value for key, value in metadata.items())
            or any(
                persisted[key] is not None
                for key in (
                    "completed_at",
                    "response_json",
                    "error_json",
                    "write_disposition",
                )
            )
        ):
            raise RuntimeError(
                "Evaluation insertion did not preserve the unfinished record."
            )
        connection.execute("RELEASE SAVEPOINT evaluation_creation")
    except BaseException:
        if connection.in_transaction:
            connection.execute("ROLLBACK TO SAVEPOINT evaluation_creation")
            connection.execute("RELEASE SAVEPOINT evaluation_creation")
        raise
    return persisted


def get_evaluation(
    connection: sqlite3.Connection, evaluation_id: str
) -> sqlite3.Row | None:
    """Return one stored row unchanged, or None; do not validate stored history.

    Own only a cursor, using its local Row factory. Connection settings and caller
    transactions remain unchanged; closed-connection and SQLite errors propagate.
    """
    _validate_connection(connection)
    _validate_required_text(evaluation_id, "Evaluation ID")
    with closing(connection.cursor()) as cursor:
        cursor.row_factory = sqlite3.Row
        return cursor.execute(
            "SELECT * FROM evaluations WHERE evaluation_id = ?", (evaluation_id,)
        ).fetchone()


def list_claim_evaluations(
    connection: sqlite3.Connection,
    claim_id: str,
    *,
    unfinished_only: bool = False,
) -> list[sqlite3.Row]:
    """Return historical/current rows in stored started_at/evaluation_id order.

    Missing history returns []. Unfinished means completed_at IS NULL, regardless
    of other stored fields. No repair, transaction control or settings changes;
    callers own any shared snapshot needed across separate reads.
    """
    _validate_connection(connection)
    _validate_required_text(claim_id, "Claim ID")
    if type(unfinished_only) is not bool:
        raise TypeError("Unfinished-only flag must be a boolean.")
    query = "SELECT * FROM evaluations WHERE claim_id = ?"
    if unfinished_only:
        query += " AND completed_at IS NULL"
    query += " ORDER BY started_at, evaluation_id"
    with closing(connection.cursor()) as cursor:
        cursor.row_factory = sqlite3.Row
        return cursor.execute(query, (claim_id,)).fetchall()
