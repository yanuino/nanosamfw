# nanosamfw Documentation

![nanosamfw Logo](assets/images/256.png){ width="256" style="display:block; margin: 0 auto" }

**nanosamfw** (NotANOtherSamsungFirmware downloader) is a Python package providing programmatic access to Samsung firmware downloads through the Samsung Firmware Update Service (FUS).

## Overview

This package offers a clean, well-documented Python API for:

- **Firmware Discovery**: Query latest firmware versions for Samsung devices
- **Secure Downloads**: Download firmware with resume capability and encryption support
- **Decryption**: Automatic decryption of ENC2/ENC4 encrypted firmware files
- **Database Tracking**: Built-in SQLite tracking for downloads and IMEI operations
- **Integration Ready**: Designed for easy integration into tools and workflows

## Key Features

### 🔐 Full FUS Protocol Support
- BinaryInform, BinaryInit, and BinaryDownload operations
- Server nonce handling and signature generation
- Device ID (IMEI/Serial) validation

### 📦 High-Level Download API
- One-line firmware downloads with automatic version resolution
- HTTP Range support for resuming interrupted downloads
- Progress callback support for custom UI integration

### 🔓 Firmware Decryption
- ENC2 (MD5-based) and ENC4 (logic-value-based) decryption
- Automatic key derivation from FUS responses
- Streaming decryption with progress tracking

### 💾 Firmware Repository
- Centralized firmware storage (no duplication per model/CSC)
- Cached InformInfo metadata for efficient operations
- IMEI event logging with status tracking
- Repository pattern for clean data access

## Architecture

nanosamfw uses a three-layer architecture for clean separation of concerns:

```
┌─────────────────────────────────────────────────────┐
│                   Service Layer                      │
├─────────────────────────────────────────────────────┤
│ check_firmware()         │ FOTA query + IMEI log    │
│ get_or_download_firmware()│ Smart download          │
│ decrypt_firmware()       │ Repository → decrypted   │
│ download_and_decrypt()   │ Full workflow           │
└─────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────┐
│                Repository Layer                      │
├─────────────────────────────────────────────────────┤
│ firmware_repository.py   │ FirmwareRecord CRUD      │
│ imei_repository.py       │ IMEIEvent logging        │
└─────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────┐
│                  Database Layer                      │
├─────────────────────────────────────────────────────┤
│ firmware.db              │                          │
│  ├─ firmware (repository)│ version → file + metadata│
│  └─ imei_log (tracking)  │ requests + operations   │
└─────────────────────────────────────────────────────┘
```

**Key Design Principles:**

- **Firmware Repository**: Centralized storage - one record per firmware version (no model/CSC duplication)
- **Smart Downloads**: Checks repository before downloading from FUS servers
- **Cached Metadata**: Stores InformInfo data including logic values for efficient decryption
- **Separation of Concerns**: FOTA check, download, and decrypt are independent operations
- **Request Tracking**: IMEI log captures all queries separately from firmware repository

## Quick Start

### Complete Workflow

```python
from download import download_and_decrypt

# Download and decrypt in one call
firmware, decrypted = download_and_decrypt(
    model="SM-G998B",
    csc="EUX",
    device_id="352976245060954",
    resume=True,
)

print(f"Version: {firmware.version_code}")
print(f"Decrypted file: {decrypted}")
```

### Separate Operations

```python
from download import check_firmware, get_or_download_firmware, decrypt_firmware

# 1. Check FOTA for latest version
version = check_firmware("SM-G998B", "EUX", "352976245060954")
print(f"Latest: {version}")

# 2. Download to repository (if not already present)
firmware = get_or_download_firmware(version, "SM-G998B", "EUX", "352976245060954")
print(f"Encrypted file: {firmware.encrypted_file_path}")

# 3. Decrypt from repository (can be deferred!)
decrypted = decrypt_firmware(version)
print(f"Decrypted file: {decrypted}")
```

### Repository Queries

```python
from download import find_firmware, list_firmware

# Find specific version
fw = find_firmware("G998BXXU1ATCT/...")
if fw:
    print(f"Logic value: {fw.logic_value_factory}")
    print(f"Size: {fw.size_bytes} bytes")

# List all firmware in repository
for fw in list_firmware(limit=10):
    print(f"{fw.version_code}: {fw.filename}")
```

## Requirements

- Python 3.12 or higher
- Dependencies:
  - `pycryptodome` - Cryptographic operations
  - `requests` - HTTP client
  - `tqdm` - Progress bars

## Installation

```bash
pip install -r requirements.txt
```

## Project Structure

### Core Modules

- **[fus](api/fus.client.md)** - FUS protocol client and utilities
  - Client implementation with session management
  - Cryptographic operations and key derivation
  - Firmware version parsing and normalization
  - Device ID validation (IMEI/Serial)

- **[download](api/download.service.md)** - High-level download service
  - Firmware repository management
  - FOTA version checking with IMEI logging
  - Smart download (skips if already in repository)
  - On-demand decryption with cached logic values
  - Configuration and path management

## Documentation Sections

- **Core API** - FUS client, cryptography, device validation
- **Download API** - Service layer, repositories, configuration
- **Database** - Schema documentation and repository patterns

## License

This project is MIT licensed. See the LICENSE file for details.

## Contributing

Contributions are welcome! Please ensure:

- Code follows PEP 8 and project style guidelines (100 char line length)
- Type hints are provided for all public APIs
- Google-style docstrings document all functions
- Tests cover new functionality

## Links

- [GitHub Repository](https://github.com/yanuino/nanosamfw)
- [Issue Tracker](https://github.com/yanuino/nanosamfw/issues)
