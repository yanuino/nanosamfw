"""Odin client for Samsung download mode communication.

This module provides functions and protocol structures for communicating with Samsung
devices in download mode (Odin mode) using the DVIF/LOKE binary protocol.

Based on SharpOdinClient implementation by Gsm Alphabet (https://github.com/Alephgsm/SharpOdinClient)

**Protocol**: Odin/LOKE binary protocol
**Requires**: pyserial, Samsung USB drivers (Windows), device in download mode

Copyright (c) 2024 nanosamfw contributors
SPDX-License-Identifier: MIT
"""

import struct
import time
from dataclasses import dataclass
from typing import Optional

import serial

from device.detector import get_first_device
from device.errors import DeviceOdinError

# Protocol byte sequences
DVIF_COMMAND = bytes([0x44, 0x56, 0x49, 0x46])  # "DVIF" - Get device info
ODIN_COMMAND = bytes([0x4F, 0x44, 0x49, 0x4E])  # "ODIN" - Verify download mode
LOKE_RESPONSE = b"LOKE"  # Expected response for ODIN command


@dataclass
class OdinCommand:
    """Odin/LOKE protocol command structure.

    This represents the 1024-byte command buffer used for all Odin protocol
    operations. The structure matches Samsung's binary protocol.

    Structure (little-endian):
        - Cmd (4 bytes): Command code
        - SeqCmd (4 bytes): Sequence/sub-command
        - BinaryType (4 or 8 bytes): Binary type identifier
        - SizeWritten (4 bytes): Size of data written
        - Unknown (4 bytes): Reserved/unknown field
        - DeviceId (4 bytes): Device type identifier
        - Identifier (4 bytes): Partition identifier
        - SessionEnd (4 bytes): Session end flag
        - EfsClear (4 bytes): EFS clear flag
        - BootUpdate (4 bytes): Boot update flag

    Common command codes:
        - 0x64 (100): LOKE_Initialize
        - 0x65 (101): Read/Write PIT
        - 0x66 (102): Flash data
        - 0x67 (103): Reboot to normal mode
        - 0x69 (105): Additional initialization
    """

    cmd: int
    seq_cmd: int = 0
    binary_type: int = 0
    size_written: int = 0
    unknown: int = 0
    device_id: int = 0
    identifier: int = 0
    session_end: int = 0
    efs_clear: int = 0
    boot_update: int = 0

    def to_bytes(self) -> bytes:
        """Serialize command to 1024-byte buffer.

        Returns:
            1024-byte buffer in Odin protocol format
        """
        buffer = bytearray(1024)

        # Pack header fields (little-endian)
        struct.pack_into("<I", buffer, 0, self.cmd)
        struct.pack_into("<I", buffer, 4, self.seq_cmd)

        # BinaryType is 8 bytes for cmd 0x64 (100), else 4 bytes
        if self.cmd == 100:
            struct.pack_into("<Q", buffer, 8, self.binary_type)
        else:
            struct.pack_into("<I", buffer, 8, self.binary_type)
            struct.pack_into("<I", buffer, 12, self.size_written)

        struct.pack_into("<I", buffer, 16, self.unknown)
        struct.pack_into("<I", buffer, 20, self.device_id)
        struct.pack_into("<I", buffer, 24, self.identifier)
        struct.pack_into("<I", buffer, 28, self.session_end)
        struct.pack_into("<I", buffer, 32, self.efs_clear)
        struct.pack_into("<I", buffer, 36, self.boot_update)

        return bytes(buffer)

    @classmethod
    def from_bytes(cls, data: bytes) -> "OdinCommand":
        """Parse command from response buffer.

        Args:
            data: Response buffer (minimum 8 bytes)

        Returns:
            Parsed command

        Raises:
            ValueError: If data is too short
        """
        if len(data) < 8:
            raise ValueError(f"Response too short: {len(data)} bytes (need 8)")

        cmd = struct.unpack_from("<I", data, 0)[0]
        seq_cmd = struct.unpack_from("<I", data, 4)[0]

        return cls(cmd=cmd, seq_cmd=seq_cmd)


def get_variant(response: bytes) -> int:
    """Extract protocol variant from LOKE response.

    The variant determines which initialization sequence to use.

    Args:
        response: 8-byte response from LOKE_Initialize

    Returns:
        Protocol variant (2, 3, 4, or 5)

    Raises:
        ValueError: If response is invalid
    """
    if len(response) < 8:
        raise ValueError(f"Invalid response length: {len(response)}")

    # Variant is in bits 16-31 of second dword
    value = struct.unpack_from("<I", response, 4)[0]
    variant = (value & 0xFFFF0000) >> 16
    return variant


@dataclass(frozen=True)
class OdinDeviceInfo:
    """Device information from Odin download mode (DVIF protocol).

    This is returned by sending DVIF command (0x44,0x56,0x49,0x46) to a device
    in download mode. Response format is semicolon-separated key=value pairs.

    Example response:
        @capa=1;product=GT-I9300;model=GT-I9300;fwver=I9300XXEMK4;...#

    Attributes:
        capa: Device capability number
        product: Product identifier
        model: Model number
        fwver: Firmware version string
        vendor: Vendor identifier
        sales: Sales code (region)
        ver: Build number
        did: Device ID
        un: Unique number
        tmu_temp: TMU temperature sensor value
        prov: Provision status
        raw_response: Original raw response from device
    """

    capa: Optional[str] = None
    product: Optional[str] = None
    model: Optional[str] = None
    fwver: Optional[str] = None
    vendor: Optional[str] = None
    sales: Optional[str] = None
    ver: Optional[str] = None
    did: Optional[str] = None
    un: Optional[str] = None
    tmu_temp: Optional[str] = None
    prov: Optional[str] = None
    raw_response: str = ""

    def __str__(self) -> str:
        """Return human-readable device information."""
        lines = []
        if self.model:
            lines.append(f"Model: {self.model}")
        if self.product:
            lines.append(f"Product: {self.product}")
        if self.fwver:
            lines.append(f"Firmware: {self.fwver}")
        if self.sales:
            lines.append(f"Sales Code: {self.sales}")
        if self.un:
            lines.append(f"Unique ID: {self.un}")
        return "\n".join(lines) if lines else "No device info"


def parse_dvif_response(response: str) -> OdinDeviceInfo:
    """Parse DVIF response into OdinDeviceInfo.

    The response format is: @key1=value1;key2=value2;...#

    Args:
        response: Raw DVIF response string

    Returns:
        Parsed device information

    Raises:
        ValueError: If response format is invalid
    """
    # Remove @ and # markers
    cleaned = response.replace("#", "").replace("@", "")

    if not cleaned:
        raise ValueError("Empty DVIF response")

    # Parse key=value pairs
    data = {}
    for pair in cleaned.split(";"):
        pair = pair.strip()
        if not pair or "=" not in pair:
            continue

        key, value = pair.split("=", 1)
        key = key.strip().lower()
        value = value.strip()

        if key and value:
            data[key] = value

    return OdinDeviceInfo(
        capa=data.get("capa"),
        product=data.get("product"),
        model=data.get("model"),
        fwver=data.get("fwver"),
        vendor=data.get("vendor"),
        sales=data.get("sales"),
        ver=data.get("ver"),
        did=data.get("did"),
        un=data.get("un"),
        tmu_temp=data.get("tmu_temp"),
        prov=data.get("prov"),
        raw_response=response,
    )


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
