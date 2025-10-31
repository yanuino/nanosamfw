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
