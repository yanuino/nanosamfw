"""Read device information via Odin protocol over serial port.

This module communicates with Samsung devices in download mode (Odin mode)
using the DVIF (0x44,0x56,0x49,0x46) byte protocol to retrieve firmware version,
model, and device info.

Based on SharpOdinClient implementation by Gsm Alphabet.

**Protocol**: Odin/LOKE binary protocol
**Requires**: pyserial, Samsung USB drivers (Windows), device in download mode

Copyright (c) 2024 nanosamfw contributors
SPDX-License-Identifier: MIT
"""

import time
from typing import Optional

import serial

from device.detector import get_first_device
from device.errors import DeviceOdinError
from device.protocol import DVIF_COMMAND, LOKE_RESPONSE, ODIN_COMMAND, OdinDeviceInfo, parse_dvif_response


def is_odin_mode(
    port_name: str,
    *,
    timeout: float = 2.0,
) -> bool:
    """Check if device is in Odin download mode.

    Sends ODIN command (0x4F,0x44,0x49,0x4E) and checks for LOKE response.

    Args:
        port_name: Serial port name (e.g., "COM3" on Windows, "/dev/ttyACM0" on Linux)
        timeout: Read timeout in seconds

    Returns:
        True if device responds with LOKE, False otherwise

    Raises:
        DeviceOdinError: If serial communication fails
    """
    try:
        with serial.Serial(
            port=port_name,
            baudrate=115200,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=timeout,
            rtscts=True,  # RTS/CTS hardware flow control
        ) as port:
            # Clear input buffer
            port.reset_input_buffer()

            # Send ODIN command
            port.write(ODIN_COMMAND)
            time.sleep(0.4)  # Wait for response

            # Read response
            bytes_waiting = port.in_waiting
            if bytes_waiting > 0:
                response = port.read(bytes_waiting)
                return LOKE_RESPONSE in response
            return False

    except serial.SerialException as ex:
        raise DeviceOdinError(
            f"Serial communication error on {port_name}: {ex}. "
            "Verify device is in download mode and Samsung USB drivers are installed."
        ) from ex


def read_device_info(
    port_name: Optional[str] = None,
    *,
    timeout: float = 2.0,
    port_instance: Optional[serial.Serial] = None,
) -> OdinDeviceInfo:
    """Read device information from Samsung device in download mode.

    Sends DVIF command (0x44,0x56,0x49,0x46) to device in Odin mode
    and parses the response.

    The device must be in download mode (Odin mode) for this to work.
    To enter download mode: Power off device, then hold Volume Down + Home + Power.

    IMPORTANT: If calling both is_odin_mode() and read_device_info(), pass an opened
    port via port_instance to keep the connection alive between operations.

    Args:
        port_name: Serial port name (e.g., "COM3" on Windows, "/dev/ttyACM0" on Linux).
            If None, auto-detects first device in download mode. Ignored if port_instance provided.
        timeout: Read timeout in seconds
        port_instance: Optional pre-opened serial port. If provided, port will NOT be closed.

    Returns:
        Device information from Odin protocol

    Raises:
        DeviceOdinError: If serial communication fails or device not in Odin mode
        ValueError: If response cannot be parsed
        DeviceNotFoundError: If auto-detection fails
    """
    # Use provided port or auto-detect/open new one
    if port_instance is not None:
        port = port_instance
        should_close = False
    else:
        # Auto-detect device if port not specified
        if port_name is None:
            device = get_first_device()
            port_name = device.port_name

        port = serial.Serial(
            port=port_name,
            baudrate=115200,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=timeout,
            rtscts=True,
        )
        # Disable DTR and RTS after opening (may reset device if done before)
        port.dtr = False
        port.rts = False
        should_close = True

    try:
        # Clear input buffer
        port.reset_input_buffer()

        # Send DVIF command
        port.write(DVIF_COMMAND)
        time.sleep(0.4)  # Wait for device response

        # Read response
        bytes_waiting = port.in_waiting
        if bytes_waiting > 0:
            raw_response = port.read(bytes_waiting)
            response = raw_response.decode("utf-8", errors="replace")
        else:
            response = ""

        if not response:
            port_desc = port_name if port_name else port.port
            raise DeviceOdinError(
                f"No response from device on {port_desc}. "
                "Ensure device is in download mode (Odin mode). "
                "To enter download mode: Power off device, "
                "then hold Volume Down + Home + Power."
            )

        # Parse DVIF response
        return parse_dvif_response(response)

    except serial.SerialException as ex:
        port_desc = port_name if port_name else port.port
        raise DeviceOdinError(
            f"Serial communication error on {port_desc}: {ex}. "
            "Verify device is in download mode and Samsung USB drivers are installed."
        ) from ex
    finally:
        # Only close if we created the port
        if should_close and port.is_open:
            port.close()
