"""Evaluation validation foundations and opaque history reads; no write APIs."""

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
