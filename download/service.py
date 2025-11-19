# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Yannick Locque (yanuino)

"""Firmware download and management service.

This module provides high-level firmware management functionality including
FOTA version checking, firmware download with repository management, and
decryption services.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from fus.client import FUSClient
from fus.decrypt import decrypt_file, get_v4_key_from_logic
from fus.errors import DownloadError
from fus.firmware import get_latest_version, normalize_vercode
from fus.messages import build_binary_inform, build_binary_init
from fus.responses import parse_inform

from .config import PATHS
from .firmware_repository import (
    FirmwareRecord,
    find_firmware,
    update_decrypted_path,
    upsert_firmware,
)
from .imei_repository import add_imei_event


def check_firmware(model: str, csc: str, device_id: str) -> str:
    """Check latest available firmware version via FOTA.

    Queries Samsung FOTA servers for the latest firmware version and logs
    the request to imei_log database.

    Args:
        model: Device model identifier (e.g., SM-G998B).
        csc: Country Specific Code.
        device_id: Device IMEI or serial number.

    Returns:
        Normalized firmware version string (4-part format: AAA/BBB/CCC/DDD).

    Raises:
        FUSError: If version lookup fails.

    Example:
        version = check_firmware("SM-A146P", "EUX", "352976245060954")
        print(f"Latest: {version}")
    """
    version = get_latest_version(model, csc)
    version_norm = normalize_vercode(version)

    # Log FOTA check to database
    add_imei_event(
        imei=device_id,
        model=model,
        csc=csc,
        version_code=version_norm,
        status_fus="ok",
        status_upgrade="unknown",
    )

    return version_norm


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

    # Log download to IMEI log
    add_imei_event(
        imei=device_id,
        model=model,
        csc=csc,
        version_code=version_norm,
        status_fus="ok",
        status_upgrade="ok",
    )

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
    version: Optional[str] = None,
    *,
    output_path: Optional[str] = None,
    resume: bool = True,
    progress_cb: Optional[Callable[[int, int], None]] = None,
) -> tuple[FirmwareRecord, str]:
    """Complete workflow: check FOTA, download, and decrypt firmware.

    Convenience function that performs the full workflow:
    1. Check latest version via FOTA (if version not specified)
    2. Download firmware to repository (if not already present)
    3. Decrypt firmware to output directory

    Args:
        model: Device model identifier.
        csc: Country Specific Code.
        device_id: Device IMEI or serial number.
        version: Optional specific version to download. If None, fetches latest.
        output_path: Optional custom decryption output path.
        resume: If True, resume partial downloads.
        progress_cb: Optional progress callback for download and decrypt.

    Returns:
        Tuple of (FirmwareRecord, decrypted_file_path).

    Example:
        firmware, decrypted = download_and_decrypt(
            "SM-A146P", "EUX", "352976245060954",
            decrypt=True
        )
        print(f"Version: {firmware.version_code}")
        print(f"Decrypted: {decrypted}")
    """
    # 1. Resolve version
    if not version:
        version = check_firmware(model, csc, device_id)
    else:
        version = normalize_vercode(version)

    # 2. Download to repository
    firmware = get_or_download_firmware(
        version, model, csc, device_id, resume=resume, progress_cb=progress_cb
    )

    # 3. Decrypt
    decrypted_path = decrypt_firmware(version, output_path, progress_cb=progress_cb)

    return firmware, decrypted_path
