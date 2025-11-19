"""Samsung device detection and information reading.

This package provides functionality to detect Samsung devices connected in MTP mode
and read device information (model, IMEI, firmware versions) via AT commands.

**Platform Requirements:**
- Cross-platform support (Windows, Linux, macOS)
- Samsung USB drivers installed (Windows)
- Python package: pyserial

**Installation:**

.. code-block:: bash

    pip install pyserial

**Usage:**

Auto-detect and read device info:

.. code-block:: python

    from device import read_device_info

    try:
        info = read_device_info()
        print(f"Model: {info.model}")
        print(f"IMEI: {info.imei}")
        print(f"Firmware: {info.pda_version}")
    except Exception as ex:
        print(f"Error: {ex}")

Manual device detection:

.. code-block:: python

    from device import detect_samsung_devices, read_device_info

    devices = detect_samsung_devices()
    for device in devices:
        print(f"Found: {device.device_name} on {device.port_name}")
        info = read_device_info(device.port_name)
        print(info)

**Integration with nanosamfw:**

Use detected device information for firmware downloads:

.. code-block:: python

    from device import read_device_info
    from download import check_firmware, download_and_decrypt

    # Read from connected device
    device_info = read_device_info()

    # Check latest firmware
    firmware_info = check_firmware(
        model=device_info.model,
        csc=device_info.region,
        device_id=device_info.imei
    )

    # Download if newer version available
    if firmware_info.latest_fw_version != device_info.pda_version:
        download_and_decrypt(
            model=device_info.model,
            csc=device_info.region,
            device_id=device_info.imei
        )

Copyright (c) 2024 nanosamfw contributors
SPDX-License-Identifier: MIT
"""

from device.detector import DetectedDevice, detect_samsung_devices, get_first_device
from device.errors import DeviceError, DeviceNotFoundError, DeviceParseError, DeviceReadError
from device.models import DeviceInfo
from device.reader import read_device_info

__all__ = [
    # Main functions
    "detect_samsung_devices",
    "get_first_device",
    "read_device_info",
    # Models
    "DeviceInfo",
    "DetectedDevice",
    # Errors
    "DeviceError",
    "DeviceNotFoundError",
    "DeviceReadError",
    "DeviceParseError",
]
