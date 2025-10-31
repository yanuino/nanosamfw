# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Vladislav Tislenko (keklick1337)
# Copyright (c) 2025 Yannick Locque (yanuino)

"""Repository layer for firmware download operations.

This module provides the data access layer for managing firmware download
records in the database using the repository pattern.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

from .db import connect


@dataclass
class DownloadRecord:
    """Firmware download record.

    Represents a firmware download entry with all associated metadata.

    Attributes:
        model: Device model identifier (e.g., SM-G998B).
        csc: Country Specific Code.
        version_code: Firmware version identifier (format: AAA/BBB/CCC/DDD).
        encoded_filename: Encoded filename from the FUS service.
        size_bytes: File size in bytes, or None if unknown.
        status: Download status (e.g., 'done', 'downloading', 'decrypting', 'error').
        path: Absolute filesystem path to the downloaded file, or None if not yet downloaded.
    """

    model: str
    csc: str
    version_code: str
    encoded_filename: str
    size_bytes: int | None
    status: str
    path: str | None


def upsert_download(rec: DownloadRecord) -> None:
    """Insert or update a firmware download record.

    Creates a new download record or updates an existing one if a record with
    the same model, csc, and version_code already exists. The operation is
    performed within a transaction.

    Args:
        rec: Download record to insert or update.

    Raises:
        Exception: If the database operation fails, the exception is re-raised
            after rolling back the transaction.
    """
    sql = """
    INSERT INTO downloads (model, csc, version_code,
                           encoded_filename, size_bytes, status, path)
    VALUES (:model, :csc, :version_code,
            :encoded_filename, :size_bytes, :status, :path)
    ON CONFLICT(model, csc, version_code) DO UPDATE SET
        encoded_filename=excluded.encoded_filename,
        size_bytes=excluded.size_bytes,
        status=excluded.status,
        path=excluded.path;
    """
    with connect() as conn:
        conn.execute("BEGIN;")
        try:
            conn.execute(sql, rec.__dict__)
            conn.execute("COMMIT;")
        except Exception:
            conn.execute("ROLLBACK;")
            raise


def find_download(model: str, csc: str, version_code: str) -> Optional[DownloadRecord]:
    """Find a specific firmware download record.

    Searches for a download record matching the provided model, CSC, and version code.

    Args:
        model: Device model identifier to search for.
        csc: Country Specific Code to search for.
        version_code: Firmware version identifier to search for.

    Returns:
        DownloadRecord if found, None otherwise.
    """
    sql = """
    SELECT * FROM downloads
    WHERE model=? AND csc=? AND version_code=?;
    """
    with connect() as conn:
        row = conn.execute(sql, (model, csc, version_code)).fetchone()
        if not row:
            return None
        return DownloadRecord(
            model=row["model"],
            csc=row["csc"],
            version_code=row["version_code"],
            encoded_filename=row["encoded_filename"],
            size_bytes=row["size_bytes"],
            status=row["status"],
            path=row["path"],
        )


def list_downloads(model: str | None = None, csc: str | None = None) -> Iterable[DownloadRecord]:
    """List firmware download records with optional filtering.

    Retrieves download records from the database, optionally filtered by model
    and/or CSC. Results are ordered by creation date (newest first).

    Args:
        model: Optional device model to filter by. If None, all models are included.
        csc: Optional Country Specific Code to filter by. If None, all CSCs are included.

    Yields:
        DownloadRecord: Download records matching the filter criteria, ordered by
            creation date in descending order.
    """
    base = "SELECT * FROM downloads"
    params: list[str] = []
    where = []
    if model:
        where.append("model=?")
        params.append(model)
    if csc:
        where.append("csc=?")
        params.append(csc)
    if where:
        base += " WHERE " + " AND ".join(where)
    base += " ORDER BY created_at DESC;"
    with connect() as conn:
        for row in conn.execute(base, params):
            yield DownloadRecord(
                model=row["model"],
                csc=row["csc"],
                version_code=row["version_code"],
                encoded_filename=row["encoded_filename"],
                size_bytes=row["size_bytes"],
                status=row["status"],
                path=row["path"],
            )
