# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Vladislav Tislenko (keklick1337)
# Copyright (c) 2025 Yannick Locque (yanuino)

import string, requests, xml.etree.ElementTree as ET
from typing import Optional, Tuple
from .errors import FUSError

"""
FOTA end point and firmware parsing.
"""

def normalize_vercode(vercode: str) -> str:
    """
    Normalize a 3‑ or 4‑part version code to exactly 4 parts.

    :param vercode: e.g. "G900FXXU1ANE2" or "G900F/XXU/1ANE/2"
    :return: 4‑part string
    """
    parts = vercode.split("/")
    if len(parts) == 3:
        parts.append(parts[0])
    if parts[2] == "":
        parts[2] = parts[0]
    return "/".join(parts)

def _read_firmware(firmware: str) -> Tuple[Optional[str], Optional[int], int, int, int]:
    """
    Gets basic information from a firmware string.
    
    :param firmware: Samsung firmware version string
    :return: Tuple containing (bootloader_type, major_version, year, month, minor_version)
    """
    # Default values in case parsing fails
    default_year = 2020
    default_month = 0  # January (0-indexed)
    
    # First normalize to handle both slash-separated and compact formats
    if "/" in firmware:
        # Handle slash-separated format (newer style)
        parts = firmware.split("/")
        pda = parts[0][-6:] if len(parts) >= 1 and len(parts[0]) >= 6 else ""
    else:
        # Handle compact format (older style like N7000XXKKA)
        # Extract the last 6 characters, assuming model prefix varies in length
        pda = firmware[-6:] if len(firmware) >= 6 else firmware
    
    result = [None, None, default_year, default_month, 0]
    
    try:
        # Detect if we're using the newer (R=2018+) or older (A=2001+) scheme
        # This could be based on the year character or device model prefix
        use_new_scheme = ord(pda[3]) >= ord('R') if len(pda) >= 4 else True
        
        if len(pda) >= 6 and pda[0] in ["U", "S"]:
            # Bootloader version (U = Upgrade, S = Security)
            result[0] = pda[0:2]
            # Major version iteration (A = 0, B = 1, ... Z = Public Beta)
            result[1] = ord(pda[2]) - ord("A") if pda[2] in string.ascii_uppercase else 0
            
            # Year calculation based on scheme
            if use_new_scheme:
                # Newer devices (R=2018, S=2019, T=2020...)
                result[2] = (ord(pda[3]) - ord("R")) + 2018
            else:
                # Older devices (A=2001, B=2002, K=2011...)
                result[2] = (ord(pda[3]) - ord("A")) + 2001
                
            # Month (A = 01, B = 02, ... L = 12)
            month_char = pda[4]
            if month_char in string.ascii_uppercase and ord(month_char) - ord("A") <= 11:
                result[3] = ord(month_char) - ord("A")
            else:
                # Invalid month character, default to January
                result[3] = 0
                
            # Minor version iteration (1 = 1, ... A = 10 ...)
            if pda[5] in string.digits + string.ascii_uppercase:
                result[4] = (string.digits + string.ascii_uppercase).index(pda[5])
            else:
                result[4] = 0
        else:
            # Alternative format for older devices
            if len(pda) >= 3:
                # Year calculation based on scheme
                if use_new_scheme:
                    result[2] = (ord(pda[-3]) - ord("R")) + 2018
                else:
                    result[2] = (ord(pda[-3]) - ord("A")) + 2001
                
                # Month (A = 01, B = 02, ... L = 12)
                if len(pda) >= 2:
                    month_char = pda[-2]
                    if month_char in string.ascii_uppercase and ord(month_char) - ord("A") <= 11:
                        result[3] = ord(month_char) - ord("A")
                    else:
                        # Invalid month character, default to January
                        result[3] = 0
                    
                # Minor version iteration (1 = 1, ... A = 10 ...)
                if len(pda) >= 1:
                    if pda[-1] in string.digits + string.ascii_uppercase:
                        result[4] = (string.digits + string.ascii_uppercase).index(pda[-1])
                    else:
                        result[4] = 0
    
    except (IndexError, ValueError) as e:
        # If parsing fails, log and use default values
        # We've already initialized result with default values
        pass
        
    # Ensure month is in valid range 0-11
    if result[3] is None or result[3] < 0 or result[3] > 11:
        result[3] = default_month
    
    # Ensure year is reasonable
    if result[2] is None or result[2] < 2000 or result[2] > 2030:
        result[2] = default_year
    
    return (result[0], result[1], result[2], result[3], result[4])


def read_firmware_info(firmware: str) -> dict:
    """
    Return firmware information as a dictionary with meaningful keys.
    
    :param firmware: Samsung firmware version string
    :return: Dictionary with 'bl' (bootloader), 'date' (year.month), 'it' (iteration) keys
    """
    ff = _read_firmware(firmware)
    return {
        "bl": ff[0],
        "date": f"{ff[2]}.{ff[3]+1:02d}",  # Adding 1 to month for 1-based month numbering
        "it": f"{ff[1]}.{ff[4]}"
    }


def format_firmware_info(firmware: str) -> str:
    """
    Format firmware information as a human-readable string.
    
    :param firmware: Samsung firmware version string
    :return: Formatted string with firmware details
    """
    try:
        info = read_firmware_info(firmware)
        norm_fw = normalize_vercode(firmware)
        
        result = f"Firmware: {norm_fw}\n"
        if info["bl"]:
            result += f"Bootloader type: {info['bl']}\n"
        result += f"Date: {info['date']} (YYYY.MM)\n"
        result += f"Version iteration: {info['it']}"
        
        return result
    except ValueError:
        return f"Could not parse firmware string: {firmware}"

def get_latest_version(model: str, region: str) -> str:
    """ Get the latest firmware version code for a model and region. """
    req = requests.get("https://fota-cloud-dn.ospserver.net/firmware/"
                       + region + "/" + model + "/version.xml",
                       headers={'User-Agent': 'curl/7.87.0'})
    if req.status_code == 403:
        raise FUSError("Model or region not found (403)")
    req.raise_for_status()
    root = ET.fromstring(req.text)
    latest = root.find("./firmware/version/latest").text # type: ignore
    if latest is None:
        raise FUSError("No latest firmware available")
    return normalize_vercode(latest)