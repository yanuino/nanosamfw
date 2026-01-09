# SPDX-License-Identifier: MIT
# SQL schema definitions
"""Embedded SQL schemas for firmware and IMEI logging."""

# Embedded SQL schemas for reliable packaging
FIRMWARE_SCHEMA = """
-- Firmware repository table
CREATE TABLE IF NOT EXISTS firmware (
  id                    INTEGER PRIMARY KEY,
  version_code          TEXT NOT NULL UNIQUE,
  filename              TEXT NOT NULL,
  path                  TEXT NOT NULL,
  size_bytes            INTEGER NOT NULL,
  logic_value_factory   TEXT NOT NULL,
  latest_fw_version     TEXT NOT NULL,
  downloaded            INTEGER NOT NULL DEFAULT 0 CHECK (downloaded IN (0, 1)),
  decrypted             INTEGER NOT NULL DEFAULT 0 CHECK (decrypted IN (0, 1)),
  extracted             INTEGER NOT NULL DEFAULT 0 CHECK (extracted IN (0, 1)),
  created_at            TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
  updated_at            TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
  
  -- 4 parts: AAA/BBB/CCC/DDD
  CHECK ((length(version_code) - length(replace(version_code, '/', ''))) = 3)
);

CREATE INDEX IF NOT EXISTS idx_firmware_version
ON firmware(version_code);

CREATE INDEX IF NOT EXISTS idx_firmware_filename
ON firmware(filename);

CREATE TRIGGER IF NOT EXISTS trg_firmware_updated_at
AFTER UPDATE ON firmware
FOR EACH ROW
BEGIN
  UPDATE firmware SET updated_at = strftime('%Y-%m-%dT%H:%M:%SZ','now') WHERE id = OLD.id;
END;
"""

IMEI_LOG_SCHEMA = """
-- IMEI events log table
CREATE TABLE IF NOT EXISTS imei_log (
  id               INTEGER PRIMARY KEY,
  session_id       TEXT NOT NULL,
  imei             TEXT NOT NULL,
  model            TEXT NOT NULL,
  csc              TEXT NOT NULL,
  version_code     TEXT NOT NULL,  -- Actual device firmware version (PDA/CSC/MODEM/BOOTLOADER)
  fota_version     TEXT,            -- FOTA/FUS firmware version (AAA/BBB/CCC/DDD format, nullable)
  serial_number    TEXT,            -- Device serial number (SN from AT)
  lock_status      TEXT,            -- Device lock status (LOCK from AT)
  aid              TEXT,            -- AID from AT (device/account identifier)
  cc               TEXT,            -- CC from AT (country code)
  status_fus       TEXT NOT NULL DEFAULT 'unknown'
                      CHECK (status_fus IN ('ok','error','denied','unauthorized','throttled','unknown')),
  status_upgrade   TEXT NOT NULL DEFAULT 'unknown'
                      CHECK (status_upgrade IN ('queued','in_progress','ok','failed','skipped','unknown')),
  created_at       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
  updated_at       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
  upgrade_at       TEXT,

  -- Permit multiple CSCs: EUX, EUX/FTM, etc.
  CHECK (length(csc) BETWEEN 3 AND 5),

  -- Unique constraint: one record per session+imei
  UNIQUE(session_id, imei)
);


CREATE INDEX IF NOT EXISTS idx_imei_log__session_imei
ON imei_log (session_id, imei);

CREATE INDEX IF NOT EXISTS idx_imei_log__imei_created
ON imei_log (imei, created_at DESC);


CREATE INDEX IF NOT EXISTS idx_imei_log__model_csc_created
ON imei_log (model, csc, created_at DESC);


CREATE INDEX IF NOT EXISTS idx_imei_log__model_csc_version
ON imei_log (model, csc, version_code);

CREATE INDEX IF NOT EXISTS idx_imei_log__serial_number
ON imei_log (serial_number);

CREATE INDEX IF NOT EXISTS idx_imei_log__aid
ON imei_log (aid);

CREATE INDEX IF NOT EXISTS idx_imei_log__cc
ON imei_log (cc);

CREATE INDEX IF NOT EXISTS idx_imei_log__created_at
ON imei_log (created_at);

CREATE INDEX IF NOT EXISTS idx_imei_log__upgrade_at
ON imei_log (upgrade_at);
"""
