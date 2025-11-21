# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Yannick Locque (yanuino)
"""
FUS package error definitions.

This module defines custom exceptions used across the FUS package. In
particular, DeviceIdError is raised by the device identifier utilities
(e.g. IMEI/TAC validation and autofill) when provided input is invalid.

Exceptions:
    FUSError: Base class for FUS-related errors.
    AuthError: Raised for authentication failures in FUS operations.
    InformError: Raised for protocol or information errors in FUS communication.
    DownloadError: Raised when a firmware download fails or is incomplete.
    DecryptError: Raised when firmware decryption fails.
    DeviceIdError: Raised by fus.deviceid helpers on invalid TAC/IMEI/serial input.
    FOTAError: Base class for FOTA endpoint errors.
    FOTAParsingError: Raised when FOTA XML response parsing fails.
"""


class FUSError(Exception):
    """Base class for FUS-related errors with optional predefined messages."""

    # Error subtypes with built-in messages
    class NoFirmware(Exception):
        """No firmware available for the specified model/region."""

        def __init__(self, model: str = "", region: str = ""):
            msg = "No latest firmware available"
            if model or region:
                msg += f" for {model}/{region}"
            super().__init__(msg)


class AuthError(FUSError): ...


class InformError(FUSError):
    """Raised for protocol or information errors in FUS communication."""

    # Error subtypes with built-in messages
    class MissingStatus(Exception):
        """Missing Status field in inform response."""

        def __init__(self):
            super().__init__("Missing Status field in inform response")

    class BadStatus(Exception):
        """Non-200 status code in inform response."""

        def __init__(self, status: int):
            super().__init__(f"DownloadBinaryInform returned {status}")

    class MissingField(Exception):
        """Required field missing from inform response."""

        def __init__(self, field_name: str):
            super().__init__(f"Missing {field_name} in inform response")

    class DecryptionKeyError(Exception):
        """Could not obtain decryption key from inform response."""

        def __init__(self, model: str = "", region: str = "", device_id: str = ""):
            msg = "Could not obtain decryption key"
            details = []
            if model:
                details.append(f"model={model}")
            if region:
                details.append(f"region={region}")
            if device_id:
                details.append(f"device_id={device_id[:4]}***")
            if details:
                msg += f" ({', '.join(details)})"
            msg += "; check model/region/device_id"
            super().__init__(msg)


class DownloadError(FUSError):
    """Raised when a firmware download fails or is incomplete."""

    # Error subtypes with built-in messages
    class HTTPError(Exception):
        """HTTP error during download."""

        def __init__(self, status_code: int, url: str = ""):
            msg = f"HTTP {status_code} on download"
            if url:
                msg += f": {url}"
            super().__init__(msg)


class DecryptError(FUSError):
    """Raised when firmware decryption fails."""

    # Error subtypes with built-in messages
    class DeviceIdRequired(Exception):
        """Device ID required for ENC4 decryption."""

        def __init__(self):
            super().__init__(
                "Device ID (IMEI or Serial) required for ENC4 key (Samsung requirement)"
            )

    class InvalidBlockSize(Exception):
        """Invalid encrypted file block size."""

        def __init__(self, size: int = 0):
            msg = "Invalid input block size (not multiple of 16)"
            if size:
                msg += f": {size} bytes"
            super().__init__(msg)


class DeviceIdError(FUSError):
    """Raised by fus.deviceid helpers on invalid TAC/IMEI/serial input."""

    # Error subtypes with built-in messages
    class InvalidTAC(Exception):
        """TAC validation failed."""

        def __init__(self, tac: str = ""):
            msg = "TAC must have at least 8 digits"
            if tac:
                msg += f" (got: {tac})"
            super().__init__(msg)


class FOTAError(Exception):
    """Base class for FOTA endpoint errors with optional predefined messages."""

    # Error subtypes with built-in messages
    class ModelOrRegionNotFound(Exception):
        """Model or region not found (HTTP 403)."""

        def __init__(self, model: str = "", region: str = ""):
            msg = "Model or region not found (403)"
            if model or region:
                msg += f": {model}/{region}"
            super().__init__(msg)

    class NoFirmware(Exception):
        """No firmware available in FOTA response."""

        def __init__(self, model: str = "", region: str = ""):
            msg = "No latest firmware available"
            if model or region:
                msg += f" for {model}/{region}"
            super().__init__(msg)


class FOTAParsingError(FOTAError):
    """Raised when FOTA XML response parsing fails.

    Args:
        field: The XML field that failed to parse.
        model: Optional device model for context.
        region: Optional region code for context.
    """

    def __init__(self, field: str = "", model: str = "", region: str = ""):
        msg = "Failed to parse FOTA response"
        if field:
            msg += f": missing or invalid '{field}' field"
        if model or region:
            msg += f" for {model}/{region}"
        super().__init__(msg)
