-- Downloads metadata table
CREATE TABLE IF NOT EXISTS downloads (
  id               INTEGER PRIMARY KEY,
  model            TEXT NOT NULL,
  csc              TEXT NOT NULL,
  version_code     TEXT NOT NULL,
  encoded_filename TEXT NOT NULL,
  size_bytes       INTEGER,
  status           TEXT NOT NULL DEFAULT 'done',
  path             TEXT,
  created_at       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
  updated_at       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
  UNIQUE(model, csc, version_code)
);

CREATE INDEX IF NOT EXISTS idx_downloads_model_csc
ON downloads(model, csc);

CREATE TRIGGER IF NOT EXISTS trg_downloads_updated_at
AFTER UPDATE ON downloads
FOR EACH ROW
BEGIN
  UPDATE downloads SET updated_at = strftime('%Y-%m-%dT%H:%M:%SZ','now') WHERE id = OLD.id;
END;