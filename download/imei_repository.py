# SPDX-License-Identifier: MIT
# Copyright (c) 2025 ...

"""Repository layer for IMEI event logging.

This module provides data access functions for tracking IMEI-based firmware
queries and upgrade operations. Events are logged with FUS status and upgrade
status for traceability.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Optional

from .db import connect

ISO_UTC = "%Y-%m-%dT%H:%M:%SZ"


def _iso_now() -> str:
    """Get current UTC time as ISO 8601 formatted string.

    Returns:
        str: Current UTC timestamp in ISO 8601 format (YYYY-MM-DDTHH:MM:SSZ).
    """
    return datetime.now(timezone.utc).strftime(ISO_UTC)


@dataclass
class IMEIEvent:
    """IMEI event record.

    Represents a logged IMEI-based firmware query or upgrade operation.

    Attributes:
        id: Database record ID, or None for new records.
        session_id: Application session identifier (changes per app launch).
        imei: Device IMEI number.
        model: Device model identifier.
        csc: Country Specific Code.
        aid: Application ID, or None.
        cc: Country Code, or None.
        version_code: Actual device firmware version (PDA/CSC/MODEM/BOOTLOADER format from AT).
        fota_version: FOTA/FUS firmware version (AAA/BBB/CCC/DDD format), or None.
        serial_number: Device serial number (SN from AT), or None.
        lock_status: Device lock status (LOCK from AT), or None.
        status_fus: FUS query status (ok, error, denied, unauthorized, throttled, unknown).
        status_upgrade: Upgrade operation status (queued, in_progress, ok, failed, skipped, unknown).
        created_at: ISO 8601 UTC timestamp of event creation, or None.
        updated_at: ISO 8601 UTC timestamp of last update, or None.
        upgrade_at: ISO 8601 UTC timestamp of upgrade operation, or None.
    """

    id: int | None
    session_id: str
    imei: str
    model: str
    csc: str
    version_code: str
    fota_version: str | None = None
    serial_number: str | None = None
    lock_status: str | None = None
    aid: str | None = None
    cc: str | None = None
    status_fus: str = "unknown"  # ok/error/denied/unauthorized/throttled/unknown
    status_upgrade: str = "unknown"  # queued/in_progress/ok/failed/skipped/unknown
    created_at: str | None = None  # ISO-8601 UTC
    updated_at: str | None = None  # ISO-8601 UTC
    upgrade_at: str | None = None  # ISO-8601 UTC


def upsert_imei_event(
    *,
    session_id: str,
    imei: str,
    model: str,
    csc: str,
    version_code: str,
    fota_version: str | None = None,
    serial_number: str | None = None,
    lock_status: str | None = None,
    aid: str | None = None,
    cc: str | None = None,
    status_fus: str = "unknown",
    status_upgrade: str = "unknown",
    upgrade_at: str | None = None,
) -> int:
    """Insert or update IMEI event record for current session.

    Creates a new IMEI event log entry, or updates the existing one if a record
    with the same session_id and imei already exists. This ensures one record
    per device per application session.

    Args:
        session_id: Application session identifier (generated at app launch).
        imei: Device IMEI number.
        model: Device model identifier.
        csc: Country Specific Code.
        aid: Optional Application ID.
        cc: Optional Country Code.
        version_code: Actual device firmware version (PDA/CSC/MODEM/BOOTLOADER format).
        fota_version: Optional FOTA/FUS firmware version (AAA/BBB/CCC/DDD format).
        serial_number: Optional device serial number (SN from AT).
        lock_status: Optional device lock status (LOCK from AT).
        status_fus: FUS query status. Defaults to "unknown".
        status_upgrade: Upgrade operation status. Defaults to "unknown".
        upgrade_at: Optional ISO 8601 UTC timestamp of upgrade operation.

    Returns:
        int: Database ID of the inserted or updated record.
    """
    sql = """
    INSERT INTO imei_log
        (session_id, imei, model, csc, version_code, fota_version, serial_number, lock_status, aid, cc,
         status_fus, status_upgrade, created_at, updated_at, upgrade_at)
    VALUES
        (:session_id, :imei, :model, :csc, :version_code, :fota_version, :serial_number, :lock_status, :aid, :cc,
         :status_fus, :status_upgrade, :created_at, :updated_at, :upgrade_at)
    ON CONFLICT(session_id, imei) DO UPDATE SET
        model=excluded.model,
        csc=excluded.csc,
        version_code=excluded.version_code,
        fota_version=excluded.fota_version,
        serial_number=excluded.serial_number,
        lock_status=excluded.lock_status,
        aid=excluded.aid,
        cc=excluded.cc,
        status_fus=excluded.status_fus,
        status_upgrade=excluded.status_upgrade,
        updated_at=excluded.updated_at,
        upgrade_at=excluded.upgrade_at;
    """
    now = _iso_now()
    params = {
        "session_id": session_id,
        "imei": imei,
        "model": model,
        "csc": csc,
        "version_code": version_code,
        "fota_version": fota_version,
        "serial_number": serial_number,
        "lock_status": lock_status,
        "aid": aid,
        "cc": cc,
        "status_fus": status_fus,
        "status_upgrade": status_upgrade,
        "created_at": now,
        "updated_at": now,
        "upgrade_at": upgrade_at,
    }
    with connect() as conn:
        cur = conn.execute(sql, params)
        return int(cur.lastrowid)  # type: ignore


# Backward compatibility alias (deprecated - use upsert_imei_event with session_id)
def add_imei_event(
    *,
    imei: str,
    model: str,
    csc: str,
    version_code: str,
    fota_version: str | None = None,
    serial_number: str | None = None,
    lock_status: str | None = None,
    aid: str | None = None,
    cc: str | None = None,
    status_fus: str = "unknown",
    status_upgrade: str = "unknown",
    upgrade_at: str | None = None,
    session_id: str = "legacy",
) -> int:
    """Legacy function - use upsert_imei_event instead.

    Kept for backward compatibility. New code should use upsert_imei_event.
    """
    return upsert_imei_event(
        session_id=session_id,
        imei=imei,
        model=model,
        csc=csc,
        version_code=version_code,
        fota_version=fota_version,
        serial_number=serial_number,
        lock_status=lock_status,
        status_fus=status_fus,
        status_upgrade=status_upgrade,
        upgrade_at=upgrade_at,
        aid=aid,
        cc=cc,
    )


def set_upgrade_status(id_: int, status_upgrade: str, upgrade_at: Optional[str] = None) -> None:
    """Update the upgrade status for an existing event.

    Updates the upgrade status and timestamp for a previously logged IMEI event.

    Args:
        id_: Database ID of the event to update.
        status_upgrade: New upgrade status (e.g., ok, failed, skipped).
        upgrade_at: Optional ISO 8601 UTC timestamp. If None, current time is used.
    """
    if upgrade_at is None:
        upgrade_at = _iso_now()
    sql = """
    UPDATE imei_log
       SET status_upgrade = :status_upgrade,
           upgrade_at = :upgrade_at
     WHERE id = :id
    """
    with connect() as conn:
        conn.execute(sql, {"status_upgrade": status_upgrade, "upgrade_at": upgrade_at, "id": id_})


def list_by_imei(imei: str, *, limit: int = 200, offset: int = 0) -> Iterable[IMEIEvent]:
    """List IMEI events for a specific IMEI number.

    Retrieves event records for a given IMEI, ordered by creation date (newest first).

    Args:
        imei: Device IMEI number to search for.
        limit: Maximum number of records to return. Defaults to 200.
        offset: Number of records to skip for pagination. Defaults to 0.

    Yields:
        IMEIEvent: Event records matching the IMEI, ordered by created_at descending.
    """
    sql = """
    SELECT * FROM imei_log
     WHERE imei = ?
     ORDER BY created_at DESC
     LIMIT ? OFFSET ?;
    """
    with connect() as conn:
        for row in conn.execute(sql, (imei, limit, offset)):
            yield IMEIEvent(
                id=row["id"],
                session_id=row["session_id"],
                imei=row["imei"],
                model=row["model"],
                csc=row["csc"],
                version_code=row["version_code"],
                fota_version=row.get("fota_version"),
                serial_number=row.get("serial_number"),
                lock_status=row.get("lock_status"),
                aid=row.get("aid"),
                cc=row.get("cc"),
                status_fus=row["status_fus"],
                status_upgrade=row["status_upgrade"],
                created_at=row["created_at"],
                updated_at=row.get("updated_at", row["created_at"]),
                upgrade_at=row["upgrade_at"],
            )


def list_by_model_csc(
    model: str,
    csc: str,
    *,
    since: str | None = None,
    until: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> Iterable[IMEIEvent]:
    """List IMEI events for a specific model and CSC combination.

    Retrieves event records filtered by model and CSC, with optional date range
    filtering. Results are ordered by creation date (newest first).

    Args:
        model: Device model identifier.
        csc: Country Specific Code.
        since: Optional ISO 8601 UTC timestamp for minimum created_at filter.
        until: Optional ISO 8601 UTC timestamp for maximum created_at filter.
        limit: Maximum number of records to return. Defaults to 200.
        offset: Number of records to skip for pagination. Defaults to 0.

    Yields:
        IMEIEvent: Event records matching the filters, ordered by created_at descending.
    """
    sql = """
    SELECT * FROM imei_log
     WHERE model = :model AND csc = :csc
       AND (:since IS NULL OR created_at >= :since)
       AND (:until IS NULL OR created_at <= :until)
     ORDER BY created_at DESC
     LIMIT :limit OFFSET :offset;
    """
    with connect() as conn:
        for row in conn.execute(
            sql,
            {
                "model": model,
                "csc": csc,
                "since": since,
                "until": until,
                "limit": limit,
                "offset": offset,
            },
        ):
            yield IMEIEvent(
                id=row["id"],
                session_id=row["session_id"],
                imei=row["imei"],
                model=row["model"],
                csc=row["csc"],
                version_code=row["version_code"],
                fota_version=row.get("fota_version"),
                serial_number=row.get("serial_number"),
                lock_status=row.get("lock_status"),
                aid=row.get("aid"),
                cc=row.get("cc"),
                status_fus=row["status_fus"],
                status_upgrade=row["status_upgrade"],
                created_at=row["created_at"],
                updated_at=row.get("updated_at", row["created_at"]),
                upgrade_at=row["upgrade_at"],
            )


def list_between_dates(
    *,
    created_since: str | None = None,
    created_until: str | None = None,
    upgrade_since: str | None = None,
    upgrade_until: str | None = None,
    limit: int = 500,
    offset: int = 0,
) -> Iterable[IMEIEvent]:
    """List IMEI events filtered by creation and/or upgrade date ranges.

    Retrieves event records with flexible date range filtering on both creation
    and upgrade timestamps. All filters are optional and can be combined.

    Args:
        created_since: Optional ISO 8601 UTC timestamp for minimum created_at filter.
        created_until: Optional ISO 8601 UTC timestamp for maximum created_at filter.
        upgrade_since: Optional ISO 8601 UTC timestamp for minimum upgrade_at filter.
        upgrade_until: Optional ISO 8601 UTC timestamp for maximum upgrade_at filter.
        limit: Maximum number of records to return. Defaults to 500.
        offset: Number of records to skip for pagination. Defaults to 0.

    Yields:
        IMEIEvent: Event records matching the date filters, ordered by created_at descending.

    Note:
        Upgrade date filters only match records where upgrade_at is not NULL.
    """
    sql = """
    SELECT * FROM imei_log
     WHERE (:cs IS NULL OR created_at >= :cs)
       AND (:cu IS NULL OR created_at <= :cu)
       AND (:us IS NULL OR (upgrade_at IS NOT NULL AND upgrade_at >= :us))
       AND (:uu IS NULL OR (upgrade_at IS NOT NULL AND upgrade_at <= :uu))
     ORDER BY created_at DESC
     LIMIT :limit OFFSET :offset;
    """
    params = {
        "cs": created_since,
        "cu": created_until,
        "us": upgrade_since,
        "uu": upgrade_until,
        "limit": limit,
        "offset": offset,
    }
    with connect() as conn:
        for row in conn.execute(sql, params):
            yield IMEIEvent(
                id=row["id"],
                session_id=row["session_id"],
                imei=row["imei"],
                model=row["model"],
                csc=row["csc"],
                version_code=row["version_code"],
                fota_version=row.get("fota_version"),
                serial_number=row.get("serial_number"),
                lock_status=row.get("lock_status"),
                aid=row.get("aid"),
                cc=row.get("cc"),
                status_fus=row["status_fus"],
                status_upgrade=row["status_upgrade"],
                created_at=row["created_at"],
                updated_at=row.get("updated_at", row["created_at"]),
                upgrade_at=row["upgrade_at"],
            )


def last_status_by_imei(imei: str) -> IMEIEvent | None:
    """Get the most recent IMEI event for a specific IMEI number.

    Retrieves the latest event record (by creation date) for the given IMEI.

    Args:
        imei: Device IMEI number to search for.

    Returns:
        IMEIEvent if found, None if no events exist for this IMEI.
    """
    sql = """
    SELECT * FROM imei_log
     WHERE imei = ?
     ORDER BY created_at DESC
     LIMIT 1;
    """
    with connect() as conn:
        row = conn.execute(sql, (imei,)).fetchone()
        if not row:
            return None
        return IMEIEvent(
            id=row["id"],
            session_id=row["session_id"],
            imei=row["imei"],
            model=row["model"],
            csc=row["csc"],
            version_code=row["version_code"],
            fota_version=row.get("fota_version"),
            serial_number=row.get("serial_number"),
            lock_status=row.get("lock_status"),
            aid=row.get("aid"),
            cc=row.get("cc"),
            status_fus=row["status_fus"],
            status_upgrade=row["status_upgrade"],
            created_at=row["created_at"],
            updated_at=row.get("updated_at", row["created_at"]),
            upgrade_at=row["upgrade_at"],
        )
