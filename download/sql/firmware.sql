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