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

### 💾 Database Integration
- SQLite-based download history
- IMEI event logging with status tracking
- Repository pattern for clean data access

## Quick Start

```python
from download.service import download_firmware

# Download latest firmware for a device
record = download_firmware(
    model="SM-G998B",
    csc="EUX",
    device_id="352976245060954",
    decrypt=True,  # Automatically decrypt after download
    resume=True,   # Resume if interrupted
)

print(f"Downloaded to: {record.path}")
print(f"Version: {record.version_code}")
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
  - Firmware download orchestration
  - Database repositories for tracking
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
