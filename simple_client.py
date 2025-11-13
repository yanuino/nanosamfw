# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Yannick Locque (yanuino)

import xml.etree.ElementTree as ET
from pathlib import Path
from xml.dom import minidom

from tqdm import tqdm

from fus import FUSClient, get_latest_version, get_v4_key
from fus.decrypt import decrypt_file
from fus.firmware import normalize_vercode, read_firmware_info
from fus.messages import build_binary_inform, build_binary_init
from fus.responses import parse_inform

model, region = "SM-A146P", "EUX"  # EUX
tac: str = "35297624"  # 8-digit TAC code
imei: str = "352976245060954"
ver: str = get_latest_version(model, region)  # latest via version.xml FOTA
info = read_firmware_info(ver)
print(f"Latest: {ver}\nBL: {info['bl']}\nDate: {info['date']}\nIter: {info['it']}")

key = get_v4_key(ver, model, region, imei)
print(f"Decryption key: {key.hex()}")  # type: ignore

client = FUSClient()
ver: str = normalize_vercode(ver)
print(f"Normalized version: {ver}")

inform_xml = client.inform(
    build_binary_inform(fwv=ver, model=model, region=region, device_id=imei, nonce=client.nonce)
)


raw = ET.tostring(inform_xml, encoding="unicode")
pretty = minidom.parseString(raw).toprettyxml(indent="  ")

# print(f"Inform response received: {pretty}")

info_inform = parse_inform(inform_xml)
print(
    f"Inform info: Latest FW: {info_inform.latest_fw_version}, ",
    f"Logic: {info_inform.logic_value_factory}, ",
    f"Filename: {info_inform.filename},",
    f"Path: {info_inform.path},",
    f"Size: {info_inform.size_bytes} bytes",
)


# --- Download and decrypt via FUS only (no download module) ---
print("\nDownloading via FUS (inform → init → stream)...")

# Use the already-parsed inform info
fname = info_inform.filename
srv_path = info_inform.path
expected = info_inform.size_bytes

# Authorize the download (BinaryInit) — expects only the filename
init_xml = client.init(build_binary_init(fname, client.nonce))
raw2 = ET.tostring(init_xml, encoding="unicode")
pretty = minidom.parseString(raw2).toprettyxml(indent="  ")
print(f"Init response received: {raw2}")

# Prepare output paths (downloads/<model>/<region>/filename.enc4)
out_dir = Path("data") / model.replace("/", "_") / region.replace("/", "_")
if not out_dir.exists():
    out_dir.mkdir(parents=True, exist_ok=True)
enc_path = out_dir / fname
part_path = enc_path.with_suffix(enc_path.suffix + ".part")

# Resume if a partial exists
start = part_path.stat().st_size if part_path.exists() else 0
# Concatenate path + filename (path already ends with /, so no extra separator)
remote = srv_path + fname if srv_path else fname
print(f"Streaming from: {remote}")
resp = client.stream(remote, start=start)
mode = "ab" if start > 0 else "wb"
written = start
with open(part_path, mode) as f, tqdm(
    total=expected,
    initial=start,
    unit="B",
    unit_scale=True,
    unit_divisor=1024,
    desc="Downloading",
) as pbar:
    for chunk in resp.iter_content(chunk_size=1024 * 1024):
        if not chunk:
            continue
        f.write(chunk)
        written += len(chunk)
        pbar.update(len(chunk))

if expected and written != expected:
    raise RuntimeError(f"Size mismatch: got {written}, expected {expected}")

# Atomic finalize
part_path.replace(enc_path)
print(f"Encrypted firmware: {enc_path}")

# Decrypt (ENC4) → same name without extension
print("Decrypting...")
dec_path = enc_path.with_suffix("")
if not key:
    raise RuntimeError("Failed to derive ENC4 key; cannot decrypt.")

# Progress bar for decryption (tracks encrypted bytes processed)
total_enc = enc_path.stat().st_size
with tqdm(
    total=total_enc,
    unit="B",
    unit_scale=True,
    unit_divisor=1024,
    desc="Decrypting",
) as pbar:

    def _dec_cb(done: int, total: int) -> None:
        # Sync total if needed (should match total_enc) and advance by delta
        if pbar.total != total:
            pbar.total = total
        pbar.update(done - pbar.n)

    decrypt_file(str(enc_path), str(dec_path), key=key, progress_cb=_dec_cb)
print(f"Decrypted to: {dec_path}")
