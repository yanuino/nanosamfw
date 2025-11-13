# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Vladislav Tislenko (keklick1337)
# Copyright (c) 2025 Yannick Locque (yanuino)

"""
FUS inform response parsing helpers.

Provides a dataclass and parser to extract firmware-related metadata from a
FUS BinaryInform XML response.

Functions:
- parse_inform: parse BinaryInform response into an InformInfo dataclass.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass

from .errors import InformError


@dataclass(frozen=True)
class InformInfo:
    """FUS BinaryInform response data.

    Dataclass holding parsed metadata from a Samsung FUS BinaryInform XML response.
    All fields are guaranteed to be present when status is 200.

    Attributes:
        latest_fw_version: Latest firmware version string.
        logic_value_factory: Logic value for ENC4 decryption key derivation.
        filename: Binary firmware filename on the server.
        path: Server model path.
        size_bytes: Firmware file size in bytes.
    """

    latest_fw_version: str
    logic_value_factory: str
    filename: str
    path: str
    size_bytes: int


def parse_inform(root: ET.Element) -> InformInfo:
    """
    Parse a BinaryInform XML response into an InformInfo structure.

    Args:
        root: Parsed XML root element of the BinaryInform response.

    Returns:
        InformInfo: Dataclass containing latest firmware version, logic value,
                    filename, path and size in bytes.

    Raises:
        InformError: If the inform response status is not 200 or required fields are missing.
    """
    status_elem = root.find("./FUSBody/Results/Status")
    if status_elem is None or status_elem.text is None:
        raise InformError("Missing Status field in inform response")

    status = int(status_elem.text)
    if status != 200:
        raise InformError(f"DownloadBinaryInform returned {status}")

    # Extract required fields - raise InformError if any are missing
    latest = root.findtext("./FUSBody/Results/LATEST_FW_VERSION/Data")
    if not latest:
        raise InformError("Missing LATEST_FW_VERSION in inform response")

    logic = root.findtext("./FUSBody/Put/LOGIC_VALUE_FACTORY/Data")
    if not logic:
        raise InformError("Missing LOGIC_VALUE_FACTORY in inform response")

    filename_elem = root.find("./FUSBody/Put/BINARY_NAME/Data")
    if filename_elem is None or not filename_elem.text:
        raise InformError("Missing BINARY_NAME in inform response")
    filename = filename_elem.text

    size_elem = root.find("./FUSBody/Put/BINARY_BYTE_SIZE/Data")
    if size_elem is None or not size_elem.text:
        raise InformError("Missing BINARY_BYTE_SIZE in inform response")
    size = int(size_elem.text)

    path = root.findtext("./FUSBody/Put/MODEL_PATH/Data")
    if not path:
        raise InformError("Missing MODEL_PATH in inform response")

    return InformInfo(
        latest_fw_version=latest,
        logic_value_factory=logic,
        filename=filename,
        path=path,
        size_bytes=size,
    )
