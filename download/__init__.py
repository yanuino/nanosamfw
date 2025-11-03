# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Vladislav Tislenko (keklick1337)
# Copyright (c) 2025 Yannick Locque (yanuino)

"""Firmware download service with database tracking.

This package provides high-level firmware download functionality with automatic
database tracking, resume support, and optional decryption. It orchestrates the
complete download workflow from version resolution through decryption and
persistence.

Main Components:
    - download_firmware: High-level API for complete firmware download workflow
    - DownloadRecord: Database model for firmware download metadata
    - Database utilities: SQLite initialization, health checks, and repair
    - Repository layer: Clean data access patterns for downloads and IMEI logs

Features:
    - Automatic version resolution from Samsung FOTA servers
    - HTTP Range support for resuming interrupted downloads
    - Optional automatic decryption of ENC4 encrypted firmware
    - SQLite database tracking of all downloads
    - Progress callback support for UI integration
    - Organized storage by model and CSC

Example:
    Simple one-line firmware download::

        from download import download_firmware

        record = download_firmware(
            model="SM-G998B",
            csc="EUX",
            device_id="352976245060954",
            decrypt=True,
            resume=True
        )
        print(f"Downloaded to: {record.path}")
        print(f"Version: {record.version_code}")

    Query download history::

        from download import list_downloads, find_download

        # List all downloads for a model/CSC
        for rec in list_downloads(model="SM-G998B", csc="EUX"):
            print(f"{rec.version_code}: {rec.status}")

        # Find specific version
        rec = find_download("SM-G998B", "EUX", "A146PXXS6CXK3/...")
        if rec:
            print(f"Found at: {rec.path}")

    Database management::

        from download import init_db, is_healthy, repair_db

        # Initialize schema
        init_db()

        # Check health and repair if needed
        if not is_healthy():
            repair_db()
"""

from .db import get_db_path, init_db, is_healthy, repair_db
from .repository import DownloadRecord, find_download, list_downloads
from .service import download_firmware
