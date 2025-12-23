# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.2] - 2025-12-23

### Added
- CSC filter feature: configure allowed CSC codes in `config.toml` to filter devices by region
- HOME_CSC extraction control: `unzip_home_csc` config option to skip HOME_CSC files during firmware extraction
- Disconnect callback mechanism to reset task state when device disconnects
- PyInstaller support: config.toml now loads from .exe directory when packaged
- Comprehensive API documentation for all app modules
- Stop task functionality: ability to cancel active firmware download/decrypt/extract operations
- AID (Active IMEI Display) and CC (Country Code) fields to device info display and IMEI logging
- Config-based GUI controls: visibility toggles for dry run and auto FUS mode checkboxes
- Serial tool module for enhanced device communication

### Changed
- **Major refactoring**: Split monolithic `app/gui.py` (1084 lines) into 6 focused modules:
  - `app/config.py` - Configuration loading from TOML
  - `app/progress_tracker.py` - Progress calculations and ETA
  - `app/ui_updater.py` - Thread-safe UI updates
  - `app/device_monitor.py` - Device detection and firmware orchestration
  - `app/ui_builder.py` - UI widget creation
  - `app/gui.py` - Main application coordination (280 lines)
- Build script preserves `config.toml` in dist directory during clean operations
- Enhanced PyInstaller hidden imports to include all refactored app modules
- Device info fields now displayed before CSC filter check for better UX
- Reordered GUI widgets for improved layout and usability
- Enhanced device logging with AID and CC parameters
- Firmware check logic now includes additional parameters (AID, CC)
- IMEI repository schema extended with aid and cc columns

### Fixed
- Stop task flag not cleared on device disconnect, causing immediate stops on new device connections
- Progress bar stage parameter now properly logged for debugging

### Documentation
- Added GUI architecture guide (`docs/gui-architecture.md`)
- Updated Copilot instructions with GUI module architecture details
- Added API documentation for all 6 app modules
- Updated French user manual

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

[0.1.2]: https://github.com/yanuino/nanosamfw/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/yanuino/nanosamfw/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/yanuino/nanosamfw/compare/v0.0.1...v0.1.0
[0.0.1]: https://github.com/yanuino/nanosamfw/releases/tag/v0.0.1
