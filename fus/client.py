# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Yannick Locque (yanuino)


from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Optional

import requests

from .config import DEFAULT_CONFIG, FUSConfig
from .crypto import decrypt_nonce, make_signature
from .errors import DownloadError


class FUSClient:
    """
    Samsung Firmware Update Service (FUS) client implementation.

    Handles core FUS protocol operations including NONCE rotation,
    signature generation, and session management.

    Args:
        cfg: FUS configuration settings. Defaults to DEFAULT_CONFIG.
        session: Optional requests.Session for connection reuse.
    """

    def __init__(self, cfg: FUSConfig = DEFAULT_CONFIG, session: Optional[requests.Session] = None):
        self.cfg = cfg
        self.sess = session or requests.Session()
        self._auth = ""
        self._sessid = ""
        self._enc_nonce = ""
        self.nonce = ""
        # bootstrap: récupérer un NONCE
        self._makereq("NF_DownloadGenerateNonce.do")

    def _headers(self, with_server_nonce: bool = False) -> dict:
        """
        Build request headers including Authorization and User-Agent.

        Args:
            with_server_nonce: Whether to include encrypted NONCE in Authorization.

        Returns:
            dict: Headers dictionary for FUS requests.
        """
        nonce = self._enc_nonce if with_server_nonce else ""
        authv = (
            f'FUS nonce="{nonce}", signature="{self._auth}", nc="", type="", realm="", newauth="1"'
        )
        return {"Authorization": authv, "User-Agent": self.cfg.user_agent}

    def _makereq(self, path: str, data: bytes | str = b"") -> str:
        """
        Make an authenticated request to FUS server with NONCE rotation.

        Args:
            path: API endpoint path.
            data: Request payload (XML or bytes).

        Returns:
            str: Response text from server.

        Raises:
            requests.exceptions.HTTPError: On non-200 response.
        """
        url = f"{self.cfg.base_url}/{path}"
        r = self.sess.post(
            url,
            data=data,
            headers=self._headers(),
            timeout=self.cfg.request_timeout,
            cookies={"JSESSIONID": self._sessid},
        )
        # rotation de nonce + signature
        if "NONCE" in r.headers:
            self._enc_nonce = r.headers["NONCE"]
            self.nonce = decrypt_nonce(self._enc_nonce)
            self._auth = make_signature(self.nonce)
        if "JSESSIONID" in r.cookies:
            self._sessid = r.cookies["JSESSIONID"]
        r.raise_for_status()
        return r.text

    def inform(self, payload: bytes) -> ET.Element:
        """
        Send inform request to get firmware information.

        Args:
            payload: XML payload containing device and firmware details.

        Returns:
            ET.Element: Parsed XML response containing firmware metadata.

        Raises:
            requests.exceptions.HTTPError: On server error.
        """
        xml = self._makereq("NF_DownloadBinaryInform.do", payload)
        return ET.fromstring(xml)

    def init(self, payload: bytes) -> ET.Element:
        """
        Initialize binary download session.

        Args:
            payload: XML payload with download request details.

        Returns:
            ET.Element: Parsed XML response with download authorization.

        Raises:
            requests.exceptions.HTTPError: On server error.
        """
        xml = self._makereq("NF_DownloadBinaryInitForMass.do", payload)
        return ET.fromstring(xml)

    def stream(self, filename: str, start: int = 0):
        """
        Stream firmware download from cloud server.

        Args:
            filename: Remote firmware file path.
            start: Byte offset for resume capability.

        Returns:
            requests.Response: Streaming response object.

        Raises:
            DownloadError: On download initialization failure.
        """
        # cloud download (transmits client-side encrypted NONCE)
        url = f"{self.cfg.cloud_url}/NF_DownloadBinaryForMass.do"
        headers = self._headers(with_server_nonce=True)
        if start > 0:
            headers["Range"] = f"bytes={start}-"
        r = self.sess.get(
            url,
            params="file=" + filename,
            headers=headers,
            stream=True,
            timeout=self.cfg.request_timeout,
        )
        if not r.ok:
            raise DownloadError(f"HTTP {r.status_code} on download")
        return r
