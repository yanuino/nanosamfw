# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Yannick Locque (yanuino)

"""Firmware download and management service.

This module provides high-level firmware management functionality including
FOTA version checking, firmware download with repository management, and
decryption services.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Callable, Dict, Optional

from fus.client import FUSClient
from fus.decrypt import decrypt_file, get_v4_key_from_logic
from fus.errors import DownloadError
from fus.firmware import get_latest_version, normalize_vercode
from fus.messages import build_binary_inform, build_binary_init
from fus.responses import parse_inform

from .config import PATHS
from .firmware_repository import (
    FirmwareRecord,
    delete_firmware,
    find_firmware,
    list_firmware,
    update_decrypted_path,
    upsert_firmware,
)
from .imei_repository import upsert_imei_event

# Generate unique session ID for this application instance
_SESSION_ID = str(uuid.uuid4())


def get_session_id() -> str:
    """Get the current application session ID.

    Returns:
        str: UUID string identifying this application session.
    """
    return _SESSION_ID


def check_and_prepare_firmware(
    model: str,
    csc: str,
    device_id: str,
    current_firmware: str,  # noqa: ARG001 - Reserved for future comparison logic
) -> tuple[str, bool]:
    """Check latest firmware via FOTA and determine if cached in repository.

    Always queries Samsung FOTA for latest version. Logs to imei_log with
    status_fus="unknown" (no FUS query yet). Then checks firmware table
    to see if that version is already downloaded.

    Args:
        model: Device model identifier (e.g., SM-G998B).
        csc: Country Specific Code.
        device_id: Device IMEI or serial number.
        current_firmware: Current device firmware version (for logging/comparison).

    Returns:
        (latest_version, is_cached): Latest version from FOTA and whether
            it exists in local repository.

    Raises:
        FOTAError: If FOTA query fails.

    Example:
        latest, cached = check_and_prepare_firmware(
            "SM-A146P", "EUX", "352976245060954", "A146PXXS6CXK3/..."
        )
        if cached:
            print(f"Version {latest} already downloaded")
    """
    # 1. Always query FOTA for latest version
    version = get_latest_version(model, csc)
    version_norm = normalize_vercode(version)

    # 2. Log device detection with FOTA result (status_fus="unknown" - no FUS download yet)
    upsert_imei_event(
        session_id=_SESSION_ID,
        imei=device_id,
        model=model,
        csc=csc,
        version_code=version_norm,
        status_fus="unknown",  # FUS download not attempted yet
        status_upgrade="unknown",  # Firmware flashing not implemented
    )

    # 3. Check if this specific version exists in repository
    cached = find_firmware(version_norm)
    is_cached = cached is not None and Path(cached.encrypted_file_path).exists()

    return version_norm, is_cached


def get_or_download_firmware(
    version_code: str,
    model: str,
    csc: str,
    device_id: str,
    *,
    resume: bool = True,
    progress_cb: Optional[Callable[[int, int], None]] = None,
) -> FirmwareRecord:
    """Get firmware from repository or download if not present.

    Checks if the firmware already exists in the repository. If not, downloads
    it from Samsung FUS servers and stores metadata in the database.

    Args:
        version_code: Firmware version identifier (4-part format).
        model: Device model identifier.
        csc: Country Specific Code.
        device_id: Device IMEI or serial number.
        resume: If True, resume from partial download if .part file exists.
        progress_cb: Optional callback function(bytes_downloaded, total_bytes).

    Returns:
        FirmwareRecord: Repository record with encrypted file path and metadata.

    Raises:
        InformError: If FUS inform request fails.
        DownloadError: If download fails or size verification fails.

    Example:
        firmware = get_or_download_firmware(
            "A146PXXS6CXK3/A146POXM6CXK3/...",
            "SM-A146P",
            "EUX",
            "352976245060954"
        )
        print(f"Encrypted file: {firmware.encrypted_file_path}")
    """
    # Check if already in repository
    existing = find_firmware(version_code)
    if existing and Path(existing.encrypted_file_path).exists():
        return existing

    # Download from FUS
    version_norm = normalize_vercode(version_code)
    client = FUSClient()

    # 1. INFORM - get firmware metadata
    inform_payload = build_binary_inform(version_norm, model, csc, device_id, client.nonce)
    inform_root = client.inform(inform_payload)
    info = parse_inform(inform_root)

    # 2. INIT - authorize download
    init_payload = build_binary_init(info.filename, client.nonce)
    client.init(init_payload)

    # 3. DOWNLOAD - stream to disk
    PATHS.firmware_dir.mkdir(parents=True, exist_ok=True)
    enc_path = PATHS.firmware_dir / info.filename
    part_path = enc_path.with_suffix(enc_path.suffix + ".part")

    start = part_path.stat().st_size if (resume and part_path.exists()) else 0
    remote = info.path + info.filename
    resp = client.stream(remote, start=start)

    mode = "ab" if start > 0 else "wb"
    written = start
    with open(part_path, mode) as f:
        for chunk in resp.iter_content(chunk_size=1024 * 1024):
            if not chunk:
                continue
            f.write(chunk)
            written += len(chunk)
            if progress_cb:
                progress_cb(written, info.size_bytes)

    if written != info.size_bytes:
        raise DownloadError(f"Size mismatch: got {written}, expected {info.size_bytes}")

    # Atomic finalize
    part_path.replace(enc_path)

    # 4. PERSIST to repository
    rec = FirmwareRecord(
        version_code=version_norm,
        filename=info.filename,
        path=info.path,
        size_bytes=info.size_bytes,
        logic_value_factory=info.logic_value_factory,
        latest_fw_version=info.latest_fw_version,
        encrypted_file_path=str(enc_path.resolve()),
        decrypted_file_path=None,
    )
    upsert_firmware(rec)

    return rec


def decrypt_firmware(
    version_code: str,
    output_path: Optional[str] = None,
    *,
    progress_cb: Optional[Callable[[int, int], None]] = None,
) -> str:
    """Decrypt firmware from repository.

    Decrypts a firmware file that exists in the repository. The decrypted
    file is saved to the configured decrypted directory or a custom path.

    Args:
        version_code: Firmware version identifier to decrypt.
        output_path: Optional custom output path. If None, uses
            PATHS.decrypted_dir/<filename_without_enc4>.
        progress_cb: Optional callback function(bytes_processed, total_bytes).

    Returns:
        Absolute path to the decrypted file.

    Raises:
        ValueError: If firmware not found in repository.
        FileNotFoundError: If encrypted file doesn't exist on disk.
        DecryptError: If decryption fails.

    Example:
        decrypted = decrypt_firmware("A146PXXS6CXK3/...")
        print(f"Decrypted to: {decrypted}")
    """
    # Get firmware from repository
    firmware = find_firmware(version_code)
    if not firmware:
        raise ValueError(f"Firmware {version_code} not found in repository")

    enc_path = Path(firmware.encrypted_file_path)
    if not enc_path.exists():
        raise FileNotFoundError(f"Encrypted file not found: {enc_path}")

    # Determine output path
    if output_path:
        dec_path = Path(output_path)
    else:
        PATHS.decrypted_dir.mkdir(parents=True, exist_ok=True)
        dec_path = PATHS.decrypted_dir / enc_path.stem

    # Decrypt using logic value from repository
    key = get_v4_key_from_logic(firmware.latest_fw_version, firmware.logic_value_factory)
    decrypt_file(
        str(enc_path),
        str(dec_path),
        key=key,
        progress_cb=progress_cb,
    )

    # Update repository with decrypted path
    update_decrypted_path(version_code, str(dec_path.resolve()))

    return str(dec_path.resolve())


def download_and_decrypt(
    model: str,
    csc: str,
    device_id: str,
    current_firmware: str,
    version: Optional[str] = None,
    *,
    output_path: Optional[str] = None,
    resume: bool = True,
    progress_cb: Optional[Callable[[str, int, int], None]] = None,
) -> tuple[FirmwareRecord, str]:
    """Complete workflow: check FOTA, download, and decrypt firmware.

    Performs the full workflow:
    1. Query FOTA for latest version and check repository cache
    2. Download encrypted firmware if not cached (with resume support)
    3. Decrypt firmware to output directory
    4. Update imei_log with FUS download status

    A single optional ``progress_cb`` is invoked for both stages with:
        progress_cb(stage, done_bytes, total_bytes)
    where ``stage`` is one of ``"download"`` or ``"decrypt"``.

    Args:
        model: Device model identifier.
        csc: Country Specific Code (region).
        device_id: Device IMEI or serial/blank for download mode.
        current_firmware: Current device firmware version.
        version: Specific version to fetch; if None latest from FOTA is used.
        output_path: Optional explicit decrypted output path.
        resume: Resume partial downloads when True.
        progress_cb: Unified callback for both stages.

    Returns:
        (FirmwareRecord, decrypted_file_path)
    """
    # 1. Resolve version and check cache
    if not version:
        version, _is_cached = check_and_prepare_firmware(model, csc, device_id, current_firmware)
    else:
        version = normalize_vercode(version)

    # 2. Download to repository
    def _dl_cb(done: int, total: int):
        if progress_cb:
            progress_cb("download", done, total)

    firmware = get_or_download_firmware(
        version, model, csc, device_id, resume=resume, progress_cb=_dl_cb if progress_cb else None
    )

    # Update log with successful firmware retrieval (whether downloaded or cached)
    # This updates the existing session record created by check_and_prepare_firmware
    upsert_imei_event(
        session_id=_SESSION_ID,
        imei=device_id,
        model=model,
        csc=csc,
        version_code=version,
        status_fus="ok",  # Firmware obtained successfully
        status_upgrade="unknown",  # Firmware flashing not implemented
    )

    # 3. Decrypt
    def _dec_cb(done: int, total: int):
        if progress_cb:
            progress_cb("decrypt", done, total)

    decrypted_path = decrypt_firmware(
        version,
        output_path,
        progress_cb=_dec_cb if progress_cb else None,
    )

    return firmware, decrypted_path


def cleanup_repository(
    progress_cb: Optional[Callable[[int, int, int, int, int], None]] = None,
) -> Dict[str, int]:
    """Clean repository inconsistencies.

    Verifies each firmware record's encrypted file exists. If missing:
        * Deletes decrypted file if present.
        * Deletes database record.

    Args:
        progress_cb: Optional callback invoked as
            progress_cb(processed, total, missing_encrypted, records_deleted, decrypted_deleted)

    Returns:
        Summary statistics dict with keys:
            total_records, missing_encrypted, decrypted_deleted, records_deleted
    """
    stats = {
        "total_records": 0,
        "missing_encrypted": 0,
        "decrypted_deleted": 0,
        "records_deleted": 0,
    }

    records = list(list_firmware())
    total = len(records)
    for idx, rec in enumerate(records, start=1):
        stats["total_records"] += 1
        enc_path = Path(rec.encrypted_file_path)
        if not enc_path.is_file():
            stats["missing_encrypted"] += 1
            # remove decrypted file if exists
            if rec.decrypted_file_path:
                dec_path = Path(rec.decrypted_file_path)
                try:
                    if dec_path.exists():
                        dec_path.unlink()
                        stats["decrypted_deleted"] += 1
                except OSError:
                    pass
            delete_firmware(rec.version_code)
            stats["records_deleted"] += 1

        if progress_cb:
            progress_cb(
                idx,
                total,
                stats["missing_encrypted"],
                stats["records_deleted"],
                stats["decrypted_deleted"],
            )

    return stats
