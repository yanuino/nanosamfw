#!/usr/bin/env python3
# GetNewSamsungFirmware (GNSF)
# A CLI tool to download and decrypt Samsung firmware packages.
# Author: Vladislav Tislenko (keklick1337), 2025

import argparse
import base64
import hashlib
import os
import random
import string
import sys
import xml.etree.ElementTree as ET
from typing import Any, Dict, Optional, Tuple
import requests
from Crypto.Cipher import AES
from tqdm import tqdm
from csclist import CSC_DICT
import concurrent.futures
import threading

VERSION = "1.0.4"

class CryptoUtils:
    """
    Collection of static methods for AES encryption/decryption,
    padding, key derivation and logic checks.
    """

    KEY_1: str = "vicopx7dqu06emacgpnpy8j8zwhduwlh"
    KEY_2: str = "9u7qab84rpc16gvk"

    @staticmethod
    def pkcs_pad(data: bytes) -> bytes:
        """
        Apply PKCS#7 padding to the given data to reach a 16‑byte boundary.

        :param data: raw bytes to pad
        :return: padded bytes
        """
        pad_len = 16 - (len(data) % 16)
        return data + bytes([pad_len]) * pad_len

    @staticmethod
    def pkcs_unpad(data: bytes) -> bytes:
        """
        Remove PKCS#7 padding from the given data.

        :param data: padded bytes
        :return: original unpadded bytes
        """
        return data[:-data[-1]]

    @staticmethod
    def aes_encrypt(inp: bytes, key: bytes) -> bytes:
        """
        Encrypt data using AES‑CBC with IV = first 16 bytes of key.

        :param inp: plaintext bytes
        :param key: 16/24/32‑byte AES key
        :return: ciphertext bytes
        """
        iv = key[:16]
        cipher = AES.new(key, AES.MODE_CBC, iv)
        return cipher.encrypt(CryptoUtils.pkcs_pad(inp))

    @staticmethod
    def aes_decrypt(inp: bytes, key: bytes) -> bytes:
        """
        Decrypt AES‑CBC ciphertext and remove PKCS#7 padding.

        :param inp: ciphertext bytes
        :param key: AES key used to encrypt
        :return: plaintext bytes
        """
        iv = key[:16]
        cipher = AES.new(key, AES.MODE_CBC, iv)
        return CryptoUtils.pkcs_unpad(cipher.decrypt(inp))

    @staticmethod
    def derive_key(nonce: str) -> bytes:
        """
        Build a 48‑byte key from a server‑provided nonce.

        :param nonce: 16‑char nonce string
        :return: key bytes (KEY_1[ord(nonce[i])%16] * 16 + KEY_2)
        """
        k = "".join(CryptoUtils.KEY_1[ord(nonce[i]) % 16] for i in range(16))
        k += CryptoUtils.KEY_2
        return k.encode()

    @staticmethod
    def getauth(nonce: str) -> str:
        """
        Compute the base64‑encoded signature for a given nonce.

        :param nonce: plaintext nonce from server
        :return: base64 string of AES‑CBC( nonce, derive_key(nonce) )
        """
        raw = CryptoUtils.aes_encrypt(nonce.encode(), CryptoUtils.derive_key(nonce))
        return base64.b64encode(raw).decode()

    @staticmethod
    def decryptnonce(enc_nonce: str) -> str:
        """
        Decrypt a server‑returned NONCE header using KEY_1.

        :param enc_nonce: base64‑encoded ciphertext
        :return: plaintext nonce
        """
        data = base64.b64decode(enc_nonce)
        return CryptoUtils.aes_decrypt(data, CryptoUtils.KEY_1.encode()).decode()

    @staticmethod
    def getlogiccheck(inp: str, nonce: str) -> str:
        """
        Compute the “logic check” value required by FUS.
        Picks characters from inp based on low 4 bits of each nonce char.

        :param inp: string, length >= 16
        :param nonce: server nonce string
        :return: logic‐check string
        """
        if len(inp) < 16:
            raise ValueError("getlogiccheck() input too short")
        return "".join(inp[ord(c) & 0xF] for c in nonce)


class IMEIUtils:
    """
    Helpers to require, validate and auto‑fill IMEI values or Serial Numbers.
    """

    @staticmethod
    def device_id_required(args: argparse.Namespace) -> bool:
        """
        Determine if device ID (IMEI or Serial Number) is mandatory for the given command.

        :param args: parsed CLI args
        :return: True if download or decrypt(enc_ver=4)
        """
        return args.command == "download" or (args.command == "decrypt" and args.enc_ver == 4)

    @staticmethod
    def imei_required(args: argparse.Namespace) -> bool:
        """
        Determine if IMEI is mandatory for the given command.

        :param args: parsed CLI args
        :return: True if download or decrypt(enc_ver=4)
        """
        return args.command == "download" or (args.command == "decrypt" and args.enc_ver == 4)

    @staticmethod
    def luhn_checksum(imei: str) -> int:
        """
        Compute Luhn checksum digit for an IMEI‑string (without the check digit).

        :param imei: first N digits of IMEI
        :return: check digit [0–9]
        """
        s = 0
        tmp = imei + '0'
        parity = len(tmp) % 2
        for idx, ch in enumerate(tmp):
            d = int(ch)
            if idx % 2 == parity:
                d *= 2
                if d > 9:
                    d -= 9
            s += d
        return (10 - (s % 10)) % 10

    @staticmethod
    def validate_serial_number(serial: str) -> bool:
        """
        Validate serial number format (1-35 characters, letters and digits only).

        :param serial: serial number string to validate
        :return: True if valid, False otherwise
        """
        if not serial:
            return False
        if not 1 <= len(serial) <= 35:
            return False
        return serial.isalnum()

    @staticmethod
    def get_device_id(args: argparse.Namespace) -> str:
        """
        Get the device ID (IMEI or Serial Number) from args.

        :param args: parsed CLI args
        :return: device ID string (IMEI or Serial Number)
        """
        if hasattr(args, 'dev_serial') and args.dev_serial:
            return args.dev_serial
        elif hasattr(args, 'dev_imei') and args.dev_imei:
            return args.dev_imei
        return ""

    @staticmethod
    def fixup_device_id(args: argparse.Namespace) -> int:
        """
        Validate or auto‐fill the device ID (IMEI or Serial Number).

        :param args: parsed CLI args (must have dev_imei or dev_serial)
        :return: 0 on success, 1 on failure (and prints message)
        """
        if not IMEIUtils.device_id_required(args):
            return 0

        # Check if we have either IMEI or Serial Number
        device_id = IMEIUtils.get_device_id(args)
        
        if not device_id:
            print("Need either IMEI (use -i) or Serial Number (use -s)")
            return 1

        # If using serial number, validate it
        if hasattr(args, 'dev_serial') and args.dev_serial:
            if not IMEIUtils.validate_serial_number(args.dev_serial):
                print("Serial Number must be 1-35 characters (letters and digits only)")
                return 1
            return 0

        # If using IMEI, validate and auto-fill if needed
        if hasattr(args, 'dev_imei') and args.dev_imei:
            return IMEIUtils.fixup_imei(args)
        
        return 1

    @staticmethod
    def fixup_imei(args: argparse.Namespace) -> int:
        """
        Validate or auto‐fill the IMEI to 15 digits.

        :param args: parsed CLI args (must have dev_imei)
        :return: 0 on success, 1 on failure (and prints message)
        """
        if not args.dev_imei:
            return 0
        if not args.dev_imei.isdecimal() or len(args.dev_imei) < 8:
            print("Need at least 8 digits for IMEI; use -i")
            return 1
        if len(args.dev_imei) < 15 and args.dev_imei.isdecimal():
            missing = 14 - len(args.dev_imei)
            rnd = random.randint(0, 10**missing - 1)
            args.dev_imei += f"%0{missing}d" % rnd
            args.dev_imei += str(IMEIUtils.luhn_checksum(args.dev_imei))
            print(f"Filled up imei to {args.dev_imei}")
        return 0


class FUSMessageBuilder:
    """
    Constructs XML messages for the FUS (Firmware Update Service) API.
    """

    @staticmethod
    def build_reqhdr(msg: ET.Element) -> None:
        """
        Add FUSHdr header to an XML message.

        :param msg: root XML element (<FUSMsg>)
        """
        hdr = ET.SubElement(msg, "FUSHdr")
        ET.SubElement(hdr, "ProtoVer").text = "1.0"

    @staticmethod
    def build_reqbody(msg: ET.Element, params: Dict[str, Any]) -> None:
        """
        Add FUSBody/Put section with key→value params.

        :param msg: root XML element (<FUSMsg>)
        :param params: mapping of tag names → values
        """
        body = ET.SubElement(msg, "FUSBody")
        put = ET.SubElement(body, "Put")
        for tag, val in params.items():
            e = ET.SubElement(put, tag)
            d = ET.SubElement(e, "Data")
            d.text = str(val)

    @staticmethod
    def binaryinform(fwv: str, model: str, region: str, device_id: str, nonce: str) -> bytes:
        """
        Build a BinaryInform request payload.

        :param fwv: firmware version code
        :param model: device model
        :param region: CSC region code
        :param device_id: device IMEI or Serial Number
        :param nonce: current FUS nonce
        :return: raw XML bytes
        """
        m = ET.Element("FUSMsg")
        FUSMessageBuilder.build_reqhdr(m)
        params = {
            "ACCESS_MODE": 2,
            "BINARY_NATURE": 1,
            "CLIENT_PRODUCT": "Smart Switch",
            "CLIENT_VERSION": "4.3.23123_1",
            "DEVICE_IMEI_PUSH": device_id,
            "DEVICE_FW_VERSION": fwv,
            "DEVICE_LOCAL_CODE": region,
            "DEVICE_MODEL_NAME": model,
            "LOGIC_CHECK": CryptoUtils.getlogiccheck(fwv, nonce),
        }
        FUSMessageBuilder.build_reqbody(m, params)
        return ET.tostring(m)

    @staticmethod
    def binaryinit(filename: str, nonce: str) -> bytes:
        """
        Build a BinaryInitForMass request payload.

        :param filename: firmware file name (with extension)
        :param nonce: current FUS nonce
        :return: raw XML bytes
        """
        m = ET.Element("FUSMsg")
        FUSMessageBuilder.build_reqhdr(m)
        checkinp = filename.split(".")[0][-16:]
        params = {
            "BINARY_FILE_NAME": filename,
            "LOGIC_CHECK": CryptoUtils.getlogiccheck(checkinp, nonce),
        }
        FUSMessageBuilder.build_reqbody(m, params)
        return ET.tostring(m)


class FirmwareUtils:
    """
    Utilities for parsing Samsung firmware version strings to extract metadata.
    """
    
    @staticmethod
    def read_firmware(firmware: str) -> Tuple[Optional[str], Optional[int], int, int, int]:
        """
        Gets basic information from a firmware string.
        
        :param firmware: Samsung firmware version string
        :return: Tuple containing (bootloader_type, major_version, year, month, minor_version)
        """
        # Default values in case parsing fails
        default_year = 2020
        default_month = 0  # January (0-indexed)
        
        # First normalize to handle both slash-separated and compact formats
        if "/" in firmware:
            # Handle slash-separated format (newer style)
            parts = firmware.split("/")
            pda = parts[0][-6:] if len(parts) >= 1 and len(parts[0]) >= 6 else ""
        else:
            # Handle compact format (older style like N7000XXKKA)
            # Extract the last 6 characters, assuming model prefix varies in length
            pda = firmware[-6:] if len(firmware) >= 6 else firmware
        
        result = [None, None, default_year, default_month, 0]
        
        try:
            # Detect if we're using the newer (R=2018+) or older (A=2001+) scheme
            # This could be based on the year character or device model prefix
            use_new_scheme = ord(pda[3]) >= ord('R') if len(pda) >= 4 else True
            
            if len(pda) >= 6 and pda[0] in ["U", "S"]:
                # Bootloader version (U = Upgrade, S = Security)
                result[0] = pda[0:2]
                # Major version iteration (A = 0, B = 1, ... Z = Public Beta)
                result[1] = ord(pda[2]) - ord("A") if pda[2] in string.ascii_uppercase else 0
                
                # Year calculation based on scheme
                if use_new_scheme:
                    # Newer devices (R=2018, S=2019, T=2020...)
                    result[2] = (ord(pda[3]) - ord("R")) + 2018
                else:
                    # Older devices (A=2001, B=2002, K=2011...)
                    result[2] = (ord(pda[3]) - ord("A")) + 2001
                    
                # Month (A = 01, B = 02, ... L = 12)
                month_char = pda[4]
                if month_char in string.ascii_uppercase and ord(month_char) - ord("A") <= 11:
                    result[3] = ord(month_char) - ord("A")
                else:
                    # Invalid month character, default to January
                    result[3] = 0
                    
                # Minor version iteration (1 = 1, ... A = 10 ...)
                if pda[5] in string.digits + string.ascii_uppercase:
                    result[4] = (string.digits + string.ascii_uppercase).index(pda[5])
                else:
                    result[4] = 0
            else:
                # Alternative format for older devices
                if len(pda) >= 3:
                    # Year calculation based on scheme
                    if use_new_scheme:
                        result[2] = (ord(pda[-3]) - ord("R")) + 2018
                    else:
                        result[2] = (ord(pda[-3]) - ord("A")) + 2001
                    
                    # Month (A = 01, B = 02, ... L = 12)
                    if len(pda) >= 2:
                        month_char = pda[-2]
                        if month_char in string.ascii_uppercase and ord(month_char) - ord("A") <= 11:
                            result[3] = ord(month_char) - ord("A")
                        else:
                            # Invalid month character, default to January
                            result[3] = 0
                        
                    # Minor version iteration (1 = 1, ... A = 10 ...)
                    if len(pda) >= 1:
                        if pda[-1] in string.digits + string.ascii_uppercase:
                            result[4] = (string.digits + string.ascii_uppercase).index(pda[-1])
                        else:
                            result[4] = 0
        
        except (IndexError, ValueError) as e:
            # If parsing fails, log and use default values
            # We've already initialized result with default values
            pass
            
        # Ensure month is in valid range 0-11
        if result[3] is None or result[3] < 0 or result[3] > 11:
            result[3] = default_month
        
        # Ensure year is reasonable
        if result[2] is None or result[2] < 2000 or result[2] > 2030:
            result[2] = default_year
        
        return (result[0], result[1], result[2], result[3], result[4])

    @staticmethod
    def read_firmware_dict(firmware: str) -> dict:
        """
        Return firmware information as a dictionary with meaningful keys.
        
        :param firmware: Samsung firmware version string
        :return: Dictionary with 'bl' (bootloader), 'date' (year.month), 'it' (iteration) keys
        """
        ff = FirmwareUtils.read_firmware(firmware)
        return {
            "bl": ff[0],
            "date": f"{ff[2]}.{ff[3]+1:02d}",  # Adding 1 to month for 1-based month numbering
            "it": f"{ff[1]}.{ff[4]}"
        }
    
    @staticmethod
    def format_firmware_info(firmware: str) -> str:
        """
        Format firmware information as a human-readable string.
        
        :param firmware: Samsung firmware version string
        :return: Formatted string with firmware details
        """
        try:
            info = FirmwareUtils.read_firmware_dict(firmware)
            norm_fw = normalizevercode(firmware)
            
            result = f"Firmware: {norm_fw}\n"
            if info["bl"]:
                result += f"Bootloader type: {info['bl']}\n"
            result += f"Date: {info['date']} (YYYY.MM)\n"
            result += f"Version iteration: {info['it']}"
            
            return result
        except ValueError:
            return f"Could not parse firmware string: {firmware}"


def getv4key(version: str, model: str, region: str, device_id: str) -> Optional[bytes]:
    """
    Retrieve the MD5‐derived AES key for V4 encryption by querying FUS.

    :param version: firmware version code
    :param model: device model
    :param region: CSC region
    :param device_id: device IMEI or Serial Number
    :return: 16‐byte AES key or None on failure
    """
    if not device_id:
        raise ValueError("Device ID (IMEI or Serial Number) is required for V4 key retrieval. Use -i or -s")
    
    if not region:
        raise ValueError("Region is required for V4 key retrieval. Use -r")

    client = FUSClient()
    version_norm = normalizevercode(version)
    req = FUSMessageBuilder.binaryinform(version_norm, model, region, device_id, client.nonce)
    resp = client.makereq("NF_DownloadBinaryInform.do", req)
    try:
        root = ET.fromstring(resp)
        fwver = root.find("./FUSBody/Results/LATEST_FW_VERSION/Data").text  # type: ignore
        logicval = root.find("./FUSBody/Put/LOGIC_VALUE_FACTORY/Data").text  # type: ignore
    except AttributeError:
        print("Could not get decryption key from servers - bad model/region/device_id?")
        return None
    deckey = CryptoUtils.getlogiccheck(fwver, logicval)
    return hashlib.md5(deckey.encode()).digest()


def getv2key(version: str, model: str, region: str, _device_id: str) -> bytes:
    """
    Compute legacy V2 AES key (no server call).

    :param version: firmware version code
    :param model: device model
    :param region: CSC region
    :param _device_id: ignored (device ID not needed for V2)
    :return: 16‐byte AES key (MD5 of "region:model:version")
    """
    if not region:
        raise ValueError("Region is required for V2 key retrieval. Use -r")
    
    deckey = f"{region}:{model}:{version}"
    return hashlib.md5(deckey.encode()).digest()


def decrypt_progress(inf: Any, outf: Any, key: bytes, length: int) -> None:
    """
    Decrypt an encrypted firmware stream, showing a progress bar.

    :param inf: file‐like input (.read)
    :param outf: file‐like output (.write)
    :param key: AES key (16 bytes)
    :param length: total input size in bytes
    :raises Exception: if length not multiple of 16
    """
    if length % 16 != 0:
        raise ValueError("invalid input block size")
    cipher = AES.new(key, AES.MODE_ECB)
    chunks = length // 4096 + 1
    pbar = tqdm(total=length, unit="B", unit_scale=True)
    for i in range(chunks):
        block = inf.read(4096)
        if not block:
            break
        decblock = cipher.decrypt(block)
        if i == chunks - 1:
            outf.write(CryptoUtils.pkcs_unpad(decblock))
        else:
            outf.write(decblock)
        pbar.update(len(block))
    pbar.close()


class FUSClient:
    """ FUS API client. """
    def __init__(self):
        self.auth = ""
        self.sessid = ""
        self.makereq("NF_DownloadGenerateNonce.do") # initialize nonce
    def makereq(self, path: str, data: str = "") -> str:
        """ Make a FUS request to a given endpoint. """
        authv = 'FUS nonce="", signature="' + self.auth + '", nc="", type="", realm="", newauth="1"'
        req = requests.post("https://neofussvr.sslcs.cdngc.net/" + path, data=data,
                            headers={"Authorization": authv, "User-Agent": "Kies2.0_FUS"},
                            cookies={"JSESSIONID": self.sessid})
        # If a new NONCE is present, decrypt it and update our auth token.
        if "NONCE" in req.headers:
            self.encnonce = req.headers["NONCE"]
            self.nonce = CryptoUtils.decryptnonce(self.encnonce)
            self.auth = CryptoUtils.getauth(self.nonce)
        # Update the session cookie if needed.
        if "JSESSIONID" in req.cookies:
            self.sessid = req.cookies["JSESSIONID"]
        req.raise_for_status()
        return req.text
    def downloadfile(self, filename: str, start: int = 0) -> requests.Response:
        """ Make a FUS cloud request to download a given file. """
        # In a cloud request, we also need to pass the server nonce.
        authv = 'FUS nonce="' + self.encnonce + '", signature="' + self.auth \
            + '", nc="", type="", realm="", newauth="1"'
        headers = {"Authorization": authv, "User-Agent": "Kies2.0_FUS"}
        if start > 0:
            headers["Range"] = "bytes={}-".format(start)
        req = requests.get("http://cloud-neofussvr.samsungmobile.com/NF_DownloadBinaryForMass.do",
                           params="file=" + filename, headers=headers, stream=True)
        req.raise_for_status()
        return req

def normalizevercode(vercode: str) -> str:
    """
    Normalize a 3‑ or 4‑part version code to exactly 4 parts.

    :param vercode: e.g. "G900FXXU1ANE2" or "G900F/XXU/1ANE/2"
    :return: 4‑part string
    """
    parts = vercode.split("/")
    if len(parts) == 3:
        parts.append(parts[0])
    if parts[2] == "":
        parts[2] = parts[0]
    return "/".join(parts)


def getlatestver(model: str, region: str) -> str:
    """ Get the latest firmware version code for a model and region. """
    req = requests.get("https://fota-cloud-dn.ospserver.net/firmware/"
                       + region + "/" + model + "/version.xml",
                       headers={'User-Agent': 'curl/7.87.0'})
    if req.status_code == 403:
        raise Exception("Model or region not found (403)")
    req.raise_for_status()
    root = ET.fromstring(req.text)
    vercode = root.find("./firmware/version/latest").text
    if vercode is None:
        raise Exception("No latest firmware available")
    return normalizevercode(vercode)

def decrypt_file(
    args: argparse.Namespace, version: int, encrypted: str, decrypted: str
) -> int:
    """
    High‐level helper to decrypt a .enc2/.enc4 file using the correct key.

    :param args: CLI args (to supply model, region, device_id, version)
    :param version: encryption version (2 or 4)
    :param encrypted: path to .enc2/.enc4 file
    :param decrypted: path for output decrypted file
    :return: 0 on success, 1 on failure
    """
    if version not in (2, 4):
        raise ValueError(f"Unknown encryption version: {version}")
    getkey = getv2key if version == 2 else getv4key
    device_id = IMEIUtils.get_device_id(args)
    key = getkey(args.fw_ver, args.dev_model, args.dev_region, device_id)
    if not key:
        return 1
    length = os.stat(encrypted).st_size
    with open(encrypted, "rb") as inf, open(decrypted, "wb") as outf:
        decrypt_progress(inf, outf, key, length)
    return 0


def initdownload(client: FUSClient, filename: str) -> None:
    """
    Send the BinaryInitForMass request before streaming a download.

    :param client: active FUSClient
    :param filename: remote firmware file name
    """
    req = FUSMessageBuilder.binaryinit(filename, client.nonce)
    resp = client.makereq("NF_DownloadBinaryInitForMass.do", req)

def getbinaryfile(
    client: FUSClient, fw: str, model: str, device_id: str, region: str
) -> Tuple[str, str, int]:
    """
    Request info on the firmware bundle (path, filename, size).

    :param client: FUSClient with valid nonce
    :param fw: normalized firmware version
    :param model: device model
    :param device_id: device IMEI or Serial Number
    :param region: CSC region
    :return: (server path, filename, size in bytes)
    """
    req = FUSMessageBuilder.binaryinform(fw, model, region, device_id, client.nonce)
    resp = client.makereq("NF_DownloadBinaryInform.do", req)
    root = ET.fromstring(resp)
    status = int(root.find("./FUSBody/Results/Status").text)  # type: ignore
    if status != 200:
        raise RuntimeError(f"DownloadBinaryInform returned {status}")
    filename = root.find("./FUSBody/Put/BINARY_NAME/Data").text  # type: ignore
    size = int(root.find("./FUSBody/Put/BINARY_BYTE_SIZE/Data").text)  # type: ignore
    path = root.find("./FUSBody/Put/MODEL_PATH/Data").text  # type: ignore
    return path, filename, size


class GNSFApp:
    """
    CLI application class for GNSF.
    Parses arguments and dispatches to download, check or decrypt.
    """

    def __init__(self) -> None:
        """
        Initialize the top‐level argument parser.
        """
        self.parser = argparse.ArgumentParser(
            prog="GNSF", description="Download and decrypt Samsung firmware"
        )
        self._setup_args()

    def _setup_args(self) -> None:
        """Define command‑line arguments and subcommands."""
        p = self.parser
        p.add_argument("-m", "--dev-model", required=True, help="device model")
        p.add_argument("-r", "--dev-region", help="device region code")
        p.add_argument(
            "-i",
            "--dev-imei",
            help="device IMEI (will be auto‑filled if you give ≥8 digits)",
        )
        p.add_argument(
            "-s",
            "--dev-serial",
            help="device Serial Number (1-35 characters, letters and digits)",
        )
        p.add_argument("--version", action="version", version=f"GNSF {VERSION}")

        subs = p.add_subparsers(dest="command", required=True)
        # download
        dl = subs.add_parser("download", help="download & decrypt firmware")
        dl.add_argument(
            "-v", "--fw-ver", help="firmware version to download (if omitted, fetch latest)"
        )
        dl.add_argument("-R", "--resume", action="store_true", help="resume unfinished download")
        dl.add_argument(
            "--no-decrypt", action="store_true", help="skip auto‑decrypt after download"
        )
        dl.add_argument("-O", "--out-dir", default="./downloads", help="directory to save firmware")

        # check
        subs.add_parser("check", help="print latest available firmware version")

        # decrypt
        dec = subs.add_parser("decrypt", help="manually decrypt an encrypted firmware")
        dec.add_argument("-v", "--fw-ver", required=True, help="encrypted firmware version")
        dec.add_argument(
            "-V", "--enc-ver", type=int, choices=[2, 4], default=4, help="encryption version"
        )
        dec.add_argument("-i", "--in-file", required=True, help="input .enc2/.enc4 file")
        dec.add_argument("-o", "--out-file", required=True, help="output decrypted file")

    def run(self) -> int:
        """
        Entry point: parse args and invoke the appropriate workflow.

        :return: exit code (0 on success)
        """
        args = self.parser.parse_args()

        # Device ID validation/fill (IMEI or Serial Number)
        if IMEIUtils.fixup_device_id(args):
            return 1

        # check
        if args.command == "check":
            if args.dev_region:
                args.fw_ver = getlatestver(args.dev_model, args.dev_region)
                try:
                    print(FirmwareUtils.format_firmware_info(args.fw_ver))
                except Exception as e:
                    print(args.fw_ver)
                    print(f"Note: Could not parse firmware version format: {e}")

            else:
                # Create a thread-safe print lock to avoid garbled output
                print_lock = threading.Lock()
                
                def check_region(region_pair):
                    """Worker function to check firmware for a single region"""
                    region, name = region_pair
                    try:
                        ver = getlatestver(args.dev_model, region)
                        with print_lock:
                            print(f"CSC [{region}] ({name}) -> {ver}")
                        return True
                    except Exception as e:
                        with print_lock:
                            print(f"CSC [{region}] ({name}) -> not found. {e}")
                        return False

                # Use ThreadPoolExecutor with 10 workers to check all regions in parallel
                with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                    # Submit all regions to the thread pool and wait for completion
                    list(executor.map(check_region, CSC_DICT.items()))
                    
            return 0

        # download needs region
        if args.command == "download" and not args.dev_region:
            print("Error: --dev-region is required for download")
            return 1

        if args.command == "download":
            # get version
            if not args.fw_ver:
                args.fw_ver = getlatestver(args.dev_model, args.dev_region)
            # Display firmware information
            try:
                print(FirmwareUtils.format_firmware_info(args.fw_ver))
            except Exception as e:
                print("latest version:", args.fw_ver)
                print(f"Note: Could not parse firmware version format: {e}")

            client = FUSClient()
            device_id = IMEIUtils.get_device_id(args)
            path, fname, size = getbinaryfile(
                client, args.fw_ver, args.dev_model, device_id, args.dev_region
            )
            os.makedirs(args.out_dir, exist_ok=True)
            if not os.path.isdir(args.out_dir):
                print(f"{args.out_dir} is not a directory")
                return 1

            out = os.path.join(args.out_dir, fname)
            offset = os.stat(out).st_size if (args.resume and os.path.exists(out)) else 0
            print(("resuming" if offset else "downloading"), fname)
            if offset != size:
                with open(out, "ab" if offset else "wb") as fd:
                    initdownload(client, fname)
                    r = client.downloadfile(path + fname, offset)
                    pbar = tqdm(total=size, initial=offset, unit="B", unit_scale=True)
                    for chunk in r.iter_content(0x10000):
                        if not chunk:
                            break
                        fd.write(chunk)
                        fd.flush()
                        pbar.update(len(chunk))
                    pbar.close()

            # auto‑decrypt
            if not args.no_decrypt and fname.endswith((".enc2", ".enc4")):
                dec = out.rsplit(".", 1)[0]
                if os.path.exists(dec):
                    print(f"{dec} exists, skipping decrypt")
                else:
                    print("decrypting", out)
                    ver = 2 if fname.endswith(".enc2") else 4
                    decrypt_file(args, ver, out, dec)
                    os.remove(out)
            return 0

        # manual decrypt
        if args.command == "decrypt":
            return decrypt_file(args, args.enc_ver, args.in_file, args.out_file)

        return 0


if __name__ == "__main__":
    sys.exit(GNSFApp().run())