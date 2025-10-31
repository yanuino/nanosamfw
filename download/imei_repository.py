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
        imei: Device IMEI number.
        model: Device model identifier.
        csc: Country Specific Code.
        version_code: Firmware version identifier (format: AAA/BBB/CCC/DDD).
        status_fus: FUS query status (ok, error, denied, unauthorized, throttled, unknown).
        status_upgrade: Upgrade operation status (queued, in_progress, ok, failed, skipped, unknown).
        created_at: ISO 8601 UTC timestamp of event creation, or None.
        upgrade_at: ISO 8601 UTC timestamp of upgrade operation, or None.
    """

    id: int | None
    imei: str
    model: str
    csc: str
    version_code: str
    status_fus: str = "unknown"  # ok/error/denied/unauthorized/throttled/unknown
    status_upgrade: str = "unknown"  # queued/in_progress/ok/failed/skipped/unknown
    created_at: str | None = None  # ISO-8601 UTC
    upgrade_at: str | None = None  # ISO-8601 UTC


def add_imei_event(
    *,
    imei: str,
    model: str,
    csc: str,
    version_code: str,
    status_fus: str = "ok",
    status_upgrade: str = "unknown",
    upgrade_at: str | None = None,
) -> int:
    """Insert a new IMEI event record.

    Creates a new IMEI event log entry. No uniqueness constraints are enforced;
    all events are kept for full traceability.

    Args:
        imei: Device IMEI number.
        model: Device model identifier.
        csc: Country Specific Code.
        version_code: Firmware version identifier (format: AAA/BBB/CCC/DDD).
        status_fus: FUS query status. Defaults to "ok".
        status_upgrade: Upgrade operation status. Defaults to "unknown".
        upgrade_at: Optional ISO 8601 UTC timestamp of upgrade operation.

    Returns:
        int: Auto-incremented database ID of the inserted record.
    """
    sql = """
    INSERT INTO imei_log
        (imei, model, csc, version_code, status_fus, status_upgrade, created_at, upgrade_at)
    VALUES
        (:imei, :model, :csc, :version_code, :status_fus, :status_upgrade, :created_at, :upgrade_at);
    """
    params = {
        "imei": imei,
        "model": model,
        "csc": csc,
        "version_code": version_code,
        "status_fus": status_fus,
        "status_upgrade": status_upgrade,
        "created_at": _iso_now(),
        "upgrade_at": upgrade_at,
    }
    with connect() as conn:
        cur = conn.execute(sql, params)
        return int(cur.lastrowid)  # type: ignore


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
                imei=row["imei"],
                model=row["model"],
                csc=row["csc"],
                version_code=row["version_code"],
                status_fus=row["status_fus"],
                status_upgrade=row["status_upgrade"],
                created_at=row["created_at"],
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
                imei=row["imei"],
                model=row["model"],
                csc=row["csc"],
                version_code=row["version_code"],
                status_fus=row["status_fus"],
                status_upgrade=row["status_upgrade"],
                created_at=row["created_at"],
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
                imei=row["imei"],
                model=row["model"],
                csc=row["csc"],
                version_code=row["version_code"],
                status_fus=row["status_fus"],
                status_upgrade=row["status_upgrade"],
                created_at=row["created_at"],
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
            imei=row["imei"],
            model=row["model"],
            csc=row["csc"],
            version_code=row["version_code"],
            status_fus=row["status_fus"],
            status_upgrade=row["status_upgrade"],
            created_at=row["created_at"],
            upgrade_at=row["upgrade_at"],
        )
