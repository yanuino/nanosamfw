# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Vladislav Tislenko (keklick1337)
# Copyright (c) 2025 Yannick Locque (yanuino)

"""Firmware download service with repository management.

This package provides high-level firmware management with a centralized firmware
repository, automatic FOTA version checking, intelligent download handling,
configurable decryption, and component checksum verification.

Architecture:
    - Firmware Repository: Centralized storage with metadata tracking
    - Component Management: MD5 checksum verification for extracted files
    - IMEI Log: Request tracking for all FOTA queries and downloads
    - Service Layer: High-level API for firmware operations
    - Configuration: Customizable paths for firmware and decrypted files

Main Components:
    - check_and_prepare_firmware: Query FOTA + check repository cache
    - get_or_download_firmware: Smart download (checks repository first)
    - decrypt_firmware: Decrypt from repository to configurable path
    - extract_firmware: Extract firmware with MD5 checksum computation
    - download_and_decrypt: Complete workflow convenience function
    - FirmwareRecord: Repository model with all InformInfo metadata
    - ComponentRecord: Component file model with checksum verification
    - Database utilities: SQLite initialization, health checks, and cleanup

Features:
    - Centralized firmware repository (no per-model/CSC duplication)
    - Automatic FOTA version checking with IMEI logging
    - Smart downloads (skip if already in repository)
    - HTTP Range support for resuming interrupted downloads
    - ENC4 decryption using cached logic values (no extra FUS calls)
    - MD5 checksum computation and verification for components
    - Automatic cleanup of encrypted/decrypted files after extraction
    - Configurable output paths via environment variables
    - Progress callback support for UI integration

Workflow:
    1. Download encrypted firmware (.enc4)
    2. Decrypt firmware to ZIP file
    3. Extract components and compute MD5 checksums
    4. Store component metadata in database
    5. Optionally clean up encrypted and decrypted files

    At each step, the firmware status flags (downloaded, decrypted, extracted)
    are updated in the database for tracking and resumption support.

Example:
    Check latest firmware version and repository cache::

        from download import check_and_prepare_firmware

        version, is_cached = check_and_prepare_firmware(
            "SM-A146P", "EUX", "352976245060954", "current_version"
        )
        print(f"Latest: {version}, Already downloaded: {is_cached}")

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
    Complete workflow::

        from download import download_and_decrypt

        firmware, decrypted = download_and_decrypt(
            "SM-A146P", "EUX", "352976245060954", "current_version"
        )
        print(f"Version: {firmware.version_code}")
        print(f"File: {decrypted}")
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

    Component management::

        from download import extract_firmware, list_components

        # Extract with checksum computation and cleanup
        unzip_dir = extract_firmware(
            decrypted_path,
            version_code="A146PXXS6CXK3/...",
            cleanup_after=True  # Remove encrypted and decrypted files
        )

        # List components with checksums
        for comp in list_components("A146PXXS6CXK3/..."):
            print(f"{comp.filename}: {comp.md5sum} ({comp.size_bytes} bytes)")

Configuration:
    Set environment variables to customize paths::

        export FIRM_DATA_DIR="/path/to/data"
        export FIRM_DECRYPT_DIR="/path/to/decrypted"
"""

from .db import get_db_path, init_db, is_healthy, repair_db
from .firmware_repository import (
    ComponentRecord,
    FirmwareRecord,
    compute_md5,
    delete_components,
    delete_firmware,
    find_firmware,
    list_components,
    list_firmware,
    update_firmware_status,
    upsert_component,
)
from .service import (
    check_and_prepare_firmware,
    cleanup_repository,
    decrypt_firmware,
    download_and_decrypt,
    extract_firmware,
    get_or_download_firmware,
    get_session_id,
)
