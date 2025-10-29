# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Vladislav Tislenko (keklick1337)
# Copyright (c) 2025 Yannick Locque (yanuino)

"""
FUS inform response parsing helpers.

Provides a small dataclass and utilities to extract firmware-related metadata
(filename, path, size) and server-provided values from a FUS BinaryInform XML
response.

Functions:
- get_info_from_inform: extract server path, filename and size from an inform response.
- parse_inform: build an InformInfo instance combining results and logic values.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Optional, Tuple

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
    Extract download metadata from a BinaryInform XML response.

    Args:
        root: Parsed XML root element of the BinaryInform response.

    Returns:
        A tuple (filename, path, size_bytes).

    Raises:
        InformError: If the inform response status is not 200.
        (Other exceptions may propagate if expected XML elements are missing or malformed.)
    """
    status = int(root.find("./FUSBody/Results/Status").text)  # type: ignore
    if status != 200:
        raise InformError(f"DownloadBinaryInform returned {status}")
    filename = root.find("./FUSBody/Put/BINARY_NAME/Data").text  # type: ignore
    size = int(root.find("./FUSBody/Put/BINARY_BYTE_SIZE/Data").text)  # type: ignore
    path = root.find("./FUSBody/Put/MODEL_PATH/Data").text  # type: ignore
    return filename, path, size  # type: ignore


def parse_inform(root: ET.Element) -> InformInfo:
    """
    Parse a BinaryInform XML response into an InformInfo structure.

    Args:
        root: Parsed XML root element of the BinaryInform response.

    Returns:
        InformInfo: Dataclass containing latest firmware version, logic value,
                    filename, path and size in bytes.

    Raises:
        InformError: If get_info_from_inform detects a non-200 status or other
                     inform-related errors occur.
    """
    latest = root.findtext("./FUSBody/Results/LATEST_FW_VERSION/Data")
    logic = root.findtext("./FUSBody/Put/LOGIC_VALUE_FACTORY/Data")
    filename, path, size = get_info_from_inform(root)
    return InformInfo(
        latest_fw_version=latest,
        logic_value_factory=logic,
        filename=filename,
        path=path,
        size_bytes=size,
    )
