# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Vladislav Tislenko (keklick1337)
# Copyright (c) 2025 Yannick Locque (yanuino)

"""Firmware download service.

This module provides high-level firmware download functionality including
version resolution, FUS protocol handling, file download with resume support,
and optional decryption.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Callable, Optional, Tuple

from fus.client import FUSClient
from fus.decrypt import decrypt_file, get_v4_key
from fus.errors import DownloadError
from fus.firmware import get_latest_version, normalize_vercode
from fus.messages import build_binary_inform, build_binary_init
from fus.responses import get_info_from_inform

from .config import PATHS
from .repository import DownloadRecord, upsert_download


def _safe_dir(*parts: str) -> Path:
    """Create a sanitized subdirectory under the downloads directory.

    Constructs a safe directory path by replacing path separators with underscores
    and creating the directory if it doesn't exist.

    Args:
        *parts: Variable number of path components to join.

    Returns:
        Path: Absolute path to the created directory.
    """
    rel = Path(*[p.replace("/", "_") for p in parts])
    final = PATHS.downloads_dir / rel
    final.mkdir(parents=True, exist_ok=True)
    return final


def _extract_filename_and_size(inform_root: ET.Element) -> Tuple[str, int]:
    """Extract filename and size from FUS inform response.

    Args:
        inform_root: Parsed XML root element from the inform response.

    Returns:
        Tuple of (filename, size_bytes).

    Raises:
        InformError: If the inform response status is not 200.
    """
    filename, _path, size = get_info_from_inform(inform_root)
    return filename, size


def _download_to_file(
    client: FUSClient,
    filename: str,
    out_path: Path,
    *,
    expected_size: Optional[int] = None,
    resume: bool = True,
    chunk_size: int = 1024 * 1024,
    progress_cb: Optional[Callable[[int, Optional[int]], None]] = None,
) -> Path:
    """Download firmware file to disk with resume support.

    Downloads a firmware file via NF_DownloadBinaryForMass.do endpoint with the
    following features:
    - Resume support using HTTP Range headers if a .part file exists
    - Atomic rename from .part to final filename on completion
    - Size verification if expected_size is provided
    - Progress callback support

    Args:
        client: FUSClient instance with valid authorization.
        filename: Firmware filename to download.
        out_path: Destination path for the downloaded file.
        expected_size: Optional expected file size in bytes for verification.
        resume: If True, resume from existing .part file if present.
        chunk_size: Download chunk size in bytes.
        progress_cb: Optional callback function(bytes_written, expected_size).

    Returns:
        Path: Absolute path to the downloaded file.

    Raises:
        DownloadError: If downloaded size doesn't match expected_size.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = out_path.with_suffix(out_path.suffix + ".part")

    start = 0
    if resume and tmp_path.exists():
        start = tmp_path.stat().st_size

    resp = client.stream(filename, start=start)

    mode = "ab" if start > 0 else "wb"
    written = start
    with open(tmp_path, mode) as f:
        for chunk in resp.iter_content(chunk_size=chunk_size):
            if not chunk:
                continue
            f.write(chunk)
            written += len(chunk)
            if progress_cb:
                progress_cb(written, expected_size)

    if expected_size is not None and written != expected_size:
        raise DownloadError(f"Taille inattendue: {written} != {expected_size}")

    tmp_path.replace(out_path)
    return out_path


def download_firmware(
    *,
    model: str,
    csc: str,
    device_id: str,
    version: Optional[str] = None,
    decrypt: bool = True,
    resume: bool = True,
    progress_cb: Optional[Callable[[int, Optional[int]], None]] = None,
) -> DownloadRecord:
    """Download and optionally decrypt firmware, persisting metadata to database.

    This is the main high-level API for firmware downloads. The process follows these steps:

    1. Version resolution (if not provided) via FOTA version.xml
    2. INFORM request to get filename and size
    3. INIT request with LOGIC_CHECK computed from filename
    4. Download binary with HTTP Range support for resume
    5. (Optional) Decrypt ENC4 to ZIP format
    6. Persist metadata to database via upsert

    Args:
        model: Device model identifier (e.g., SM-G998B).
        csc: Country Specific Code.
        device_id: Device IMEI or serial number.
        version: Optional firmware version (4-part format). If None, latest version is fetched.
        decrypt: If True, decrypt the downloaded file after download.
        resume: If True, resume from partial download if .part file exists.
        progress_cb: Optional callback function(bytes_processed, expected_size) for progress tracking.

    Returns:
        DownloadRecord: Database record containing download metadata and file path.

    Raises:
        FUSError: If version lookup fails or FUS protocol errors occur.
        DownloadError: If download fails or size verification fails.

    Note:
        The output directory is organized as downloads/model/csc/ with path separators
        sanitized to underscores.
    """
    # 1) Version (4-part)
    if not version:
        version = get_latest_version(model, csc)
    version_norm = normalize_vercode(version)

    # Output directory (by model/CSC)
    out_dir = _safe_dir(model, csc)

    # 2) INFORM
    client = FUSClient()
    inform_payload = build_binary_inform(version_norm, model, csc, device_id, client.nonce)
    inform_root = client.inform(inform_payload)

    filename, expected_size = _extract_filename_and_size(inform_root)

    # 3) INIT (LOGIC_CHECK computed from filename - last 16 chars of base-name)
    init_payload = build_binary_init(filename, client.nonce)
    client.init(init_payload)

    # 4) DOWNLOAD binary enc4 file (encoded_filename)
    enc_path = out_dir / filename
    enc_final = _download_to_file(
        client=client,
        filename=filename,
        out_path=enc_path,
        expected_size=expected_size,
        resume=resume,
        progress_cb=progress_cb,
    )

    # 5) (Optional) DECRYPT ENC4 -> ZIP
    dec_path: Optional[Path] = None
    if decrypt:
        key = get_v4_key(version_norm, model, csc, device_id, client)
        dec_path = enc_final.with_suffix("")  # Remove .enc4 -> .zip (or actual suffix)
        decrypt_file(
            str(enc_final),
            str(dec_path),
            enc_ver=4,
            key=key,  # type: ignore
            progress_cb=progress_cb,
        )

    # 6) UPSERT to database
    size_bytes = enc_final.stat().st_size if enc_final.exists() else None
    preferred_path = dec_path if dec_path else enc_final

    rec = DownloadRecord(
        model=model,
        csc=csc,
        version_code=version_norm,
        encoded_filename=filename,
        size_bytes=size_bytes,
        status="done",
        path=str(preferred_path.resolve()),
    )
    upsert_download(rec)
    return rec
