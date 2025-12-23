# Copilot Instructions for nanosamfw

## Project Overview
nanosamfw (NotANOtherSamsungFirmware downloader) is a Python package for programmatic access to Samsung firmware downloads. It provides:
- A backend client for Samsung Firmware Update Service (FUS)
- High-level API for firmware downloads using Model, CSC, and IMEI
- Device detection and information reading (cross-platform via pyserial)
- Integration capabilities for tools and workflows

## Technical Requirements
- Python 3.12 or higher (3.14+ in pyproject.toml)
- Core Dependencies: `pycryptodome`, `requests`, `tqdm`
- Device Detection: `pyserial>=3.5` (cross-platform)
- SQLite for firmware/IMEI tracking
- MkDocs Material for documentation

## Architecture & Data Flow

### Three-Package Design
The codebase is organized into three main packages:

1. **Device Package** (`device/`) - Device detection and reading (dual protocol support)
   - Cross-platform Samsung device detection via `serial.tools.list_ports`
   - **Two Protocol Options**:
     - **Odin Protocol** (`reader.py`) - For download mode devices (based on SharpOdinClient)
       - DVIF command (0x44,0x56,0x49,0x46) reads device info: model, fwver, sales, etc.
       - ODIN command (0x4F,0x44,0x49,0x4E) verifies download mode (expects "LOKE")
       - Communication at 115200 baud with RTS/CTS flow control
       - Device must be in download mode (Volume Down + Home + Power)
       - Returns `OdinDeviceInfo` dataclass
       - **Note**: DVIF may not work on all devices/firmware versions
     - **AT Commands** (`reader_at.py`) - For normal/recovery mode devices
       - AT+DEVCONINFO command for device information
       - Parses semicolon-delimited key-value format: `MN(model);VER(fw);PRD(sales);IMEI(imei);...`
       - Standard serial communication (115200 baud, no special flow control)
       - Returns `ATDeviceInfo` dataclass with model, firmware_version (PDA/CSC/MODEM/BOOTLOADER), sales_code, imei
   - No platform restrictions (works on Windows, Linux, macOS)
   - Requires Samsung USB drivers on Windows for serial port access

2. **FUS Package** (`fus/`) - Low-level protocol

   - `FUSClient` manages session, NONCE rotation, signature generation
   - Each request to Samsung servers follows: NONCE → Sign → Request → Parse
   - NONCE is server-provided, encrypted with `KEY_1` (see `crypto.py`)
   - Signatures use client-side NONCE + logic-check algorithm
   - XML payloads built via `messages.py`, parsed via `responses.py`

3. **Download Package** (`download/`) - Service & repository layer
   - Three-layer architecture: Service → Repository → Database
   - Service functions: `check_firmware()`, `get_or_download_firmware()`, `decrypt_firmware()`, `download_and_decrypt()`
   - Repository pattern with `FirmwareRecord` (one per version, no model/CSC duplication)
   - Database uses explicit transaction management (WAL mode, autocommit)
   - Files organized as `data/firmware/filename.enc4` and `data/decrypted/filename`

4. **GUI Application** (`app/`) - Graphical user interface
   - Built with customtkinter for modern dark-mode UI
   - Automatic device detection and firmware download workflow
   - Configuration via TOML file (`app/config.toml`)
   - Real-time progress tracking with stop functionality
   - Automatic repository cleanup on startup
   - **Modular Architecture** (6 focused modules):
     - `gui.py` (280 lines) - Main window coordination & app lifecycle
     - `device_monitor.py` (363 lines) - Device detection & firmware orchestration
     - `ui_builder.py` (352 lines) - UI widget creation & layout
     - `ui_updater.py` (230 lines) - Thread-safe UI updates via `after()`
     - `progress_tracker.py` (154 lines) - Progress calculations, ETA, throughput
     - `config.py` (84 lines) - Configuration loading from TOML

### Critical FUS Protocol Flow
```python
# 1. Client bootstrap (auto in __init__)
client = FUSClient()  # Gets initial NONCE from server

# 2. BinaryInform - query firmware metadata
xml = client.inform(build_binary_inform(version, model, csc, imei, client.nonce))
info = parse_inform(xml)  # Unified function (replaced get_info_from_inform)
# info.filename, info.path, info.size_bytes, info.latest_fw_version, info.logic_value_factory

# 3. BinaryInit - authorize download (uses logic_check on last 16 chars of filename)
client.init(build_binary_init(info.filename, client.nonce))

# 4. Download - stream with Range support (path concatenation fixed)
remote = info.path + info.filename  # Note: path includes trailing slash
response = client.stream(remote, start=0)  # Returns requests.Response

# 5. Decrypt - ENC4 key from cached logic_value (no extra FUS call needed)
key = get_v4_key_from_logic(version, info.logic_value_factory)
decrypt_file(enc_path, out_path, enc_ver=4, key=key)
```

### Device Detection Flow (Two Approaches)

**Option 1: AT Commands (Normal/Recovery Mode)**
```python
# For devices in normal mode or recovery mode
from device import read_device_info_at

# Read device info via AT commands
device = read_device_info_at()  # Auto-detects first device
# Or specify port: device = read_device_info_at("COM3")

# Returns ATDeviceInfo with: model, firmware_version (PDA/CSC/MODEM/BOOTLOADER), sales_code, imei
print(f"Model: {device.model}")
print(f"Firmware: {device.firmware_version}")
print(f"Region: {device.sales_code}")
print(f"IMEI: {device.imei}")

# Integration with firmware download (IMEI available)
from download import check_firmware, download_and_decrypt

latest = check_firmware(device.model, device.sales_code, device.imei)
if latest != device.firmware_version:
    firmware, decrypted = download_and_decrypt(
        device.model, device.sales_code, device.imei
    )
```

**Option 2: Odin Protocol (Download Mode)**
```python
# For devices in download mode (Odin mode)
from device import detect_download_mode_devices, is_odin_mode, read_device_info

# 1. Detect devices in download mode
devices = detect_download_mode_devices()  # Returns list with VID/PID
for device in devices:
    print(f"{device.port_name}: {device.device_name} ({device.vid}:{device.pid})")

# 2. Verify device is in Odin mode
if is_odin_mode(devices[0].port_name):
    print("Device in download mode")

# 3. Read device info via DVIF protocol (0x44,0x56,0x49,0x46)
info = read_device_info()  # Auto-detects first device
# Or specify port: info = read_device_info("COM3")
# Returns OdinDeviceInfo with: model, fwver, sales, vendor, un, did, etc.
# Response format: @key1=val1;key2=val2;...#
# Note: DVIF may not work on all devices - use AT commands as fallback

# 4. Integration with firmware download (no IMEI available)
from download import check_firmware, download_and_decrypt

latest = check_firmware(info.model, info.sales, "")  # Empty IMEI in download mode
if latest != info.fwver:
    firmware, decrypted = download_and_decrypt(info.model, info.sales, "")
```

### GUI Configuration (`app/config.toml`)
The GUI application uses a TOML configuration file for behavioral settings:

**File Location**: `app/config.toml`

**Configuration Sections**:
- `[gui]` section - UI element toggles:
  - `btn_dryrun` (bool): Show/hide "Dry run" checkbox in GUI
  - `btn_autofus` (bool): Show/hide "Auto FUS Mode" checkbox in GUI
  
- `[devices]` section - Device behavior:
  - `auto_fusmode` (bool): Automatically enter device into FUS mode when needed
  - `csc_filter` (string): Comma-separated list of CSC codes to filter devices (empty = no filtering)

**Usage Pattern**:
- Loaded via `app.config.load_config()` returning `AppConfig` dataclass
- Config changes require app restart to take effect
- Missing config file or keys use sensible defaults

**Example**:
```python
from app.config import load_config

config = load_config()  # Returns AppConfig dataclass
show_dryrun = config.btn_dryrun
auto_fusmode = config.auto_fusmode
csc_filter = config.csc_filter
```

### GUI Module Architecture
The `app/` package follows a modular design pattern for maintainability:

**Dependency Flow**:
```
gui.py (main orchestrator)
  ├─> config.py (settings via AppConfig dataclass)
  ├─> ui_builder.py (creates CTk widgets, returns dict)
  ├─> ui_updater.py (thread-safe updates via after())
  ├─> progress_tracker.py (calculations, callbacks)
  └─> device_monitor.py (AT detection, firmware ops)
        ├─> ui_updater (status/field updates)
        └─> progress_tracker (via callback)
```

**Module Responsibilities**:
- **gui.py**: Application window, lifecycle, icon setup, splash screen, monitoring coordination
- **config.py**: TOML parsing, AppConfig dataclass, defaults handling
- **ui_builder.py**: CTkFrame/CTkLabel/CTkEntry creation, layout logic, component organization
- **ui_updater.py**: Thread-safe UI updates via `after()`, widget state management
- **progress_tracker.py**: Throttled updates, ETA calculation, MB/s tracking, duration formatting
- **device_monitor.py**: AT command detection loop, firmware check/download/decrypt/extract, error handling

**Communication Patterns**:
- UI updates use `root.after(0, callback)` for thread safety
- Progress tracker uses callback pattern: `callback(stage, done, total, label)`
- Device monitor holds references to ui_updater and progress_callback
- Stop functionality via `stop_task` flag checked by device_monitor

### Key Integration Points
- **Database**: WAL mode, autocommit (isolation_level=None), explicit BEGIN/COMMIT
  - `firmware` table: one record per version_code (unique key)
  - `imei_log` table: tracks all FOTA queries
  - No model/CSC columns in firmware table (repository-centric design)
- **Cryptography**: 
  - `KEY_1`, `KEY_2` are hardcoded Samsung constants (in `crypto.py`)
  - ENC2 uses MD5 of `region:model:version`
  - ENC4 uses MD5 of logic_check result
  - `get_v4_key_from_logic()` computes key from cached logic_value (no FUS call needed)
- **File Operations**: 
  - Downloads use `.part` suffix for resume support
  - Atomic rename on completion
  - Firmware stored in `data/firmware/` (configurable via FIRM_DATA_DIR)
  - Decrypted files in `data/decrypted/` (configurable via FIRM_DECRYPT_DIR)
- **Device Detection**:
  - Uses `serial.tools.list_ports.comports()` for cross-platform enumeration
  - Identifies Samsung devices by "SAMSUNG MOBILE USB MODEM" in description
  - Extracts VID/PID from hardware ID (e.g., "USB VID:PID=04E8:685D")
  - **Odin Protocol (Download Mode)**:
    - DVIF protocol: sends bytes [0x44,0x56,0x49,0x46], parses @key=val;...# response
    - ODIN protocol: sends bytes [0x4F,0x44,0x49,0x4E], expects "LOKE" response
    - Communication: 115200 baud, RTS/CTS flow control, DTR/RTS off initially
    - Response keys: capa, product, model, fwver, vendor, sales, ver, did, un, tmu_temp, prov
  - **AT Protocol (Normal/Recovery Mode)**:
    - AT+DEVCONINFO command: `AT+DEVCONINFO\r\n`
    - Parses response format: `MN(model);VER(pda/csc/modem/bl);PRD(sales);IMEI(imei);...`
    - Communication: 115200 baud, standard serial (no special flow control)
    - Returns: model, firmware_version (full PDA/CSC/MODEM/BOOTLOADER), sales_code (PRD), imei

## Development Guidelines

### Code Style (from pyproject.toml and .vscode/settings.json)
- **Line Length**: 120 chars max (Black + Pylint enforced, ruler visible in editor)
- **Type Hints**: Required for all function parameters and return values
  - Pylance type checking mode: "standard"
  - Inlay hints enabled for variables and function returns
- **Docstrings**: Google-style for all public APIs
  - Use proper `Args:`, `Returns:`, `Raises:` sections
  - No parenthetical exception notes - use `ExceptionType: description` format
- **Import Ordering**: isort with profile "black"
  - Known first-party: `device`, `download`, `fus`
  - Use `combine_as_imports = true`
  - **CRITICAL**: All imports must be at top of module (Pylint standard mode enforced)
  - **NEVER** use lazy imports (e.g., `import` inside functions) unless absolutely necessary
  - Remove try/except ImportError wrappers for required dependencies
- **Formatting**: 
  - Black formatter runs on save (auto-format enabled)
  - isort runs on save (organizeImports code action)
  - String quotes: skip normalization (preserve original quotes)
- **Good Names**: Short names OK for:
  - Loops: `i`, `j`, `k`, `_`
  - Database: `id`, `pk`, `db`
  - Files: `fn`, `fp`
  - Exceptions: `ex`
  - Time: `ts`, `dt`

### Database Patterns
```python
# Always use explicit transactions (connection is autocommit)
with connect() as conn:
    conn.execute("BEGIN;")
    try:
        conn.execute(sql, params)
        conn.execute("COMMIT;")
    except Exception:
        conn.execute("ROLLBACK;")
        raise

# Use parameterized queries (dict or tuple)
conn.execute("INSERT INTO table (col) VALUES (:val)", {"val": value})
conn.execute("SELECT * FROM table WHERE id=?", (id,))

# Repository pattern returns dataclasses or yields them
def find_download(...) -> Optional[DownloadRecord]:
def list_downloads(...) -> Iterable[DownloadRecord]:
```

### Error Handling
- **FUS Errors** (`fus/errors.py`) with built-in message subtypes:
  - `FUSError` - Base class
  - `InformError` subtypes: `MissingStatus()`, `BadStatus(status)`, `MissingField(field_name)`, `DecryptionKeyError(model, region, device_id)`
  - `DownloadError` subtypes: `HTTPError(status_code, url)`
  - `DecryptError` subtypes: `DeviceIdRequired()`, `InvalidBlockSize(size)`
  - `DeviceIdError` subtypes: `InvalidTAC(tac)`
  - `FOTAError` subtypes: `ModelOrRegionNotFound(model, region)`, `NoFirmware(model, region)`
  - `FOTAParsingError(field, model, region)` - FOTA XML parsing errors
- **Device Errors** (`device/errors.py`): `DeviceError`, `DeviceNotFoundError`, `DeviceReadError`, `DeviceParseError`
- **Error Subtype Pattern**: Error classes have nested exception classes with self-managing messages
  - Example: `raise InformError.MissingField("BINARY_NAME")` instead of `raise InformError("Missing BINARY_NAME in inform response")`
  - Messages automatically include context (model, region, status codes, etc.)
- Propagate errors up - don't swallow without context
- Avoid catching generic `Exception` - use specific exception types

### Cryptographic Operations
- **Do not modify** `KEY_1`, `KEY_2` constants - they're Samsung-specific
- **Do not change** logic_check algorithm - it's protocol-defined
- Use established pycryptodome primitives (AES.new, PKCS padding)
- ENC4 key derivation: `get_v4_key_from_logic()` uses cached logic_value (no FUS call needed)
- InformInfo stores `logic_value_factory` for efficient decryption later

### Testing & Validation
- No test suite currently - use manual validation scripts:
  - `simple_client.py` - Basic firmware download
  - `example_device_detection.py` - AT command device detection (normal/recovery mode)
  - `example_odin_device_detection.py` - Odin protocol device detection (download mode)
- Test against real Samsung servers (be mindful of rate limiting)
- Verify cryptographic operations with known firmware files
- Check database integrity with `is_healthy()` before repairs
- Device detection: test on Windows with Samsung USB drivers installed

## Documentation Workflow

### Building Docs
```bash
# Local preview
mkdocs serve

# Build static site
mkdocs build -v

# Deploy to GitHub Pages
mkdocs gh-deploy
```

### API Documentation
- Uses mkdocstrings with Python handler
- Docstring style: Google (configured in mkdocs.yml)
- Auto-generated from source docstrings
- Manual pages in `docs/` (index.md, database/schema.md)

## Common Workflows

### Adding a New FUS Endpoint
1. Add XML builder to `fus/messages.py` (follow `_hdr()` + `_body_put()` pattern)
2. Add method to `FUSClient` (use `_makereq()`, return parsed ET.Element)
3. Add response parser to `fus/responses.py` if complex data needed
4. Update docstrings with Args/Returns/Raises

### Adding Database Tables
1. Add SQL schema string to `download/sql/__init__.py` (e.g., `NEW_TABLE_SCHEMA = """..."""`)
2. Append new schema to `SCHEMA_SQL` concatenation in `download/db.py`
3. Create dataclass in appropriate repository file
4. Add repository functions (find, list, upsert pattern)
5. Update `docs/database/schema.md` with table documentation

Note: SQL schemas are embedded as Python strings in `download/sql/__init__.py`, not as separate .sql files.

### Adding Device Detection Features
1. All device code goes in `device/` package
2. Use `serial.tools.list_ports` for device enumeration (cross-platform)
3. Use `serial.Serial` for AT command communication
4. Add custom exceptions to `device/errors.py` (inherit from `DeviceError`)
5. Update `device/__init__.py` exports and module docstring
6. Add documentation to `docs/api/device.*.md`
7. Test on Windows with Samsung USB drivers

### Debugging Issues
**Firmware Download:**
- Check `data/firmware.db` for firmware and imei_log records
- `.part` files indicate incomplete downloads
- Enable verbose logging by inspecting requests.Response objects
- Verify IMEI/Serial validation with `deviceid.py` helpers
- Path concatenation: `info.path` already includes trailing slash

**Device Detection:**
- Use `detect_samsung_devices()` to see all detected ports
- Check port attributes: `.manufacturer`, `.description`, `.product`
- Windows: Ensure Samsung USB drivers installed (check Device Manager)
- Linux/macOS: Check user permissions for serial port access
- **AT Commands** (`read_device_info_at()`):
  - Response parsing: expects `MN(model);VER(pda/csc/modem/bl);PRD(sales);IMEI(imei);...` format
  - Returns `ATDeviceInfo` with model, firmware_version, sales_code, imei
  - Works in normal mode or recovery mode
- **Odin Protocol** (`read_device_info()`):
  - DVIF response parsing: expects `@key=val;key=val;...#` format
  - Returns `OdinDeviceInfo` with model, fwver, sales, vendor, un, did, etc.
  - Requires device in download mode (Volume Down + Home + Power)
  - DVIF may not work on all devices - use AT commands as fallback

**Code Quality:**
- Run Black formatter before committing
- Run isort to organize imports
- Check Pylint errors (no imports inside functions)
- Verify type hints with Pylance "standard" mode

## License and Attribution
This project is MIT licensed and builds upon GNSF (see: https://github.com/keklick1337/gnsf) by keklick1337.
- Maintain copyright notices in file headers
- Document significant changes
- Credit original authors when adapting code