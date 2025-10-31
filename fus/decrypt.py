"""
FUS decryption helpers.

Provides functions to derive ENC2/ENC4 keys and to decrypt streaming firmware blobs.

Functions:
- get_v2_key: derive MD5-based ENC2 key.
- get_v4_key: retrieve logic value via FUS inform and derive ENC4 key.
- decrypt_file: decrypt a file encrypting in 16-byte AES blocks.
"""

from __future__ import annotations

import hashlib
import os
from typing import BinaryIO, Callable, Optional

from Crypto.Cipher import AES
from tqdm import tqdm

from .client import FUSClient
from .crypto import logic_check, pkcs_unpad
from .errors import DecryptError, InformError
from .firmware import normalize_vercode
from .messages import build_binary_inform


def get_v2_key(version: str, model: str, region: str, _device_id: str) -> bytes:
    """
    Derive ENC2 key (V2) using MD5.

    Args:
        version: Firmware version string.
        model: Device model identifier.
        region: Region/CSC code.
        _device_id: Unused for V2 (kept for API parity).

    Returns:
        MD5 digest bytes of the string "region:model:version".
    """
    deckey = f"{region}:{model}:{version}"
    return hashlib.md5(deckey.encode()).digest()


def get_v4_key(
    version: str, model: str, region: str, device_id: str, client: FUSClient | None = None
) -> Optional[bytes]:
    """
    Derive ENC4 key (V4) by calling FUS inform to obtain the logic value.

    Args:
        version: Firmware version string.
        model: Device model identifier.
        region: Region/CSC code.
        device_id: IMEI or Serial required by Samsung for ENC4.
        client: Optional FUSClient instance to use (a new one is created if None).

    Returns:
        MD5 digest bytes derived from the logic-check value, or None on failure.

    Raises:
        DecryptError: If device_id is not provided.
        InformError: If the inform response lacks expected fields.
    """
    if not device_id:
        raise DecryptError(
            "Device ID (IMEI or Serial) required for ENC4 key (Samsung requirement)."
        )
    client = client or FUSClient()
    ver = normalize_vercode(version)
    resp = client.inform(build_binary_inform(ver, model, region, device_id, client.nonce))
    try:
        fwver = resp.find("./FUSBody/Results/LATEST_FW_VERSION/Data").text  # type: ignore
        logicval = resp.find("./FUSBody/Put/LOGIC_VALUE_FACTORY/Data").text  # type: ignore
    except Exception as exc:
        raise InformError("Could not obtain decryption key; check model/region/device_id.") from exc
    deckey = logic_check(fwver, logicval)  # type: ignore
    return hashlib.md5(deckey.encode()).digest()


def _decrypt_progress(
    fin: BinaryIO,
    fout: BinaryIO,
    key: bytes,
    total: int,
    *,
    chunk_size: int = 4096,
    progress_cb: Optional[Callable[[int, int], None]] = None,
) -> None:
    """
    Decrypt the input stream to the output stream with optional progress.

    Args:
        fin: Input binary stream positioned at start.
        fout: Output binary stream to write decrypted data.
        key: AES ECB key for decryption.
        total: Total input size in bytes (must be a multiple of 16).
        chunk_size: Chunk size to read/decrypt per loop.
        progress_cb: Optional callback(progress_bytes, total_bytes).

    Raises:
        DecryptError: If total is not a multiple of AES block size (16).
    """
    if total % 16 != 0:
        raise DecryptError("Invalid input block size (not multiple of 16)")
    cipher = AES.new(key, AES.MODE_ECB)
    pbar = None if progress_cb else tqdm(total=total, unit="B", unit_scale=True)
    written = 0
    while True:
        block = fin.read(chunk_size)
        if not block:
            break
        dec = cipher.decrypt(block)
        # We cannot know in advance where padding ends; caller provides the exact 'total'
        next_pos = fin.tell()
        if next_pos == total:
            dec = pkcs_unpad(dec)
        fout.write(dec)
        written += len(block)
        if progress_cb:
            progress_cb(written, total)
        else:
            if pbar:
                pbar.update(len(block))
    if pbar:
        pbar.close()


def decrypt_file(
    enc_path: str,
    out_path: str,
    *,
    enc_ver: int,
    key: bytes,
    progress_cb: Optional[Callable[[int, int], None]] = None,
) -> None:
    """
    Decrypt an encrypted firmware file to disk.

    Args:
        enc_path: Path to the encrypted input file.
        out_path: Path to write the decrypted output file.
        enc_ver: Encryption version (unused by this function but kept for API parity).
        key: AES key used for decryption.
        progress_cb: Optional progress callback(progress_bytes, total_bytes).

    Returns:
        None
    """
    size = os.stat(enc_path).st_size
    with open(enc_path, "rb") as fin, open(out_path, "wb") as fout:
        _decrypt_progress(fin, fout, key, size, progress_cb=progress_cb)
