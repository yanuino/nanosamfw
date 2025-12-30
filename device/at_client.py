"""AT client for Samsung devices over serial.

Provides utilities to send AT commands and parse device information in
normal/recovery modes. Use Odin protocol for download mode devices.

Copyright (c) 2024 nanosamfw contributors
SPDX-License-Identifier: MIT
"""

import time
from dataclasses import dataclass
from typing import Optional

import serial

from device.detector import get_first_device
from device.errors import DeviceATError


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
        serial_number: Device serial number (SN field)
        lock_status: Device lock status (LOCK field)
    """

    model: str
    firmware_version: str
    sales_code: str
    imei: str
    serial_number: str = ""
    lock_status: str = ""
    aid: str = ""
    cc: str = ""


def send_at_command(
    command: str,
    port_name: Optional[str] = None,
    *,
    timeout: float = 2.0,
    encoding: str = "utf-8",
    expect_ok: bool = True,
) -> str:
    """Send an AT command and return the raw response as text.

    Adds CRLF automatically, handles serial write/read errors, and optionally
    validates presence of "OK" in the response.

    Args:
        command: The AT command to send (e.g., "AT+DEVCONINFO"). CRLF is appended automatically.
        port_name: Serial port name. If None, auto-detects the first Samsung device port.
        timeout: Read/write timeout in seconds.
        encoding: Text encoding for decoding the response.
        expect_ok: If True, raises error when "OK" is not present in the response.

    Returns:
        Raw textual response received from the device.

    Raises:
        DeviceATError: On serial open/write/read failures, timeouts, or missing OK when expected.
    """
    # Auto-detect device if port not specified
    target_port = port_name
    if target_port is None:
        device = get_first_device()
        target_port = device.port_name

    try:
        cmd_bytes = command.encode(encoding)
        if not cmd_bytes.endswith(b"\r\n"):
            cmd_bytes += b"\r\n"

        with serial.Serial(
            port=target_port,
            baudrate=115200,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=timeout,
            write_timeout=timeout,
        ) as port:
            # Clear buffers
            port.reset_input_buffer()
            port.reset_output_buffer()

            # Write command
            try:
                port.write(cmd_bytes)
                port.flush()
            except serial.SerialTimeoutException as ex:
                raise DeviceATError(f"Write timeout on {target_port}: {ex}.") from ex

            # Read until timeout
            response_parts: list[str] = []
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                waiting = port.in_waiting
                if waiting:
                    chunk = port.read(waiting)
                    response_parts.append(chunk.decode(encoding, errors="replace"))
                else:
                    time.sleep(0.05)

            response = "".join(response_parts).strip()
            if not response:
                raise DeviceATError(f"No AT response from device on {target_port}.")
            if expect_ok and "OK" not in response:
                raise DeviceATError(f"AT command did not return OK on {target_port}. Response: {response[:200]}")
            return response

    except serial.SerialException as ex:
        raise DeviceATError(
            f"Serial communication error on {target_port}: {ex}. Verify device is connected and drivers are installed."
        ) from ex


def enter_download_mode(
    port_name: Optional[str] = None,
    *,
    timeout: float = 1.0,
) -> None:
    """Put Samsung device into download mode (Odin mode) using AT command.

    Sends AT+FUS? command which immediately reboots the device into download mode
    and disconnects the serial connection. No response is expected.

    After calling this function, wait a few seconds for the device to reboot,
    then use device.odin_client functions to communicate with it.

    Args:
        port_name: Serial port name (e.g., "COM3" on Windows, "/dev/ttyACM0" on Linux).
            If None, auto-detects the first Samsung device port.
        timeout: Write timeout in seconds (default: 1.0)

    Raises:
        DeviceATError: If serial communication fails
        DeviceNotFoundError: If auto-detection fails

    Example:
        >>> from device import enter_download_mode, read_device_info
        >>> enter_download_mode("COM3")
        >>> time.sleep(3)  # Wait for reboot
        >>> info = read_device_info("COM3")  # Now use Odin protocol
    """
    # Auto-detect device if port not specified
    target_port = port_name
    if target_port is None:
        device = get_first_device()
        target_port = device.port_name

    try:
        cmd_bytes = b"AT+FUS?\r\n"

        with serial.Serial(
            port=target_port,
            baudrate=115200,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=timeout,
            write_timeout=timeout,
        ) as port:
            # Clear buffers
            port.reset_input_buffer()
            port.reset_output_buffer()

            # Write command - device will immediately disconnect
            try:
                port.write(cmd_bytes)
                port.flush()
            except serial.SerialTimeoutException as ex:
                raise DeviceATError(f"Write timeout on {target_port}: {ex}.") from ex

            # Device reboots immediately, no response expected

    except serial.SerialException as ex:
        raise DeviceATError(
            f"Serial communication error on {target_port}: {ex}. Verify device is connected and drivers are installed."
        ) from ex


def read_device_info_at(
    port_name: Optional[str] = None,
    *,
    timeout: float = 2.0,
) -> ATDeviceInfo:
    """Read device information from Samsung device using AT commands.

    Sends AT+DEVCONINFO command to device and parses the response.

    Args:
        port_name: Serial port name (e.g., "COM3" on Windows, "/dev/ttyACM0" on Linux).
        timeout: Read timeout in seconds

    Returns:
        Device information from AT command response

    Raises:
        DeviceATError: If serial communication fails or AT command returns no data
        DeviceNotFoundError: If auto-detection fails
    """
    response = send_at_command("AT+DEVCONINFO", port_name=port_name, timeout=timeout)
    return _parse_at_response(response, port_name or "(auto)")


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
        DeviceATError: If response format is invalid
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

            # SN field (serial number)
            serial_number = info_dict.get("SN", "")

            # LOCK field (lock status)
            lock_status = info_dict.get("LOCK", "")

            # AID field (Account/Android ID depending on device)
            aid = info_dict.get("AID", "")

            # CC field (Country Code)
            cc = info_dict.get("CC", "")

            if model and firmware_version and sales_code:
                return ATDeviceInfo(
                    model=model,
                    firmware_version=firmware_version,
                    sales_code=sales_code,
                    imei=imei,
                    serial_number=serial_number,
                    lock_status=lock_status,
                    aid=aid,
                    cc=cc,
                )

    raise DeviceATError(f"Failed to parse AT response from {port_name}. Response: {response[:200]}")
