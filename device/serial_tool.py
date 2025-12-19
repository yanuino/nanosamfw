"""Lightweight serial command helper for Samsung devices.

Provides a simple function to send a command over a serial port and return the
response as text. If no port is provided, the first detected Samsung device in
(download/Odin mode) is used via ``get_first_device``.
"""

from __future__ import annotations

import time
from typing import Optional

import serial

from device.detector import get_first_device
from device.errors import DeviceNotFoundError, DeviceReadError


def send_serial_command(
    command: str | bytes,
    port_name: Optional[str] = None,
    *,
    baudrate: int = 115200,
    timeout: float = 2.0,
    append_crlf: bool = True,
    encoding: str = "utf-8",
) -> str:
    """Send a command over serial and return the response.

    Args:
        command: Command to send. If str, it is encoded with ``encoding``.
        port_name: Serial port name. If None, the first detected Samsung device
            (download mode) is used.
        baudrate: Serial baudrate. Defaults to 115200.
        timeout: Read timeout in seconds. Defaults to 2.0.
        append_crlf: If True and ``command`` is str, appends ``\r\n`` when missing.
        encoding: Encoding used when ``command`` is str. Defaults to UTF-8.

    Returns:
        Response decoded as text (using ``encoding``).

    Raises:
        DeviceNotFoundError: If no device is detected and ``port_name`` is None.
        DeviceReadError: If communication fails or no response is received.
    """
    target_port = port_name
    if target_port is None:
        device = get_first_device()
        target_port = device.port_name

    try:
        cmd_bytes: bytes
        if isinstance(command, str):
            cmd_bytes = command.encode(encoding)
            if append_crlf and not cmd_bytes.endswith(b"\r\n"):
                cmd_bytes += b"\r\n"
        else:
            cmd_bytes = command

        with serial.Serial(
            port=target_port,
            baudrate=baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=timeout,
            write_timeout=timeout,
        ) as port:
            # Clear buffers to avoid mixing old data
            port.reset_input_buffer()
            port.reset_output_buffer()

            # Send command
            port.write(cmd_bytes)
            port.flush()

            # Collect response until timeout with small waits
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
                raise DeviceReadError(f"No response received from device on {target_port}.")
            return response

    except DeviceNotFoundError:
        raise
    except serial.SerialException as ex:
        raise DeviceReadError(f"Serial communication error on {target_port}: {ex}.") from ex
