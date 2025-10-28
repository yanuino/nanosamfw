# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Yannick Locque (yanuino)

from dataclasses import dataclass

@dataclass(frozen=True)
class FUSConfig:
    # Endpoints (sur certains clients/outils, l’hôte cloud diffère)
    base_url: str = "https://neofussvr.sslcs.cdngc.net"
    cloud_url: str = "http://cloud-neofussvr.samsungmobile.com"
    old_cloud_url: str = "http://cloud-fussvr.sslcs.cdngc.net"
    # User-Agent et timeout par défaut pour les requêtes HTTP
    user_agent: str = "Kies2.0_FUS"
    request_timeout: int = 60  # seconds
DEFAULT_CONFIG = FUSConfig()
