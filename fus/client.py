
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Yannick Locque (yanuino)


from __future__ import annotations
import requests, xml.etree.ElementTree as ET
from typing import Optional
from .config import FUSConfig, DEFAULT_CONFIG
from .crypto import decrypt_nonce, make_signature
from .errors import AuthError, DownloadError

class FUSClient:
    """
    Client FUS (Firmware Update Service) minimal.
    Gère NONCE -> signature, cookie JSESSIONID, POST/GET.
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
        nonce = self._enc_nonce if with_server_nonce else ""
        authv = f'FUS nonce="{nonce}", signature="{self._auth}", nc="", type="", realm="", newauth="1"'
        return {"Authorization": authv, "User-Agent": self.cfg.user_agent}

    def _makereq(self, path: str, data: bytes | str = b"") -> str:
        url = f"{self.cfg.base_url}/{path}"
        r = self.sess.post(url, data=data, headers=self._headers(), timeout=self.cfg.request_timeout, cookies={"JSESSIONID": self._sessid})
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
        xml = self._makereq("NF_DownloadBinaryInform.do", payload)
        return ET.fromstring(xml)

    def init(self, payload: bytes) -> ET.Element:
        xml = self._makereq("NF_DownloadBinaryInitForMass.do", payload)
        return ET.fromstring(xml)

    def stream(self, filename: str, start: int = 0):
        # cloud download (transmet le NONCE chiffré côté client)
        url = f"{self.cfg.cloud_url}/NF_DownloadBinaryForMass.do"
        headers = self._headers(with_server_nonce=True)
        if start > 0: headers["Range"] = f"bytes={start}-"
        r = self.sess.get(url, params="file=" + filename, headers=headers, stream=True, timeout=self.cfg.request_timeout)
        if not r.ok:
            raise DownloadError(f"HTTP {r.status_code} on download")
        return r