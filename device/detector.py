"""Samsung device detection via serial port enumeration.

This module provides functions to detect Samsung devices connected in download mode
(Odin mode) by enumerating serial ports for Samsung Mobile USB Modems.

Uses pyserial's list_ports for cross-platform compatibility.
Requires Samsung USB drivers installed on Windows.

Based on SharpOdinClient implementation by Gsm Alphabet.

Copyright (c) 2024 nanosamfw contributors
SPDX-License-Identifier: MIT
"""

import re
from typing import NamedTuple, Optional

from serial.tools import list_ports

from device.errors import DeviceNotFoundError


class DetectedDevice(NamedTuple):
    """Information about a detected Samsung device in download mode.

    Attributes:
        port_name: Serial port device ID (e.g., COM3 on Windows, /dev/ttyACM0 on Linux)
        device_name: Full device description from port enumeration
        manufacturer: Device manufacturer string (if available)
        product: Product description string (if available)
        vid: USB Vendor ID (4-char hex string, if available)
        pid: USB Product ID (4-char hex string, if available)
    """

    port_name: str
    device_name: str
    manufacturer: str
    product: str
    vid: Optional[str] = None
    pid: Optional[str] = None


def _extract_vid_pid(hwid: str) -> tuple[Optional[str], Optional[str]]:
    """Extract VID and PID from hardware ID string.

    Args:
        hwid: Hardware ID string (e.g., "USB VID:PID=04E8:685D")

    Returns:
        Tuple of (VID, PID) as 4-char hex strings, or (None, None) if not found
    """
    vid_match = re.search(r"VID[_:]([0-9A-F]{4})", hwid, re.IGNORECASE)
    pid_match = re.search(r"PID[_:]([0-9A-F]{4})", hwid, re.IGNORECASE)

    vid = vid_match.group(1).upper() if vid_match else None
    pid = pid_match.group(1).upper() if pid_match else None

    return vid, pid


def detect_download_mode_devices() -> list[DetectedDevice]:
    """Detect Samsung devices connected in download mode (Odin mode).

    Download mode devices identify as "SAMSUNG MOBILE USB MODEM" in their
    device description. This is different from MTP mode devices.

    Uses pyserial's list_ports to enumerate serial ports.

    Returns:
        List of detected download mode devices. Empty if no devices found.
    """
    devices = []

    for port in list_ports.comports():
        # Check device description for download mode signature
        description = port.description or ""
        manufacturer = port.manufacturer or ""
        product = port.product or ""

        # Download mode devices have specific signature
        is_download_mode = "samsung mobile usb modem" in description.lower()

        if is_download_mode and port.device:
            # Extract VID/PID from hardware ID
            hwid = port.hwid or ""
            vid, pid = _extract_vid_pid(hwid)

            devices.append(
                DetectedDevice(
                    port_name=port.device,
                    device_name=description,
                    manufacturer=manufacturer,
                    product=product,
                    vid=vid,
                    pid=pid,
                )
            )

    return devices


def detect_samsung_devices() -> list[DetectedDevice]:
    """Detect all Samsung devices (alias for detect_download_mode_devices).

    This function is kept for backward compatibility but now detects
    download mode devices only.

    Returns:
        List of detected devices with port information. Empty if no devices found.
    """
    return detect_download_mode_devices()


def get_first_device() -> DetectedDevice:
    """Get the first detected Samsung device in download mode.

    Convenience function for single-device scenarios.

    Returns:
        First detected device

    Raises:
        DeviceNotFoundError: If no Samsung devices are connected in download mode
    """
    devices = detect_download_mode_devices()
    if not devices:
        raise DeviceNotFoundError(
            "No Samsung devices in download mode detected. "
            "Ensure device is connected in download mode (Odin mode) "
            "and Samsung USB drivers are installed (Windows). "
            "To enter download mode: Power off device, then hold Volume Down + Home + Power."
        )
    return devices[0]
