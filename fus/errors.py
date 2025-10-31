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
"""


class FUSError(Exception): ...


class AuthError(FUSError): ...


class InformError(FUSError): ...


class DownloadError(FUSError): ...


class DecryptError(FUSError): ...


class DeviceIdError(FUSError): ...
