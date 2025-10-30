# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Yannick Locque (yanuino)
"""
FUS configuration helpers.

This module defines the FUSConfig dataclass which centralizes default
endpoints and HTTP settings used by the FUS client.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class FUSConfig:
    """
    Configuration for the Firmware Update Service (FUS) client.

    Args:
        base_url: Base URL for FUS control endpoints. Some clients/tools may use a different host.
        cloud_url: Primary cloud URL used for firmware downloads.
        old_cloud_url: Legacy cloud URL kept for compatibility.
        user_agent: User-Agent header used for HTTP requests.
        request_timeout: Default timeout in seconds for HTTP requests.
    """

    # Endpoints (some clients/tools may use a different cloud host)
    base_url: str = "https://neofussvr.sslcs.cdngc.net"
    cloud_url: str = "http://cloud-neofussvr.samsungmobile.com"
    old_cloud_url: str = "http://cloud-fussvr.sslcs.cdngc.net"
    # Default User-Agent and timeout for HTTP requests
    user_agent: str = "Kies2.0_FUS"
    request_timeout: int = 60  # seconds


DEFAULT_CONFIG = FUSConfig()
