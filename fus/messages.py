# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Vladislav Tislenko (keklick1337)
# Copyright (c) 2025 Yannick Locque (yanuino)

"""
FUS XML message builders.

Provides helpers to construct XML payloads used by the FUS protocol (inform/init).
These builders return raw XML bytes ready to be posted to the FUS endpoints.
"""

import xml.etree.ElementTree as ET
from typing import Any, Dict

from .crypto import logic_check


def _hdr(root: ET.Element) -> None:
    """
    Add a standard FUSHdr header to a message.

    Args:
        root: Root XML element (<FUSroot>).

    Returns:
        None.
    """
    hdr = ET.SubElement(root, "FUSHdr")
    ET.SubElement(hdr, "ProtoVer").text = "1.0"


def _body_put(root: ET.Element, params: Dict[str, Any]) -> None:
    """
    Add a FUSBody/Put section with key→value parameters.

    Args:
        root: Root XML element (<FUSroot>).
        params: Mapping of tag names to values to include under Put/Data.

    Returns:
        None.
    """
    body = ET.SubElement(root, "FUSBody")
    put = ET.SubElement(body, "Put")
    for tag, val in params.items():
        e = ET.SubElement(put, tag)
        d = ET.SubElement(e, "Data")
        d.text = str(val)


def build_binary_inform(fwv: str, model: str, region: str, device_id: str, nonce: str) -> bytes:
    """
    Build a BinaryInform request payload.

    Args:
        fwv: Firmware version code.
        model: Device model identifier.
        region: CSC/region code.
        device_id: Device IMEI or Serial number.
        nonce: Current FUS nonce.

    Returns:
        Raw XML payload as bytes.
    """
    m = ET.Element("FUSroot")
    _hdr(m)
    params = {
        "ACCESS_MODE": 2,
        "BINARY_NATURE": 1,
        "CLIENT_PRODUCT": "Smart Switch",
        "CLIENT_VERSION": "4.3.23123_1",
        "DEVICE_IMEI_PUSH": device_id,
        "DEVICE_FW_VERSION": fwv,
        "DEVICE_LOCAL_CODE": region,
        "DEVICE_MODEL_NAME": model,
        "LOGIC_CHECK": logic_check(fwv, nonce),
    }
    _body_put(m, params)
    return ET.tostring(m)


def build_binary_init(filename: str, nonce: str) -> bytes:
    """
    Build a BinaryInitForMass request payload.

    Args:
        filename: Firmware file name (including extension).
        nonce: Current FUS nonce.

    Returns:
        Raw XML payload as bytes.
    """
    m = ET.Element("FUSroot")
    _hdr(m)
    checkinp = filename.split(".")[0][-16:]
    params = {
        "BINARY_FILE_NAME": filename,
        "LOGIC_CHECK": logic_check(checkinp, nonce),
    }
    _body_put(m, params)
    return ET.tostring(m)
