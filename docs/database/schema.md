# Database Schema

This document describes the database schema used by nanosamfw for tracking firmware in the repository and IMEI operations.

## Overview

The application uses SQLite for local data persistence with two main tables:

- **firmware** - Firmware repository with metadata from FUS inform responses
- **imei_log** - Logs IMEI-based firmware queries and upgrade operations

## Tables

### firmware

Firmware repository storing one record per firmware version with all metadata from Samsung FUS servers.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | INTEGER | PRIMARY KEY | Auto-incrementing unique identifier |
| `version_code` | TEXT | NOT NULL, UNIQUE | Firmware version identifier (4-part format: AAA/BBB/CCC/DDD) |
| `filename` | TEXT | NOT NULL | Binary firmware filename from FUS server |
| `path` | TEXT | NOT NULL | Server model path from FUS inform response |
| `size_bytes` | INTEGER | NOT NULL | File size in bytes |
| `logic_value_factory` | TEXT | NOT NULL | Logic value for ENC4 decryption key derivation |
| `latest_fw_version` | TEXT | NOT NULL | Latest firmware version from inform response |
| `encrypted_file_path` | TEXT | NOT NULL | Absolute path to encrypted (.enc4) file on disk |
| `decrypted_file_path` | TEXT | - | Absolute path to decrypted file, or NULL if not decrypted |
| `created_at` | TEXT | NOT NULL, DEFAULT (now) | ISO 8601 timestamp of creation |
| `updated_at` | TEXT | NOT NULL, DEFAULT (now) | ISO 8601 timestamp of last update |

**Unique Constraint:** `version_code` (one record per firmware version)

**Check Constraint:** `version_code` must have exactly 3 slashes (4-part format)

#### Indexes

- `idx_firmware_version` - Index on `version_code` for fast lookups
- `idx_firmware_filename` - Index on `filename` for search by filename

#### Triggers

- `trg_firmware_updated_at` - Automatically updates `updated_at` timestamp on row updates

---

### imei_log

Logs IMEI-based firmware query and upgrade operations with status tracking.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | INTEGER | PRIMARY KEY | Auto-incrementing unique identifier |
| `imei` | TEXT | NOT NULL | Device IMEI number |
| `model` | TEXT | NOT NULL | Device model identifier |
| `csc` | TEXT | NOT NULL, CHECK length | Country Specific Code (3-5 chars, supports multi-CSC like EUX/FTM) |
| `version_code` | TEXT | NOT NULL, CHECK format | Firmware version in AAA/BBB/CCC/DDD format |
| `status_fus` | TEXT | NOT NULL, DEFAULT 'unknown' | FUS query status (ok, error, denied, unauthorized, throttled, unknown) |
| `status_upgrade` | TEXT | NOT NULL, DEFAULT 'unknown' | Upgrade operation status (queued, in_progress, ok, failed, skipped, unknown) |
| `created_at` | TEXT | NOT NULL, DEFAULT (now) | ISO 8601 timestamp of log entry creation |
| `upgrade_at` | TEXT | - | ISO 8601 timestamp when upgrade operation occurred |

**Constraints:**

- `status_fus` must be one of: `ok`, `error`, `denied`, `unauthorized`, `throttled`, `unknown`
- `status_upgrade` must be one of: `queued`, `in_progress`, `ok`, `failed`, `skipped`, `unknown`
- `version_code` must contain exactly 3 forward slashes (AAA/BBB/CCC/DDD format)
- `csc` length must be between 3 and 5 characters

#### Indexes

- `idx_imei_log__imei_created` - Composite index on `(imei, created_at DESC)` for IMEI history queries
- `idx_imei_log__model_csc_created` - Composite index on `(model, csc, created_at DESC)` for device queries
- `idx_imei_log__model_csc_version` - Composite index on `(model, csc, version_code)` for version lookups
- `idx_imei_log__created_at` - Index on `created_at` for chronological queries
- `idx_imei_log__upgrade_at` - Index on `upgrade_at` for upgrade operation queries

## SQL Schema Files

The schema definitions are maintained in the following source files:

- `download/sql/download.sql` - Downloads table schema
- `download/sql/imei_log.sql` - IMEI log table schema

## Usage

The database is managed through the repository pattern:

- [download.firmware_repository](../api/download.firmware_repository.md) - Firmware repository operations
- [download.imei_repository](../api/download.imei_repository.md) - IMEI log operations
- [download.service](../api/download.service.md) - High-level service functions
- [download.db](../api/download.db.md) - Database connection management
