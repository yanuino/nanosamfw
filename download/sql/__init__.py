# SPDX-License-Identifier: MIT
# SQL schema definitions

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
  encrypted_file_path   TEXT NOT NULL,
  decrypted_file_path   TEXT,
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
  imei             TEXT NOT NULL,
  model            TEXT NOT NULL,
  csc              TEXT NOT NULL,
  version_code     TEXT NOT NULL, 
  status_fus       TEXT NOT NULL DEFAULT 'unknown'
                      CHECK (status_fus IN ('ok','error','denied','unauthorized','throttled','unknown')),
  status_upgrade   TEXT NOT NULL DEFAULT 'unknown'
                      CHECK (status_upgrade IN ('queued','in_progress','ok','failed','skipped','unknown')),
  created_at       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
  upgrade_at       TEXT,

  -- 4 parts: AAA/BBB/CCC/DDD
  CHECK ((length(version_code) - length(replace(version_code, '/', ''))) = 3),

  -- Permit multiple CSCs: EUX, EUX/FTM, etc.
  CHECK (length(csc) BETWEEN 3 AND 5)
);


CREATE INDEX IF NOT EXISTS idx_imei_log__imei_created
ON imei_log (imei, created_at DESC);


CREATE INDEX IF NOT EXISTS idx_imei_log__model_csc_created
ON imei_log (model, csc, created_at DESC);


CREATE INDEX IF NOT EXISTS idx_imei_log__model_csc_version
ON imei_log (model, csc, version_code);


CREATE INDEX IF NOT EXISTS idx_imei_log__created_at
ON imei_log (created_at);

CREATE INDEX IF NOT EXISTS idx_imei_log__upgrade_at
ON imei_log (upgrade_at);
"""
