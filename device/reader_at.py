"""Read device information via AT commands over serial port.

This module communicates with Samsung devices using AT commands to retrieve
firmware version, model, and device information. Works with devices in normal mode
or recovery mode that respond to AT commands.

Copyright (c) 2024 nanosamfw contributors
SPDX-License-Identifier: MIT
"""

import time
from dataclasses import dataclass
from typing import Optional

import serial

from device.detector import get_first_device
from device.errors import DeviceReadError


@dataclass(frozen=True)
class ATDeviceInfo:
    """Device information from AT commands.

    Simplified device info structure for AT+DEVCONINFO responses.
    For more detailed information, use Odin protocol (OdinDeviceInfo).

    Attributes:
        model: Device model code (e.g., SM-G991B)
        firmware_version: Full firmware version string (PDA/CSC/MODEM/BOOTLOADER)
        sales_code: 3-character CSC/region code (e.g., XAA, DBT)
        imei: International Mobile Equipment Identity (15 digits)
    """

    model: str
    firmware_version: str
    sales_code: str
    imei: str


def read_device_info_at(
    port_name: Optional[str] = None,
    *,
    timeout: float = 2.0,
) -> ATDeviceInfo:
    """Read device information from Samsung device using AT commands.

    Sends AT+DEVCONINFO command to device and parses the response.

    Args:
        port_name: Serial port name (e.g., "COM3" on Windows, "/dev/ttyACM0" on Linux).
            If None, auto-detects first device.
        timeout: Read timeout in seconds

    Returns:
        Device information from AT command response

    Raises:
        DeviceReadError: If serial communication fails or AT command returns no data
        DeviceNotFoundError: If auto-detection fails
    """
    # Auto-detect device if port not specified
    if port_name is None:
        device = get_first_device()
        port_name = device.port_name

    try:
        with serial.Serial(
            port=port_name,
            baudrate=115200,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=timeout,
        ) as port:
            # Clear buffers
            port.reset_input_buffer()
            port.reset_output_buffer()

            # Send AT command to get device info
            command = b"AT+DEVCONINFO\r\n"
            port.write(command)
            time.sleep(0.3)  # Wait for response

            # Read response
            response = ""
            while port.in_waiting > 0:
                chunk = port.read(port.in_waiting)
                response += chunk.decode("utf-8", errors="replace")
                time.sleep(0.1)

            if not response or "OK" not in response:
                raise DeviceReadError(
                    f"No valid AT response from device on {port_name}. "
                    "Device may not support AT commands or is in wrong mode."
                )

            # Parse response
            return _parse_at_response(response, port_name)

    except serial.SerialException as ex:
        raise DeviceReadError(
            f"Serial communication error on {port_name}: {ex}. " "Verify device is connected and drivers are installed."
        ) from ex


def _parse_at_response(response: str, port_name: str) -> ATDeviceInfo:
    """Parse AT+DEVCONINFO response into ATDeviceInfo.

    Expected format:
    +DEVCONINFO: MN(model);BASE(base);VER(pda/csc/modem/etc);PRD(product);...

    Args:
        response: Raw AT command response
        port_name: Port name for error messages

    Returns:
        Parsed device information

    Raises:
        DeviceReadError: If response format is invalid
    """
    # Look for +DEVCONINFO line
    for line in response.split("\n"):
        line = line.strip()
        if line.startswith("+DEVCONINFO:"):
            # Extract data after colon
            data = line.split(":", 1)[1].strip()

            # Parse key-value pairs: KEY(value);KEY(value);...
            info_dict = {}
            for pair in data.split(";"):
                pair = pair.strip()
                if "(" in pair and ")" in pair:
                    key = pair.split("(")[0].strip()
                    value = pair.split("(", 1)[1].rsplit(")", 1)[0].strip()
                    info_dict[key] = value

            # Extract required fields
            model = info_dict.get("MN", "")

            # VER field contains: PDA/CSC/MODEM/BOOTLOADER (full version)
            firmware_version = info_dict.get("VER", "")

            # PRD field is the sales/region code
            sales_code = info_dict.get("PRD", "")

            # IMEI field
            imei = info_dict.get("IMEI", "")

            if model and firmware_version and sales_code:
                return ATDeviceInfo(
                    model=model,
                    firmware_version=firmware_version,
                    sales_code=sales_code,
                    imei=imei,
                )

    raise DeviceReadError(f"Failed to parse AT response from {port_name}. " f"Response: {response[:200]}")
