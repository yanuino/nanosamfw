# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Yannick Locque (yanuino)

import xml.etree.ElementTree as ET
from xml.dom import minidom

from fus import FUSClient, get_latest_version, get_v4_key
from fus.firmware import normalize_vercode, read_firmware_info
from fus.messages import build_binary_inform
from fus.responses import parse_inform

model, region = "SM-A146P", "EUX"  # EUX
tac = "35297624"  # code TAC à 8 chiffres
imei = "352976245060954"  # sera auto‑complété à 15 chiffres
ver = get_latest_version(model, region)  # latest via version.xml FOTA
info = read_firmware_info(ver)
print(f"Latest: {ver}\nBL: {info['bl']}\nDate: {info['date']}\nIter: {info['it']}")

key = get_v4_key(ver, model, region, imei)
print(f"Decryption key: {key.hex()}")  # type: ignore

client = FUSClient()
ver = normalize_vercode(ver)
print(f"Normalized version: {ver}")

inform_xml = client.inform(
    build_binary_inform(fwv=ver, model=model, region=region, device_id=imei, nonce=client.nonce)
)


raw = ET.tostring(inform_xml, encoding="unicode")
pretty = minidom.parseString(raw).toprettyxml(indent="  ")

# print(f"Inform response received: {pretty}")

info_inform = parse_inform(inform_xml)
print(
    f"Inform info: Latest FW: {info_inform.latest_fw_version}, ",
    f"Logic: {info_inform.logic_value_factory}, ",
    f"Filename: {info_inform.filename},",
    f"Path: {info_inform.path},",
    f"Size: {info_inform.size_bytes} bytes",
)
