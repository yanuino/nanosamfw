"""Exception types for device operations.

Copyright (c) 2024 nanosamfw contributors
SPDX-License-Identifier: MIT
"""


class DeviceError(Exception):
    """Base exception for device-related errors."""


class DeviceNotFoundError(DeviceError):
    """Raised when no Samsung devices are detected in MTP or download mode."""


class DeviceATError(DeviceError):
    """Raised for AT-channel communication failures with a device.

    Covers errors related to the AT commands path including:
    - Serial port open/close failures
    - Write errors when sending AT commands
    - Read errors, timeouts, or empty responses
    - Device busy states or unsupported AT command behavior
    - Permission/driver issues
    """


class DeviceOdinError(DeviceError):
    """Raised for Odin (download mode) communication failures.

    Use for DVIF/ODIN commands and download-mode serial interactions when
    devices are expected to be in Odin mode with RTS/CTS enabled.
    """
