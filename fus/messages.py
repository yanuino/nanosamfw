# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Vladislav Tislenko (keklick1337)
# Copyright (c) 2025 Yannick Locque (yanuino)

import xml.etree.ElementTree as ET
from typing import Any, Dict

from gnsf import FUSMessageBuilder
from .crypto import logic_check

def _hdr(root: ET.Element) -> None:
    """
    Add FUSHdr header to an XML message.

    :param root: root XML element (<FUSroot>)
    """
    hdr = ET.SubElement(root, "FUSHdr")
    ET.SubElement(hdr, "ProtoVer").text = "1.0"


def _body_put(root: ET.Element, params: Dict[str, Any]) -> None:
    """
    Add FUSBody/Put section with key→value params.

    :param root: root XML element (<FUSroot>)
    :param params: mapping of tag names → values
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

    :param fwv: firmware version code
    :param model: device model
    :param region: CSC region code
    :param device_id: device IMEI or Serial Number
    :param nonce: current FUS nonce
    :return: raw XML bytes
    """
    m = ET.Element("FUSroot"); _hdr(m)
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

    :param filename: firmware file name (with extension)
    :param nonce: current FUS nonce
    :return: raw XML bytes
    """
    m = ET.Element("FUSroot"); _hdr(m)
    checkinp = filename.split(".")[0][-16:]
    params = {
        "BINARY_FILE_NAME": filename,
        "LOGIC_CHECK": logic_check(checkinp, nonce),
    }
    _body_put(m, params)
    return ET.tostring(m)
