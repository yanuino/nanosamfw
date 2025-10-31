# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Vladislav Tislenko (keklick1337)
# Copyright (c) 2025 Yannick Locque (yanuino)
"""
FUS crypto helpers: AES CBC utilities, padding, key derivation and logic checks.

Provides small helpers used by the FUS client and decryption routines.
"""

import base64

from Crypto.Cipher import AES

KEY_1: str = "vicopx7dqu06emacgpnpy8j8zwhduwlh"
KEY_2: str = "9u7qab84rpc16gvk"


def pkcs_pad(data: bytes) -> bytes:
    """
    Apply PKCS#7 padding to reach a 16-byte boundary.

    Args:
        data: Raw bytes to pad.

    Returns:
        Padded bytes.
    """
    pad_len = 16 - (len(data) % 16)
    return data + bytes([pad_len]) * pad_len


def pkcs_unpad(data: bytes) -> bytes:
    """
    Remove PKCS#7 padding.

    Args:
        data: Padded bytes.

    Returns:
        Original unpadded bytes.
    """
    return data[: -data[-1]]


def aes_cbc_encrypt(inp: bytes, key: bytes) -> bytes:
    """
    Encrypt data using AES-CBC with IV equal to the first 16 bytes of the key.

    Args:
        inp: Plaintext bytes.
        key: AES key (16/24/32 bytes).

    Returns:
        Ciphertext bytes.
    """
    iv = key[:16]
    cipher = AES.new(key, AES.MODE_CBC, iv)
    return cipher.encrypt(pkcs_pad(inp))


def aes_cbc_decrypt(inp: bytes, key: bytes) -> bytes:
    """
    Decrypt AES-CBC ciphertext and remove PKCS#7 padding.

    Args:
        inp: Ciphertext bytes.
        key: AES key used to encrypt.

    Returns:
        Plaintext bytes.
    """
    iv = key[:16]
    cipher = AES.new(key, AES.MODE_CBC, iv)
    return pkcs_unpad(cipher.decrypt(inp))


def derive_key(nonce: str) -> bytes:
    """
    Build a key from a 16-character server nonce.

    The resulting key is KEY_1[ord(nonce[i])%16] repeated for 16 chars,
    concatenated with KEY_2, returned as bytes.

    Args:
        nonce: 16-character nonce string.

    Returns:
        Derived key bytes.
    """
    k = "".join(KEY_1[ord(nonce[i]) % 16] for i in range(16))
    k += KEY_2
    return k.encode()


def make_signature(nonce: str) -> str:
    """
    Compute the base64-encoded signature for a nonce.

    The signature is base64(AES-CBC(nonce, derive_key(nonce))).

    Args:
        nonce: Plaintext nonce.

    Returns:
        Base64-encoded signature string.
    """
    raw = aes_cbc_encrypt(nonce.encode(), derive_key(nonce))
    return base64.b64encode(raw).decode()


def decrypt_nonce(enc_nonce: str) -> str:
    """
    Decrypt a server NONCE header.

    Args:
        enc_nonce: Base64-encoded ciphertext from server.

    Returns:
        Decrypted plaintext nonce.

    Raises:
        Exception: Propagates base64 and AES decode errors if input is malformed.
    """
    data = base64.b64decode(enc_nonce)
    return aes_cbc_decrypt(data, KEY_1.encode()).decode()


def logic_check(inp: str, nonce: str) -> str:
    """
    Compute the FUS logic-check value.

    Picks characters from `inp` using the low 4 bits of each character in `nonce`.

    Args:
        inp: Input string (must be at least 16 characters).
        nonce: Server nonce string.

    Returns:
        Computed logic-check string.

    Raises:
        ValueError: If `inp` is shorter than 16 characters.
    """
    if len(inp) < 16:
        raise ValueError("logic_check input too short")
    return "".join(inp[ord(c) & 0xF] for c in nonce)
