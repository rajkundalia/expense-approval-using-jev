"""Explicit SQLite connections and schema initialization; no claim workflows."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

SCHEMA_VERSION = 1


@contextmanager
def connect_database(database_path: str | Path) -> Iterator[sqlite3.Connection]:
    """Open a connection with foreign keys enabled, then always close it.

    SQL transactions are explicit. Opening a path can create an empty file;
    creating the application tables requires initialize_database().
    """
    connection = sqlite3.connect(
        database_path,
        isolation_level=None,
        autocommit=sqlite3.LEGACY_TRANSACTION_CONTROL,
    )
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        if connection.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
            raise RuntimeError("SQLite foreign-key enforcement is unavailable.")
        yield connection
    finally:
        connection.close()


@contextmanager
def write_transaction(connection: sqlite3.Connection) -> Iterator[None]:
    """Own one short BEGIN IMMEDIATE transaction, including commit-time failures.

    Nested transactions are rejected. Any exception, including a deferred
    foreign-key failure at COMMIT, rolls back before propagating to the caller.
    Keep remote calls outside this context.
    """
    if connection.in_transaction:
        raise ValueError("A write transaction must not be nested.")
    connection.execute("BEGIN IMMEDIATE")
    try:
        yield
        connection.execute("COMMIT")
    except BaseException:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise


def initialize_database(database_path: str | Path) -> None:
    """Create schema version 1 in an empty database, or leave version 1 intact.

    Reject unknown versions and unversioned databases containing application
    objects. No migrations or destructive rebuilding are performed.
    """
    with connect_database(database_path) as connection:
        with write_transaction(connection):
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            if version == SCHEMA_VERSION:
                return
            if version != 0:
                raise ValueError(f"Unsupported database schema version: {version}.")
            existing_object = connection.execute(
                "SELECT name FROM sqlite_schema WHERE name NOT LIKE 'sqlite_%' LIMIT 1"
            ).fetchone()
            if existing_object is not None:
                raise ValueError("Cannot initialize a nonempty unversioned database.")

            # executescript() can commit a pending transaction. Execute complete
            # statements individually so DDL and version assignment stay atomic.
            statement = ""
            schema = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
            for line in schema.splitlines(keepends=True):
                statement += line
                if sqlite3.complete_statement(statement):
                    connection.execute(statement)
                    statement = ""
            if statement.strip():
                raise ValueError(
                    "The database schema contains an incomplete statement."
                )
            connection.execute("PRAGMA user_version = 1")
