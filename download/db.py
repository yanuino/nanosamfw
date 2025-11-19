# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Vladislav Tislenko (keklick1337)
# Copyright (c) 2025 Yannick Locque (yanuino)

"""Database connection and schema management.

This module provides database connection utilities, schema initialization,
and database health/repair operations for the firmware download system.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .config import PATHS
from .sql import FIRMWARE_SCHEMA, IMEI_LOG_SCHEMA


# --- Accès chemins --- #
def get_db_path() -> Path:
    """Get the path to the SQLite database file.

    Returns:
        Path: Absolute path to the database file.
    """
    return PATHS.db_path


# --- Connexion --- #
def connect() -> sqlite3.Connection:
    """Open a SQLite connection with optimized PRAGMAs.

    Creates the data directory if it doesn't exist and establishes a database
    connection with WAL mode, reasonable timeouts, and other performance settings.
    One connection per thread/process is recommended.

    Returns:
        sqlite3.Connection: Configured database connection with Row factory enabled.

    Note:
        The connection uses autocommit mode (isolation_level=None), so transactions
        must be managed explicitly with BEGIN/COMMIT/ROLLBACK.
    """
    PATHS.data_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(
        PATHS.db_path,
        timeout=10.0,
        isolation_level=None,
        check_same_thread=False,
    )
    conn.row_factory = sqlite3.Row
    _apply_pragmas(conn)
    return conn


def _apply_pragmas(conn: sqlite3.Connection) -> None:
    """Apply performance and safety PRAGMAs to database connection.

    Args:
        conn: SQLite database connection to configure.
    """
    cur = conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL;")
    cur.execute("PRAGMA synchronous=NORMAL;")
    cur.execute("PRAGMA foreign_keys=ON;")
    cur.execute("PRAGMA busy_timeout=5000;")
    cur.close()


SCHEMA_SQL = FIRMWARE_SCHEMA + "\n\n" + IMEI_LOG_SCHEMA


def init_db() -> None:
    """Initialize the database schema.

    Creates the data directory and database tables if they don't exist.
    Note: executescript() implicitly commits, so no manual transaction control needed.

    Raises:
        Exception: If schema creation fails
    """
    PATHS.data_dir.mkdir(parents=True, exist_ok=True)
    with connect() as conn:
        conn.executescript(SCHEMA_SQL)


# --- Repair --- #
def is_healthy() -> bool:
    """Check database integrity.

    Runs SQLite's integrity_check pragma to verify the database is not corrupted.

    Returns:
        bool: True if database passes integrity check, False otherwise.
    """
    try:
        with sqlite3.connect(PATHS.db_path) as conn:
            cur = conn.cursor()
            cur.execute("PRAGMA integrity_check(1);")
            row = cur.fetchone()
            cur.close()
            return row is not None and row[0] == "ok"
    except sqlite3.DatabaseError:
        return False


def _dump_db(path: Path) -> None:
    """Dump the SQLite database to a SQL file.

    Args:
        path: Path where the SQL dump file will be written.
    """
    PATHS.data_dir.mkdir(parents=True, exist_ok=True)
    with connect() as conn, open(path, "w", encoding="utf-8") as f:
        for line in conn.iterdump():
            f.write(f"{line}\n")


def _restore_db(path: Path) -> None:
    """Restore the SQLite database from a SQL dump file.

    Args:
        path: Path to the SQL dump file to restore from.

    Raises:
        Exception: If restoration fails, the exception is re-raised after rollback.
    """
    PATHS.data_dir.mkdir(parents=True, exist_ok=True)
    with connect() as conn, open(path, "r", encoding="utf-8") as f:
        sql = f.read()
        conn.execute("BEGIN;")
        try:
            conn.executescript(sql)
            conn.execute("COMMIT;")
        except Exception:
            conn.execute("ROLLBACK;")
            raise


def repair_db() -> None:
    """Attempt to repair a corrupted SQLite database.

    If the database fails the integrity check, this function performs a dump
    to a temporary SQL file, deletes the corrupted database, and restores
    from the dump into a new database file.

    The process:
        1. Check if database is healthy (returns immediately if healthy)
        2. Dump database to temporary SQL file
        3. Delete the corrupted database file
        4. Restore from the SQL dump
        5. Clean up temporary dump file
    """
    if is_healthy():
        return

    PATHS.data_dir.mkdir(parents=True, exist_ok=True)
    temp_dump_path = PATHS.data_dir / "temp_dump.sql"
    _dump_db(temp_dump_path)

    try:
        PATHS.db_path.unlink()
    except FileNotFoundError:
        pass

    _restore_db(temp_dump_path)

    try:
        temp_dump_path.unlink()
    except FileNotFoundError:
        pass
