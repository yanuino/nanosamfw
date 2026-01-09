# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Yannick Locque (yanuino)

"""Repository layer for firmware management.

This module provides the data access layer for managing firmware files
in the repository database using the repository pattern.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from .config import PATHS
from .db import connect


@dataclass
class FirmwareRecord:
    """Firmware repository record.

    Represents a firmware entry with all metadata from FUS inform response
    and download/decryption status.

    Attributes:
        version_code: Firmware version identifier (format: AAA/BBB/CCC/DDD).
        filename: Binary firmware filename from FUS server.
        path: Server model path from FUS inform response.
        size_bytes: File size in bytes.
        logic_value_factory: Logic value for ENC4 decryption key derivation.
        latest_fw_version: Latest firmware version from inform response.
        downloaded: Whether the encrypted file has been successfully downloaded.
        decrypted: Whether the firmware has been successfully decrypted.
        extracted: Whether the firmware has been successfully extracted.
    """

    version_code: str
    filename: str
    path: str
    size_bytes: int
    logic_value_factory: str
    latest_fw_version: str
    downloaded: int  # 0 or 1 (SQLite boolean)
    decrypted: int  # 0 or 1 (SQLite boolean)
    extracted: int  # 0 or 1 (SQLite boolean)

    @property
    def encrypted_file_path(self) -> Path:
        """Get the encrypted file path constructed from filename and data directory.

        Returns:
            Path: Absolute path to encrypted (.enc4) file.
        """
        return PATHS.firmware_dir / self.filename

    @property
    def decrypted_file_path(self) -> Path:
        """Get the decrypted file path constructed from filename and data directory.

        Returns:
            Path: Absolute path to decrypted file (without .enc4 extension).
        """
        return PATHS.decrypted_dir / self.filename.replace('.enc4', '')


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
                          downloaded, decrypted, extracted)
    VALUES (:version_code, :filename, :path, :size_bytes,
            :logic_value_factory, :latest_fw_version,
            :downloaded, :decrypted, :extracted)
    ON CONFLICT(version_code) DO UPDATE SET
        filename=excluded.filename,
        path=excluded.path,
        size_bytes=excluded.size_bytes,
        logic_value_factory=excluded.logic_value_factory,
        latest_fw_version=excluded.latest_fw_version,
        downloaded=excluded.downloaded,
        decrypted=excluded.decrypted,
        extracted=excluded.extracted;
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
           downloaded, decrypted, extracted
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
            downloaded=row[6],
            decrypted=row[7],
            extracted=row[8],
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
           downloaded, decrypted, extracted
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
                downloaded=row[6],
                decrypted=row[7],
                extracted=row[8],
            )


def update_firmware_status(
    version_code: str,
    *,
    downloaded: Optional[int] = None,
    decrypted: Optional[int] = None,
    extracted: Optional[int] = None,
) -> None:
    """Update the status flags for a firmware record.

    Updates one or more status flags (downloaded, decrypted, extracted) for a
    firmware record. The operation is performed within a transaction.

    Args:
        version_code: Firmware version identifier.
        downloaded: Set to 0 or 1 to update downloaded status, or None to skip.
        decrypted: Set to 0 or 1 to update decrypted status, or None to skip.
        extracted: Set to 0 or 1 to update extracted status, or None to skip.

    Raises:
        ValueError: If all status parameters are None.
        Exception: If the database operation fails.
    """
    updates = []
    params: list = []

    if downloaded is not None:
        updates.append("downloaded=?")
        params.append(downloaded)
    if decrypted is not None:
        updates.append("decrypted=?")
        params.append(decrypted)
    if extracted is not None:
        updates.append("extracted=?")
        params.append(extracted)

    if not updates:
        raise ValueError("At least one status parameter must be provided")

    params.append(version_code)
    sql = f"UPDATE firmware SET {', '.join(updates)} WHERE version_code=?;"

    with connect() as conn:
        conn.execute("BEGIN;")
        try:
            conn.execute(sql, params)
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
