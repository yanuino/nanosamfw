# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Yannick Locque (yanuino)

"""Repository layer for firmware management.

This module provides the data access layer for managing firmware files
in the repository database using the repository pattern.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

from .db import connect


@dataclass
class FirmwareRecord:
    """Firmware repository record.

    Represents a firmware entry with all metadata from FUS inform response
    and local file paths.

    Attributes:
        version_code: Firmware version identifier (format: AAA/BBB/CCC/DDD).
        filename: Binary firmware filename from FUS server.
        path: Server model path from FUS inform response.
        size_bytes: File size in bytes.
        logic_value_factory: Logic value for ENC4 decryption key derivation.
        latest_fw_version: Latest firmware version from inform response.
        encrypted_file_path: Absolute path to encrypted (.enc4) file on disk.
        decrypted_file_path: Absolute path to decrypted file, or None if not decrypted.
    """

    version_code: str
    filename: str
    path: str
    size_bytes: int
    logic_value_factory: str
    latest_fw_version: str
    encrypted_file_path: str
    decrypted_file_path: str | None


def upsert_firmware(rec: FirmwareRecord) -> None:
    """Insert or update a firmware record.

    Creates a new firmware record or updates an existing one if a record with
    the same version_code already exists. The operation is performed within
    a transaction.

    Args:
        rec: Firmware record to insert or update.

    Raises:
        Exception: If the database operation fails, the exception is re-raised
            after rolling back the transaction.
    """
    sql = """
    INSERT INTO firmware (version_code, filename, path, size_bytes,
                          logic_value_factory, latest_fw_version,
                          encrypted_file_path, decrypted_file_path)
    VALUES (:version_code, :filename, :path, :size_bytes,
            :logic_value_factory, :latest_fw_version,
            :encrypted_file_path, :decrypted_file_path)
    ON CONFLICT(version_code) DO UPDATE SET
        filename=excluded.filename,
        path=excluded.path,
        size_bytes=excluded.size_bytes,
        logic_value_factory=excluded.logic_value_factory,
        latest_fw_version=excluded.latest_fw_version,
        encrypted_file_path=excluded.encrypted_file_path,
        decrypted_file_path=excluded.decrypted_file_path;
    """
    with connect() as conn:
        conn.execute("BEGIN;")
        try:
            conn.execute(sql, rec.__dict__)
            conn.execute("COMMIT;")
        except Exception:
            conn.execute("ROLLBACK;")
            raise


def find_firmware(version_code: str) -> Optional[FirmwareRecord]:
    """Find a specific firmware record by version code.

    Args:
        version_code: Firmware version identifier to search for.

    Returns:
        FirmwareRecord if found, None otherwise.
    """
    sql = """
    SELECT version_code, filename, path, size_bytes,
           logic_value_factory, latest_fw_version,
           encrypted_file_path, decrypted_file_path
    FROM firmware
    WHERE version_code=?;
    """
    with connect() as conn:
        row = conn.execute(sql, (version_code,)).fetchone()
        if not row:
            return None
        return FirmwareRecord(
            version_code=row[0],
            filename=row[1],
            path=row[2],
            size_bytes=row[3],
            logic_value_factory=row[4],
            latest_fw_version=row[5],
            encrypted_file_path=row[6],
            decrypted_file_path=row[7],
        )


def list_firmware(limit: Optional[int] = None) -> Iterable[FirmwareRecord]:
    """List all firmware records.

    Yields firmware records ordered by creation date (newest first).

    Args:
        limit: Maximum number of records to return, or None for all.

    Yields:
        FirmwareRecord: Each firmware entry in the repository.
    """
    sql = """
    SELECT version_code, filename, path, size_bytes,
           logic_value_factory, latest_fw_version,
           encrypted_file_path, decrypted_file_path
    FROM firmware
    ORDER BY created_at DESC
    """
    if limit:
        sql += f" LIMIT {int(limit)}"
    sql += ";"

    with connect() as conn:
        for row in conn.execute(sql):
            yield FirmwareRecord(
                version_code=row[0],
                filename=row[1],
                path=row[2],
                size_bytes=row[3],
                logic_value_factory=row[4],
                latest_fw_version=row[5],
                encrypted_file_path=row[6],
                decrypted_file_path=row[7],
            )


def update_decrypted_path(version_code: str, decrypted_path: str) -> None:
    """Update the decrypted file path for a firmware record.

    Args:
        version_code: Firmware version identifier.
        decrypted_path: Absolute path to the decrypted file.

    Raises:
        Exception: If the database operation fails.
    """
    sql = """
    UPDATE firmware
    SET decrypted_file_path=?
    WHERE version_code=?;
    """
    with connect() as conn:
        conn.execute("BEGIN;")
        try:
            conn.execute(sql, (decrypted_path, version_code))
            conn.execute("COMMIT;")
        except Exception:
            conn.execute("ROLLBACK;")
            raise


def delete_firmware(version_code: str) -> None:
    """Delete a firmware record by version code.

    Removes the firmware row from the repository. This does not delete any
    files on disk; callers should remove associated files before invoking.

    Args:
        version_code: Firmware version identifier to delete.
    """
    sql = "DELETE FROM firmware WHERE version_code=?;"
    with connect() as conn:
        conn.execute("BEGIN;")
        try:
            conn.execute(sql, (version_code,))
            conn.execute("COMMIT;")
        except Exception:
            conn.execute("ROLLBACK;")
            raise
