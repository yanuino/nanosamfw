# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Yannick Locque (yanuino)

import random
from .errors import DeviceIdError

def luhn_checksum(imei_without_cd: str) -> int:
    s, tmp = 0, imei_without_cd + "0"
    parity = len(tmp) % 2
    for idx, ch in enumerate(tmp):
        d = int(ch)
        if idx % 2 == parity:
            d *= 2
            if d > 9: d -= 9
        s += d
    return (10 - (s % 10)) % 10

def autofill_imei(tac: str) -> str:
    if not tac.isdecimal() or len(tac) < 8:
        raise DeviceIdError("TAC must have at least 8 digits")
    if len(tac) >= 15:
        return tac[:15]
    missing = 14 - len(tac)
    rnd = f"{random.randint(0, 10**missing - 1):0{missing}d}"
    core = tac + rnd
    return core + str(luhn_checksum(core))

def validate_serial(serial: str) -> bool:
    return bool(serial) and (1 <= len(serial) <= 35) and serial.isalnum()

def validate_imei(imei: str) -> bool:
    """
    Validate a full 15-digit IMEI using the Luhn checksum.

    Rules enforced here:
    - must be all digits
    - must be exactly 15 characters long
    - last digit (check digit) must match Luhn checksum computed over the first 14 digits

    Returns True only for a valid 15-digit IMEI.
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
    return command == "download" or (command == "decrypt" and enc_ver == 4)