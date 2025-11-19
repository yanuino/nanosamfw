"""Example script demonstrating device detection and firmware download.

This script shows how to:
1. Auto-detect a connected Samsung device
2. Read device information
3. Check for firmware updates
4. Download and decrypt firmware if updates are available

Requirements:
- pyserial package installed
- Samsung USB drivers (Windows)
- Samsung device connected in MTP mode

Copyright (c) 2024 nanosamfw contributors
SPDX-License-Identifier: MIT
"""

from device import DeviceNotFoundError, read_device_info
from download import check_firmware, download_and_decrypt


def main() -> None:
    """Main execution function."""
    print("=" * 60)
    print("Samsung Device Detection & Firmware Download")
    print("=" * 60)
    print()

    # Step 1: Detect and read device information
    try:
        print("🔍 Detecting Samsung device...")
        device = read_device_info()
        print("✅ Device detected!")
        print()
        print(device)
        print()

    except DeviceNotFoundError:
        print("❌ Error: No Samsung device detected")
        print("   Please ensure your device is:")
        print("   - Connected via USB")
        print("   - In MTP mode")
        print("   - Samsung USB drivers are installed (Windows)")
        return
    except (ImportError, OSError, IOError) as ex:
        print(f"❌ Error reading device: {ex}")
        return

    # Step 2: Check for firmware updates
    print("-" * 60)
    print("🔎 Checking for firmware updates...")
    try:
        latest_version = check_firmware(
            model=device.model, csc=device.region, device_id=device.imei
        )
        print(f"✅ Latest firmware: {latest_version}")
        print()

        # Compare versions
        if latest_version == device.pda_version:
            print("✅ Device is up to date!")
            print(f"   Current version: {device.pda_version}")
            print(f"   Latest version:  {latest_version}")
            return

        # Step 3: Download new firmware
        print("📥 New firmware available!")
        print(f"   Current version: {device.pda_version}")
        print(f"   Latest version:  {latest_version}")
        print()

        response = input("Would you like to download it? (y/n): ").strip().lower()
        if response != "y":
            print("Download cancelled.")
            return

        print()
        print("📥 Downloading and decrypting firmware...")
        firmware, decrypted_path = download_and_decrypt(
            model=device.model, csc=device.region, device_id=device.imei, resume=True
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
