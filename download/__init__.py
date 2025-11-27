# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Vladislav Tislenko (keklick1337)
# Copyright (c) 2025 Yannick Locque (yanuino)

"""Firmware download service with repository management.

This package provides high-level firmware management with a centralized firmware
repository, automatic FOTA version checking, intelligent download handling, and
configurable decryption.

Architecture:
    - Firmware Repository: Centralized storage with metadata tracking
    - IMEI Log: Request tracking for all FOTA queries and downloads
    - Service Layer: High-level API for firmware operations
    - Configuration: Customizable paths for firmware and decrypted files

Main Components:
    - check_firmware: Query FOTA for latest version
    - get_or_download_firmware: Smart download (checks repository first)
    - decrypt_firmware: Decrypt from repository to configurable path
    - download_and_decrypt: Complete workflow convenience function
    - FirmwareRecord: Repository model with all InformInfo metadata
    - Database utilities: SQLite initialization, health checks, and repair

Features:
    - Centralized firmware repository (no per-model/CSC duplication)
    - Automatic FOTA version checking with IMEI logging
    - Smart downloads (skip if already in repository)
    - HTTP Range support for resuming interrupted downloads
    - ENC4 decryption using cached logic values (no extra FUS calls)
    - Configurable output paths via environment variables
    - Progress callback support for UI integration

Example:
    Check latest firmware version::

        from download import check_firmware

        version = check_firmware("SM-A146P", "EUX", "352976245060954")
        print(f"Latest: {version}")

    Download firmware to repository::

        from download import get_or_download_firmware

        firmware = get_or_download_firmware(
            version,
            "SM-A146P",
            "EUX",
            "352976245060954",
            resume=True
        )
        print(f"Encrypted: {firmware.encrypted_file_path}")
        print(f"Logic value: {firmware.logic_value_factory}")

    Decrypt from repository::

        from download import decrypt_firmware

        decrypted_path = decrypt_firmware(version)
        print(f"Decrypted: {decrypted_path}")

    Complete workflow::

        from download import download_and_decrypt

        firmware, decrypted = download_and_decrypt(
            "SM-A146P", "EUX", "352976245060954"
        )
        print(f"Version: {firmware.version_code}")
        print(f"File: {decrypted}")

    Query repository::

        from download import find_firmware, list_firmware

        # Find specific version
        fw = find_firmware("A146PXXS6CXK3/...")
        if fw:
            print(f"Encrypted: {fw.encrypted_file_path}")
            print(f"Decrypted: {fw.decrypted_file_path}")

        # List all firmware
        for fw in list_firmware(limit=10):
            print(f"{fw.version_code}: {fw.filename}")

    Database management::

        from download import init_db, is_healthy, repair_db

        init_db()  # Initialize schema
        if not is_healthy():
            repair_db()

Configuration:
    Set environment variables to customize paths::

        export FIRM_DATA_DIR="/path/to/data"
        export FIRM_DECRYPT_DIR="/path/to/decrypted"
"""

from .db import get_db_path, init_db, is_healthy, repair_db
from .firmware_repository import (
    FirmwareRecord,
    delete_firmware,
    find_firmware,
    list_firmware,
    update_decrypted_path,
)
from .service import (
    check_firmware,
    cleanup_repository,
    decrypt_firmware,
    download_and_decrypt,
    get_or_download_firmware,
)
