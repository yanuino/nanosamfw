"""Exception types for device operations.

Copyright (c) 2024 nanosamfw contributors
SPDX-License-Identifier: MIT
"""


class DeviceError(Exception):
    """Base exception for device-related errors."""


class DeviceNotFoundError(DeviceError):
    """Raised when no Samsung devices are detected in MTP mode."""


class DeviceReadError(DeviceError):
    """Raised when device information cannot be read via AT commands.

    This can occur due to:
    - Serial port communication failure
    - Device busy (returns BUSY response)
    - Malformed AT command response
    - Permission/driver issues
    """


class DeviceParseError(DeviceError):
    """Raised when AT command response cannot be parsed.

    This indicates the device returned data but in an unexpected format.
    """
