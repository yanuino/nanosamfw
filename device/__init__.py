"""Samsung device detection and information reading.

This package provides functionality to detect Samsung devices in download mode (Odin mode)
and read device information using the Odin binary protocol.

Based on SharpOdinClient implementation by Gsm Alphabet (https://github.com/Alephgsm/SharpOdinClient)

**Platform Requirements:**
- Cross-platform support (Windows, Linux, macOS)
- Samsung USB drivers installed (Windows)
- Python package: pyserial
- Device must be in download mode (Odin mode)

**Entering Download Mode:**

To put a Samsung device into download mode:
1. Power off the device completely
2. Press and hold: Volume Down + Home + Power buttons
3. When warning screen appears, press Volume Up to continue
4. Device should display "Downloading..." screen

**Installation:**

.. code-block:: bash

    pip install pyserial

**Usage:**

Auto-detect and read device info:

.. code-block:: python

    from device import read_device_info, is_odin_mode

    try:
        # Check if device is in Odin mode
        from device import detect_download_mode_devices
        devices = detect_download_mode_devices()

        if devices:
            port = devices[0].port_name
            if is_odin_mode(port):
                info = read_device_info(port)
                print(f"Model: {info.model}")
                print(f"Firmware: {info.fwver}")
                print(f"Sales Code: {info.sales}")
    except Exception as ex:
        print(f"Error: {ex}")

Manual device detection with VID/PID:

.. code-block:: python

    from device import detect_download_mode_devices

    devices = detect_download_mode_devices()
    for device in devices:
        print(f"Found: {device.device_name}")
        print(f"  Port: {device.port_name}")
        print(f"  VID: {device.vid}, PID: {device.pid}")

**Integration with nanosamfw:**

Use detected device information for firmware downloads:

.. code-block:: python

    from device import read_device_info
    from download import check_firmware, download_and_decrypt

    # Read from device in download mode
    device_info = read_device_info()

    # Use sales code as CSC for firmware download
    if device_info.model and device_info.sales:
        firmware_info = check_firmware(
            model=device_info.model,
            csc=device_info.sales,
            device_id=""  # IMEI not available in download mode
        )

**Protocol Details:**

This package implements the Odin/LOKE protocol used by Samsung's Odin flash tool:
- DVIF (0x44,0x56,0x49,0x46): Get device information
- ODIN (0x4F,0x44,0x49,0x4E): Verify Odin mode (expects "LOKE" response)
- Communication at 115200 baud with RTS/CTS flow control

Copyright (c) 2024 nanosamfw contributors
SPDX-License-Identifier: MIT
"""

from device.at_client import ATDeviceInfo, enter_download_mode, read_device_info_at, send_at_command
from device.detector import DetectedDevice, detect_samsung_devices, get_first_device
from device.device_command import enter_odin_mode
from device.errors import DeviceATError, DeviceError, DeviceNotFoundError, DeviceOdinError
from device.odin_client import (
    DVIF_COMMAND,
    LOKE_RESPONSE,
    ODIN_COMMAND,
    OdinCommand,
    OdinDeviceInfo,
    get_variant,
    is_odin_mode,
    parse_dvif_response,
    read_device_info,
)

__all__ = [
    # Main functions - Odin protocol (download mode)
    "detect_samsung_devices",
    "get_first_device",
    "read_device_info",  # Odin/DVIF protocol
    "is_odin_mode",
    "enter_odin_mode",  # Coordinate AT + Odin mode transition
    # AT command functions (normal mode)
    "read_device_info_at",
    "send_at_command",
    "enter_download_mode",
    # Models
    "OdinDeviceInfo",  # Odin protocol result
    "ATDeviceInfo",  # AT command result
    "DetectedDevice",
    "OdinCommand",
    # Protocol constants
    "DVIF_COMMAND",
    "ODIN_COMMAND",
    "LOKE_RESPONSE",
    "get_variant",
    "parse_dvif_response",
    # Errors
    "DeviceError",
    "DeviceNotFoundError",
    "DeviceATError",
    "DeviceOdinError",
]
