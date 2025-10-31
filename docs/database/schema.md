# Database Schema

This document describes the database schema used by nanosamfw for tracking firmware downloads and IMEI operations.

## Overview

The application uses SQLite for local data persistence with two main tables:

- **downloads** - Tracks firmware download metadata and status
- **imei_log** - Logs IMEI-based firmware queries and upgrade operations

## Tables

### downloads

Stores metadata about firmware downloads including model, CSC, version, and download status.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | INTEGER | PRIMARY KEY | Auto-incrementing unique identifier |
| `model` | TEXT | NOT NULL | Device model identifier (e.g., SM-G998B) |
| `csc` | TEXT | NOT NULL | Country Specific Code |
| `version_code` | TEXT | NOT NULL | Firmware version identifier |
| `encoded_filename` | TEXT | NOT NULL | Encoded filename from FUS |
| `size_bytes` | INTEGER | - | File size in bytes |
| `status` | TEXT | NOT NULL, DEFAULT 'done' | Download status |
| `path` | TEXT | - | Local filesystem path to downloaded file |
| `created_at` | TEXT | NOT NULL, DEFAULT (now) | ISO 8601 timestamp of creation |
| `updated_at` | TEXT | NOT NULL, DEFAULT (now) | ISO 8601 timestamp of last update |

**Unique Constraint:** `(model, csc, version_code)`

#### Indexes

- `idx_downloads_model_csc` - Composite index on `(model, csc)` for efficient lookups

#### Triggers

- `trg_downloads_updated_at` - Automatically updates `updated_at` timestamp on row updates

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

The schema definitions are maintained in the following files:

- [`download/sql/download.sql`](../../download/sql/download.sql) - Downloads table schema
- [`download/sql/imei_log.sql`](../../download/sql/imei_log.sql) - IMEI log table schema

## Usage

The database is managed through the repository pattern:

- [download.repository](../api/download.repository.md) - Main download operations
- [download.imei_repository](../api/download.imei_repository.md) - IMEI log operations
- [download.db](../api/download.db.md) - Database connection management
