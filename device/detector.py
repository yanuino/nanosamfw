"""Samsung device detection via serial port enumeration.

Detects Samsung devices exposed as USB serial modems using ``serial.tools.list_ports``.
No assumption about MTP vs download mode is made here; callers can decide how to
interact (e.g., AT commands or Odin) after a port is found.

Requires pyserial and Samsung USB drivers on Windows.

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


def detect_samsung_devices() -> list[DetectedDevice]:
    """Detect Samsung devices exposed as USB modems over serial.

    Matches ports whose description contains "SAMSUNG MOBILE USB MODEM".

    Returns:
        List of detected devices. Empty if no devices found.
    """
    devices = []

    for port in list_ports.comports():
        # Check device description for Samsung signature
        description = port.description or ""
        manufacturer = port.manufacturer or ""
        product = port.product or ""

        # Samsung devices have specific signature
        is_samsung_device = "samsung mobile usb modem" in description.lower()

        if is_samsung_device and port.device:
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
            "No Samsung serial devices detected. Ensure the device is connected and USB drivers are installed."
        )
    return devices[0]
