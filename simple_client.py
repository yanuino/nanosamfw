"""Examples of using nanosamfw: high-level download/decrypt and raw FUS flow."""

from tqdm import tqdm

from download import download_and_decrypt
from download.db import init_db
from fus import FUSClient, get_latest_version, get_v4_key
from fus.decrypt import decrypt_file
from fus.firmware import normalize_vercode, read_firmware_info
from fus.messages import build_binary_inform, build_binary_init
from fus.responses import parse_inform


def main_high_level(model: str, csc: str, device_id: str) -> None:
    """High-level API: download_and_decrypt with unified progress callback.

    Args:
        model: Device model identifier (e.g., "SM-A146P").
        csc: Region/CSC code (e.g., "EUX").
        device_id: IMEI or serial.
    """
    # Initialize the database
    init_db()

    def unified_progress_cb(stage: str, done: int, total: int) -> None:
        if not hasattr(unified_progress_cb, "bars_store"):
            unified_progress_cb.bars_store = {}  # type: ignore[attr-defined]
            unified_progress_cb.last_store = {}  # type: ignore[attr-defined]
            unified_progress_cb.total_store = {}  # type: ignore[attr-defined]

        bars = unified_progress_cb.bars_store  # type: ignore[attr-defined]
        last = unified_progress_cb.last_store  # type: ignore[attr-defined]
        totals = unified_progress_cb.total_store  # type: ignore[attr-defined]

        if stage not in bars or total != totals.get(stage) or done < last.get(stage, 0):
            if stage in bars:
                bars[stage].close()
            bars[stage] = tqdm(
                total=total, unit="B", unit_scale=True, desc=stage.capitalize(), leave=True
            )
            last[stage] = 0
            totals[stage] = total

        delta = done - last[stage]
        if delta > 0:
            bars[stage].update(delta)
            last[stage] = done

    firmware, decrypted = download_and_decrypt(
        model=model,
        csc=csc,
        device_id=device_id,
        resume=True,
        progress_cb=unified_progress_cb,
    )

    print()
    print("✅ Complete!")
    print(f"Version: {firmware.version_code}")
    print(f"Decrypted file: {decrypted}")


def main_raw_fus(model: str, region: str, imei: str) -> None:
    """Raw FUS flow: inform → init → stream → decrypt (no download package).

    Args:
        model: Device model identifier.
        region: Region/CSC code.
        imei: Device IMEI.
    """

    ver = get_latest_version(model, region)
    info = read_firmware_info(ver)
    print(f"Latest: {ver}\nBL: {info['bl']}\nDate: {info['date']}\nIter: {info['it']}")

    client = FUSClient()
    ver = normalize_vercode(ver)
    print(f"Normalized version: {ver}")

    inform_xml = client.inform(
        build_binary_inform(fwv=ver, model=model, region=region, device_id=imei, nonce=client.nonce)
    )
    info_inform = parse_inform(inform_xml)
    print(
        f"Inform info: Latest FW: {info_inform.latest_fw_version}, ",
        f"Logic: {info_inform.logic_value_factory}, ",
        f"Filename: {info_inform.filename},",
        f"Path: {info_inform.path},",
        f"Size: {info_inform.size_bytes} bytes",
    )

    # Authorize the download (BinaryInit)
    client.init(build_binary_init(info_inform.filename, client.nonce))

    # Prepare paths
    from pathlib import Path

    out_dir = Path("data") / model.replace("/", "_") / region.replace("/", "_")
    out_dir.mkdir(parents=True, exist_ok=True)
    enc_path = out_dir / info_inform.filename
    part_path = enc_path.with_suffix(enc_path.suffix + ".part")

    # Resume if a partial exists
    start = part_path.stat().st_size if part_path.exists() else 0
    remote = (info_inform.path or "") + info_inform.filename
    print(f"Streaming from: {remote}")
    resp = client.stream(remote, start=start)
    mode = "ab" if start > 0 else "wb"
    written = start
    with open(part_path, mode) as f, tqdm(
        total=info_inform.size_bytes,
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

    if info_inform.size_bytes and written != info_inform.size_bytes:
        raise RuntimeError(f"Size mismatch: got {written}, expected {info_inform.size_bytes}")

    # Atomic finalize
    part_path.replace(enc_path)
    print(f"Encrypted firmware: {enc_path}")

    # Decrypt (ENC4) → key from FUS helper
    print("Decrypting...")
    dec_path = enc_path.with_suffix("")
    key = get_v4_key(ver, model, region, imei)
    if key is None:
        raise RuntimeError("Failed to derive ENC4 key; cannot decrypt.")
    total_enc = enc_path.stat().st_size
    with tqdm(
        total=total_enc,
        unit="B",
        unit_scale=True,
        unit_divisor=1024,
        desc="Decrypting",
    ) as pbar:

        def _dec_cb(done: int, total: int) -> None:
            if pbar.total != total:
                pbar.total = total
            pbar.update(done - pbar.n)

        decrypt_file(str(enc_path), str(dec_path), key=key, progress_cb=_dec_cb)
    print(f"Decrypted to: {dec_path}")


if __name__ == "__main__":
    # Defaults (edit as needed or add argparse)
    default_model = "SM-A146P"
    default_csc = "EUX"
    default_imei = "352976245060954"

    # High-level download service (recommended)
    # main_high_level(default_model, default_csc, default_imei)

    # Raw FUS-only flow (uncomment to run)
    main_raw_fus(default_model, default_csc, default_imei)
