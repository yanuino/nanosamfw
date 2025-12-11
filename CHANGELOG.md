# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.1] - 2025-12-11

### Changed
- Increased firmware component path highlight duration from 200ms to 1 second for better visual feedback ([#5](https://github.com/yanuino/nanosamfw/pull/5))
- Firmware component paths (AP, BL, CP, CSC, HOME) now persist after device disconnection until a new device is detected ([#7](https://github.com/yanuino/nanosamfw/pull/7))

### Fixed
- Component entries are no longer cleared prematurely when device disconnects, improving workflow for manual flashing operations

## [0.1.0] - 2025-12-09

### Added
- GUI application with auto device detection
- FOTA firmware check functionality
- FUS download/decrypt/extract with progress bar and ETA
- Component paths display (AP/BL/CP/CSC) with click-to-copy functionality
- Session-based IMEI logging
- Firmware cache and reuse capability
- PyInstaller Windows one-file executable build support

### Changed
- Enhanced error handling with user-facing messages for FOTA/FUS errors (400/408)
- Read-only device fields in GUI
- Startup repository cleanup

### Documentation
- Updated flow documentation
- API documentation improvements
- Database schema notes

## [0.0.1] - 2025-10-31

### Added
- Initial project migration from GNSF
- Backend client for Samsung Firmware Update Service
- High-level API for firmware downloads (Model, CSC, IMEI)
- Device detection capabilities
- Core package structure (fus, download, device)
- Documentation setup with MkDocs
- Development environment configuration

[0.1.1]: https://github.com/yanuino/nanosamfw/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/yanuino/nanosamfw/compare/v0.0.1...v0.1.0
[0.0.1]: https://github.com/yanuino/nanosamfw/releases/tag/v0.0.1
