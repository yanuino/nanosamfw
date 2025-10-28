from __future__ import annotations
import hashlib, os
from typing import Optional, BinaryIO
from Crypto.Cipher import AES
from tqdm import tqdm
import xml.etree.ElementTree as ET

from .client import FUSClient
from .messages import build_binary_inform, build_binary_init
from .firmware import normalize_vercode
from .crypto import pkcs_unpad, logic_check
from .errors import InformError, DecryptError

def get_v2_key(version: str, model: str, region: str, _device_id: str) -> bytes:
    # MD5("region:model:version")
    deckey = f"{region}:{model}:{version}"
    return hashlib.md5(deckey.encode()).digest()

def get_v4_key(version: str, model: str, region: str, device_id: str, client: FUSClient | None = None) -> Optional[bytes]:
    if not device_id:
        raise DecryptError("Device ID (IMEI or Serial) required for ENC4 key (Samsung requirement).")
    client = client or FUSClient()
    ver = normalize_vercode(version)
    resp = client.inform(build_binary_inform(ver, model, region, device_id, client.nonce))
    try:
        fwver = resp.find("./FUSBody/Results/LATEST_FW_VERSION/Data").text  # type: ignore
        logicval = resp.find("./FUSBody/Put/LOGIC_VALUE_FACTORY/Data").text  # type: ignore
    except Exception:
        raise InformError("Could not obtain decryption key; check model/region/device_id.")
    deckey = logic_check(fwver, logicval) #type: ignore
    return hashlib.md5(deckey.encode()).digest()

def _decrypt_progress(fin: BinaryIO, fout: BinaryIO, key: bytes, total: int, *, chunk_size: int = 4096, progress_cb=None) -> None:
    if total % 16 != 0:
        raise DecryptError("Invalid input block size (not multiple of 16)")
    cipher = AES.new(key, AES.MODE_ECB)
    pbar = None if progress_cb else tqdm(total=total, unit="B", unit_scale=True)
    written = 0
    while True:
        block = fin.read(chunk_size)
        if not block: break
        dec = cipher.decrypt(block)
        # On ne sait pas ex ante où tombe le padding: on laisse l'appelant gérer le 'total' exact
        next_pos = fin.tell()
        if next_pos == total:
            dec = pkcs_unpad(dec)
        fout.write(dec)
        written += len(block)
        if progress_cb: progress_cb(written, total)
        else: 
            if pbar: pbar.update(len(block))
    if pbar: pbar.close()

def decrypt_file(enc_path: str, out_path: str, *, enc_ver: int, key: bytes, progress_cb=None) -> None:
    size = os.stat(enc_path).st_size
    with open(enc_path, "rb") as fin, open(out_path, "wb") as fout:
        _decrypt_progress(fin, fout, key, size, progress_cb=progress_cb)