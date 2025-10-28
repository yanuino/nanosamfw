# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Vladislav Tislenko (keklick1337)
# Copyright (c) 2025 Yannick Locque (yanuino)

import base64
from Crypto.Cipher import AES

"""
Collection of static methods for AES encryption/decryption,
padding, key derivation and logic checks.
"""

KEY_1: str = "vicopx7dqu06emacgpnpy8j8zwhduwlh"
KEY_2: str = "9u7qab84rpc16gvk"

def pkcs_pad(data: bytes) -> bytes:
    """
    Apply PKCS#7 padding to the given data to reach a 16‑byte boundary.

    :param data: raw bytes to pad
    :return: padded bytes
    """
    pad_len = 16 - (len(data) % 16)
    return data + bytes([pad_len]) * pad_len

def pkcs_unpad(data: bytes) -> bytes:
    """
    Remove PKCS#7 padding from the given data.

    :param data: padded bytes
    :return: original unpadded bytes
    """
    return data[:-data[-1]]

def aes_cbc_encrypt(inp: bytes, key: bytes) -> bytes:
    """
    Encrypt data using AES‑CBC with IV = first 16 bytes of key.

    :param inp: plaintext bytes
    :param key: 16/24/32‑byte AES key
    :return: ciphertext bytes
    """
    iv = key[:16]
    cipher = AES.new(key, AES.MODE_CBC, iv)
    return cipher.encrypt(pkcs_pad(inp))

def aes_cbc_decrypt(inp: bytes, key: bytes) -> bytes:
    """
    Decrypt AES‑CBC ciphertext and remove PKCS#7 padding.

    :param inp: ciphertext bytes
    :param key: AES key used to encrypt
    :return: plaintext bytes
    """
    iv = key[:16]
    cipher = AES.new(key, AES.MODE_CBC, iv)
    return pkcs_unpad(cipher.decrypt(inp))

def derive_key(nonce: str) -> bytes:
    """
    Build a 48‑byte key from a server‑provided nonce.

    :param nonce: 16‑char nonce string
    :return: key bytes (KEY_1[ord(nonce[i])%16] * 16 + KEY_2)
    """
    k = "".join(KEY_1[ord(nonce[i]) % 16] for i in range(16))
    k += KEY_2
    return k.encode()

def make_signature(nonce: str) -> str:
    """
    Compute the base64‑encoded signature for a given nonce.

    :param nonce: plaintext nonce from server
    :return: base64 string of AES‑CBC( nonce, derive_key(nonce) )
    """
    raw = aes_cbc_encrypt(nonce.encode(), derive_key(nonce))
    return base64.b64encode(raw).decode()

def decrypt_nonce(enc_nonce: str) -> str:
    """
    Decrypt a server‑returned NONCE header using KEY_1.

    :param enc_nonce: base64‑encoded ciphertext
    :return: plaintext nonce
    """
    data = base64.b64decode(enc_nonce)
    return aes_cbc_decrypt(data, KEY_1.encode()).decode()

def logic_check(inp: str, nonce: str) -> str:
    """
    Compute the “logic check” value required by FUS.
    Picks characters from inp based on low 4 bits of each nonce char.

    :param inp: string, length >= 16
    :param nonce: server nonce string
    :return: logic‐check string
    """
    if len(inp) < 16:
        raise ValueError("logic_check input too short")
    return "".join(inp[ord(c) & 0xF] for c in nonce)
