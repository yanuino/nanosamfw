"""Example script demonstrating device detection via AT commands.

This script shows how to:
1. Auto-detect a connected Samsung device using AT commands
2. Read device information (model, firmware, sales code)
3. Check for firmware updates
4. Download and decrypt firmware if updates are available

Requirements:
- pyserial package installed
- Samsung USB drivers (Windows)
- Samsung device connected (normal mode or recovery mode)

NOTE: This uses AT commands, not Odin protocol. For download mode (Odin),
      see example_odin_device_detection.py

Copyright (c) 2024 nanosamfw contributors
SPDX-License-Identifier: MIT
"""

from tqdm import tqdm

from device import DeviceNotFoundError, read_device_info_at
from download import check_and_prepare_firmware, decrypt_firmware, get_or_download_firmware, init_db


def main() -> None:
    """Main execution function."""
    # Initialize database (creates tables if they don't exist)
    init_db()

    print("=" * 60)
    print("Samsung Device Detection (AT Commands)")
    print("=" * 60)
    print()
    print("NOTE: Device must be connected and responding to AT commands")
    print()

    # Step 1: Detect and read device information via AT commands
    try:
        print("🔍 Detecting Samsung device...")
        device = read_device_info_at()
        print("✅ Device detected!")
        print()
        print(device)
        print()

    except DeviceNotFoundError:
        print("❌ Error: No Samsung device in download mode detected")
        print("   Please ensure your device is:")
        print("   - Connected via USB")
        print("   - In download mode (Odin mode)")
        print("   - Samsung USB drivers are installed (Windows)")
        print()
        print("   To enter download mode:")
        print("   1. Power off device completely")
        print("   2. Hold Volume Down + Home + Power")
        print("   3. Press Volume Up when warning appears")
        return
    except (ImportError, OSError, IOError) as ex:
        print(f"❌ Error reading device: {ex}")
        return

    # Validate required fields
    if not device.model or not device.sales_code:
        print("❌ Error: Could not read model or sales code from device")
        print("   Device may not support AT commands")
        return

    # Step 2: Check for firmware updates
    print("-" * 60)
    print("🔎 Checking for firmware updates...")
    try:
        # Use device IMEI for firmware query
        latest_version, is_update = check_and_prepare_firmware(
            model=device.model,
            csc=device.sales_code,
            device_id=device.imei,
            current_firmware=device.firmware_version,
        )
        print(f"✅ Latest firmware: {latest_version}")
        print()

        # Compare versions
        if latest_version == device.firmware_version:
            print("✅ Device is up to date!")
            print(f"   Current version: {device.firmware_version}")
            print(f"   Latest version:  {latest_version}")
            return

        # Step 3: Download new firmware
        print("📥 New firmware available!")
        print(f"   Current version: {device.firmware_version}")
        print(f"   Latest version:  {latest_version}")
        print()

        response = input("Would you like to download it? (y/n): ").strip().lower()
        if response != "y":
            print("Download cancelled.")
            return

        # Progress helpers using tqdm for smooth updates
        def make_progress_cb(phase_name: str):
            state = {"bar": None, "last": 0, "total": 0}

            def _cb(done: int, total: int) -> None:
                # Initialize or reset bar when total changes or counter resets
                if state["bar"] is None or total != state["total"] or done < state["last"]:
                    if state["bar"] is not None:
                        state["bar"].close()
                    state["bar"] = tqdm(
                        total=total, unit="B", unit_scale=True, desc=phase_name, leave=True
                    )
                    state["last"] = 0
                    state["total"] = total
                # Update by delta to avoid double counting
                delta = done - state["last"]
                if delta > 0:
                    state["bar"].update(delta)
                    state["last"] = done

            return _cb

        download_cb = make_progress_cb("Download")
        decrypt_cb = make_progress_cb("Decrypt")

        print()
        print("📥 Downloading firmware to repository...")
        firmware = get_or_download_firmware(
            latest_version,
            device.model,
            device.sales_code,
            device.imei,
            resume=True,
            progress_cb=download_cb,
        )

        print()
        print("🔓 Decrypting firmware...")
        decrypted_path = decrypt_firmware(
            latest_version,
            progress_cb=decrypt_cb,
        )

        print()
        print("✅ Download complete!")
        print(f"   Version: {firmware.version_code}")
        print(f"   Filename: {firmware.filename}")
        print(f"   Size: {firmware.size_bytes:,} bytes")
        print(f"   Decrypted file: {decrypted_path}")

    except (ImportError, OSError, IOError, ValueError, RuntimeError) as ex:
        print(f"❌ Error: {ex}")
        return


if __name__ == "__main__":
    main()
