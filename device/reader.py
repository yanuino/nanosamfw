"""Read device information via AT commands over serial port.

This module communicates with Samsung devices in MTP mode using AT commands
to retrieve firmware version, IMEI, serial number, and other device information.

Requires pyserial and Samsung USB drivers (Windows).

Copyright (c) 2024 nanosamfw contributors
SPDX-License-Identifier: MIT
"""

import re
import time
from typing import Optional

import serial

from device.detector import get_first_device
from device.errors import DeviceParseError, DeviceReadError
from device.models import DeviceInfo

# AT+DEVCONINFO response pattern from Samsung devices
_AT_RESPONSE_PATTERN = re.compile(
    r"MN\((.*?)\);BASE\((.*?)\);VER\((.*?)/(.*?)/(.*?)/(.*?)\);"
    r"HIDVER\(.*?\);MNC\(.*?\);MCC\(.*?\);PRD\((.*?)\);.*?"
    r"SN\((.*?)\);IMEI\((.*?)\);UN\((.*?)\);"
)


def _parse_at_response(response: str) -> DeviceInfo:
    """Parse AT+DEVCONINFO response into DeviceInfo.

    Args:
        response: Raw AT command response string

    Returns:
        Parsed device information

    Raises:
        DeviceParseError: If response doesn't match expected pattern
    """
    match = _AT_RESPONSE_PATTERN.search(response)
    if not match:
        raise DeviceParseError(
            f"Could not parse AT response. Expected pattern not found in: {response[:200]}"
        )

    groups = match.groups()
    if len(groups) < 10:
        raise DeviceParseError(
            f"AT response matched but insufficient groups. Got {len(groups)}, expected 10"
        )

    # Extract 3-char region code from product field (last 3 characters)
    product = groups[6]
    region = product[-3:] if len(product) >= 3 else product

    return DeviceInfo(
        model=groups[0],
        device_name=groups[0],  # Samsung typically uses same value
        pda_version=groups[2],
        csc_version=groups[3],
        modem_version=groups[4],
        region=region,
        serial_number=groups[7],
        imei=groups[8],
        unique_number=groups[9],
    )


def read_device_info(
    port_name: Optional[str] = None,
    *,
    timeout: float = 2.0,
    baud_rate: int = 19200,
) -> DeviceInfo:
    """Read device information from Samsung device via AT commands.

    Opens serial connection to device, sends AT+DEVCONINFO command,
    and parses the response.

    Args:
        port_name: Serial port name (e.g., "COM3" on Windows, "/dev/ttyACM0" on Linux).
            If None, auto-detects first device.
        timeout: Read timeout in seconds
        baud_rate: Serial communication baud rate (default: 19200)

    Returns:
        Device information

    Raises:
        DeviceReadError: If serial communication fails or device is busy
        DeviceParseError: If response cannot be parsed
        DeviceNotFoundError: If auto-detection fails
    """

    # Auto-detect device if port not specified
    if port_name is None:
        device = get_first_device()
        port_name = device.port_name

    try:
        with serial.Serial(
            port=port_name,
            baudrate=baud_rate,
            bytesize=serial.EIGHTBITS,
            timeout=timeout,
        ) as port:
            # Send AT command
            port.write(b"AT+DEVCONINFO\r\n")
            time.sleep(1)  # Wait for device response

            # Read response
            raw_response = port.read_all()
            if raw_response is None:
                raw_response = b""
            response = raw_response.decode("utf-8", errors="replace")

            if not response:
                raise DeviceReadError(
                    f"No response from device on {port_name}. "
                    "Check device connection and driver installation."
                )

            if "BUSY" in response:
                raise DeviceReadError(
                    f"Device on {port_name} is busy. Try again or restart device."
                )

            return _parse_at_response(response)

    except serial.SerialException as ex:
        raise DeviceReadError(
            f"Serial communication error on {port_name}: {ex}. "
            "Verify port name and Samsung USB drivers are installed."
        ) from ex
