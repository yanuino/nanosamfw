# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Yannick Locque (yanuino)

"""Samsung Firmware Update Service (FUS) client library.

This package provides a complete implementation of the Samsung FUS protocol for
firmware discovery, download, and decryption. It handles the entire firmware
acquisition workflow including version queries, device validation, encrypted
downloads, and automatic decryption.

Main Components:
    - FUSClient: Core client for FUS protocol communication
    - Firmware utilities: Version queries and normalization
    - Decryption: ENC2/ENC4 firmware decryption with key derivation
    - Device validation: IMEI and serial number validation
    - Response parsing: XML response handling and data extraction

Example:
    Basic firmware version query::

        from fus import FUSClient, get_latest_version

        version = get_latest_version("SM-G998B", "EUX")
        print(f"Latest version: {version}")

    Full firmware download with decryption::

        from fus import FUSClient, get_v4_key, decrypt_file
        from fus.messages import build_binary_inform

        client = FUSClient()
        # ... perform inform, init, download operations
        key = get_v4_key(version, model, region, imei, client)
        decrypt_file("firmware.enc4", "firmware.zip", enc_ver=4, key=key)
"""

from .client import FUSClient
from .decrypt import decrypt_file, get_v2_key, get_v4_key
from .deviceid import is_device_id_required, validate_imei, validate_serial
from .errors import AuthError, DecryptError, DeviceIdError, DownloadError, FUSError, InformError
from .firmware import get_latest_version, normalize_vercode, read_firmware_info
from .responses import InformInfo, get_info_from_inform, parse_inform
