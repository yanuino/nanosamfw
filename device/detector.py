"""Samsung device detection via serial port enumeration.

This module provides functions to detect Samsung devices connected in MTP mode
by enumerating serial ports for Samsung USB modems.

Uses pyserial's list_ports for cross-platform compatibility.
Requires Samsung USB drivers installed on Windows.

Copyright (c) 2024 nanosamfw contributors
SPDX-License-Identifier: MIT
"""

from typing import NamedTuple

from serial.tools import list_ports

from device.errors import DeviceNotFoundError


class DetectedDevice(NamedTuple):
    """Information about a detected Samsung device.

    Attributes:
        port_name: Serial port device ID (e.g., COM3 on Windows, /dev/ttyACM0 on Linux)
        device_name: Full device description from port enumeration
        manufacturer: Device manufacturer string (if available)
        product: Product description string (if available)
    """

    port_name: str
    device_name: str
    manufacturer: str
    product: str


def detect_samsung_devices() -> list[DetectedDevice]:
    """Detect all Samsung devices connected in MTP mode.

    Uses pyserial's list_ports to enumerate serial ports and identify
    Samsung Mobile USB Modems by checking device description and manufacturer.

    Returns:
        List of detected devices with port information. Empty if no devices found.
    """
    devices = []

    for port in list_ports.comports():
        # Check if this is a Samsung device by examining description and manufacturer
        description = port.description or ""
        manufacturer = port.manufacturer or ""
        product = port.product or ""

        # Samsung devices typically have "Samsung" in manufacturer or "SAMSUNG Mobile" in description
        is_samsung = (
            "samsung" in manufacturer.lower()
            or "samsung mobile usb modem" in description.lower()
            or "samsung" in product.lower()
        )

        if is_samsung and port.device:
            devices.append(
                DetectedDevice(
                    port_name=port.device,
                    device_name=description,
                    manufacturer=manufacturer,
                    product=product,
                )
            )

    return devices


def get_first_device() -> DetectedDevice:
    """Get the first detected Samsung device.

    Convenience function for single-device scenarios.

    Returns:
        First detected device

    Raises:
        DeviceNotFoundError: If no Samsung devices are connected
    """
    devices = detect_samsung_devices()
    if not devices:
        raise DeviceNotFoundError(
            "No Samsung devices detected. Ensure device is connected in MTP mode "
            "and Samsung USB drivers are installed (Windows)."
        )
    return devices[0]
