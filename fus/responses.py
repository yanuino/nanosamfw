# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Vladislav Tislenko (keklick1337)
# Copyright (c) 2025 Yannick Locque (yanuino)

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Tuple
import xml.etree.ElementTree as ET

from .errors import InformError

@dataclass(frozen=True)
class InformInfo:
    latest_fw_version: Optional[str]
    logic_value_factory: Optional[str]
    filename: str
    path: Optional[str] = None
    size_bytes: Optional[int] = None

def get_info_from_inform(root: ET.Element) -> Tuple[str, str, int]:
    """
    Request info on the firmware bundle (path, filename, size).

    :param client: FUSClient with valid nonce
    :param fw: normalized firmware version
    :param model: device model
    :param device_id: device IMEI or Serial Number
    :param region: CSC region
    :return: (server path, filename, size in bytes)
    """
    status = int(root.find("./FUSBody/Results/Status").text)  # type: ignore
    if status != 200:
        raise RuntimeError(f"DownloadBinaryInform returned {status}")
    filename = root.find("./FUSBody/Put/BINARY_NAME/Data").text  # type: ignore
    size = int(root.find("./FUSBody/Put/BINARY_BYTE_SIZE/Data").text)  # type: ignore
    path = root.find("./FUSBody/Put/MODEL_PATH/Data").text  # type: ignore
    return filename, path, size # type: ignore


def parse_inform(root: ET.Element) -> InformInfo:
    latest = root.findtext("./FUSBody/Results/LATEST_FW_VERSION/Data")
    logic  = root.findtext("./FUSBody/Put/LOGIC_VALUE_FACTORY/Data")
    filename, path, size = get_info_from_inform(root)
    return InformInfo(latest_fw_version=latest, logic_value_factory=logic, filename=filename, path=path, size_bytes=size)
