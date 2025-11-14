# SPDX-License-Identifier: MIT
# SQL schema definitions

from pathlib import Path

_SQL_DIR = Path(__file__).parent

# Load schema files
FIRMWARE_SCHEMA = (_SQL_DIR / "firmware.sql").read_text()
IMEI_LOG_SCHEMA = (_SQL_DIR / "imei_log.sql").read_text()
