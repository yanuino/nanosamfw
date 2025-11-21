"""Data models for Samsung device information.

This module defines the data structures for device information.

.. deprecated::
    DeviceInfo (AT command format) is deprecated. The package now uses
    Odin download mode protocol. Use OdinDeviceInfo from device.protocol instead.

Copyright (c) 2024 nanosamfw contributors
SPDX-License-Identifier: MIT
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class DeviceInfo:
    """Samsung device information (DEPRECATED - kept for backward compatibility).

    .. deprecated::
        This class was used with AT commands for MTP mode devices.
        The package now uses Odin download mode protocol.
        Use OdinDeviceInfo from device.protocol instead.

    All fields are extracted from the AT+DEVCONINFO response which follows
    the pattern: MN(model);BASE(base);VER(pda/csc/modem/etc);PRD(product);
    SN(serial);IMEI(imei);UN(un).

    Attributes:
        model: Device model code (e.g., SM-G991B)
        device_name: Device marketing name (typically same as model)
        pda_version: PDA firmware version
        csc_version: CSC (Country Specific Code) version
        modem_version: Modem/baseband firmware version
        region: 3-character CSC region code
        serial_number: Device serial number
        imei: International Mobile Equipment Identity
        unique_number: Samsung unique number (UN)
    """

    model: str
    device_name: str
    pda_version: str
    csc_version: str
    modem_version: str
    region: str
    serial_number: str
    imei: str
    unique_number: str

    def __str__(self) -> str:
        """Return human-readable device information."""
        return (
            f"{self.model} ({self.device_name})\n"
            f"  PDA: {self.pda_version}\n"
            f"  CSC: {self.csc_version} ({self.region})\n"
            f"  Modem: {self.modem_version}\n"
            f"  IMEI: {self.imei}\n"
            f"  S/N: {self.serial_number}\n"
            f"  UN: {self.unique_number}"
        )
