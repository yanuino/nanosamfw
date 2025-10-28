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

def autofill_imei(imei: str) -> str:
    if not imei.isdecimal() or len(imei) < 8:
        raise DeviceIdError("IMEI must have at least 8 digits")
    if len(imei) >= 15:
        return imei[:15]
    missing = 14 - len(imei)
    rnd = f"{random.randint(0, 10**missing - 1):0{missing}d}"
    core = imei + rnd
    return core + str(luhn_checksum(core))

def validate_serial(serial: str) -> bool:
    return bool(serial) and (1 <= len(serial) <= 35) and serial.isalnum()

def is_device_id_required(command: str, enc_ver: int | None) -> bool:
    return command == "download" or (command == "decrypt" and enc_ver == 4)