# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Yannick Locque (yanuino)
"""
Device identifier helpers for FUS interactions.

Provides IMEI Luhn checksum computation, TAC-based IMEI autofill, and
validation helpers for serial numbers and IMEIs.

Functions:
- luhn_checksum: compute Luhn check digit for a 14-digit IMEI core.
- autofill_imei: complete a TAC to a full 15-digit IMEI (random fill + Luhn).
- validate_serial: basic alphanumeric serial validation.
- validate_imei: full 15-digit IMEI validation using Luhn.
- is_device_id_required: policy for when a device id is required by commands.
"""

import random

from .errors import DeviceIdError


def luhn_checksum(imei_without_cd: str) -> int:
    """
    Compute the Luhn check digit for the provided IMEI core.

    Args:
        imei_without_cd: IMEI digits excluding the check digit (typically 14 digits).

    Returns:
        The single-digit Luhn checksum as an int.
    """
    s, tmp = 0, imei_without_cd + "0"
    parity = len(tmp) % 2
    for idx, ch in enumerate(tmp):
        d = int(ch)
        if idx % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        s += d
    return (10 - (s % 10)) % 10


def autofill_imei(tac: str) -> str:
    """
    Build a full 15-digit IMEI from a TAC by filling missing digits and appending Luhn.

    Args:
        tac: TAC prefix (must be numeric and at least 8 digits).

    Returns:
        A 15-digit IMEI string.

    Raises:
        DeviceIdError: If TAC is not numeric or shorter than 8 digits.
    """
    if not tac.isdecimal() or len(tac) < 8:
        raise DeviceIdError.InvalidTAC(tac)
    if len(tac) >= 15:
        return tac[:15]
    missing = 14 - len(tac)
    rnd = f"{random.randint(0, 10**missing - 1):0{missing}d}"
    core = tac + rnd
    return core + str(luhn_checksum(core))


def validate_serial(serial: str) -> bool:
    """
    Validate a device serial number.

    Args:
        serial: Serial string to validate.

    Returns:
        True if serial is non-empty, alphanumeric and length between 1 and 35.
    """
    return bool(serial) and (1 <= len(serial) <= 35) and serial.isalnum()


def validate_imei(imei: str) -> bool:
    """
    Validate a full 15-digit IMEI using the Luhn checksum.

    Args:
        imei: IMEI string to validate.

    Returns:
        True if IMEI is numeric, exactly 15 digits, and has a correct Luhn check digit.
    """
    if not imei or not imei.isdecimal():
        return False
    if len(imei) != 15:
        return False
    try:
        check_digit = int(imei[14])
    except ValueError:
        return False
    return luhn_checksum(imei[:14]) == check_digit


def is_device_id_required(command: str, enc_ver: int | None) -> bool:
    """
    Policy deciding whether a device id is required for an operation.

    Args:
        command: Command name (e.g. "download", "decrypt").
        enc_ver: Encryption version (None if unknown).

    Returns:
        True if the command requires a device id (download always, decrypt only for ENC4).
    """
    return command == "download" or (command == "decrypt" and enc_ver == 4)
