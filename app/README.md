# Samsung Firmware Downloader GUI

Graphical user interface application for automatic Samsung firmware downloading.

## Features

- 🔍 **Automatic Device Detection** - Monitors for connected Samsung devices using AT commands
- 📥 **Automatic Downloads** - Downloads latest firmware when available
- 📊 **Real-time Progress** - Shows download and decryption progress
- 🎨 **Modern UI** - Clean Material Design-inspired interface with dark theme
- 💾 **Smart Repository** - Caches downloaded firmware to avoid re-downloads
- ⚡ **Cross-platform** - Works on Windows, Linux, and macOS

## Requirements

- Python 3.12 or higher
- Samsung USB drivers (Windows)
- Device in normal mode or recovery mode (AT commands)

## Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Or install the package
pip install -e .
```

## Usage

### Run as Module

```bash
python -m app
```

### Run Directly

```bash
python app/gui.py
```

### Programmatic Usage

```python
from app import FirmwareDownloaderApp

app = FirmwareDownloaderApp()
app.run()
```

## How It Works

1. **Connect Device** - Connect your Samsung device via USB (normal mode or recovery mode)
2. **Start Monitoring** - Click "Start Monitoring" button
3. **Automatic Detection** - App detects device and reads information via AT commands
4. **Firmware Check** - Automatically checks for latest firmware from Samsung FOTA servers
5. **Auto Download** - If firmware is available and newer, downloads automatically
6. **Progress Tracking** - Shows real-time download and decryption progress
7. **Completion** - Displays saved firmware location

## Device Modes

The app supports Samsung devices in:

- **Normal Mode** - Regular phone operation (AT commands via USB)
- **Recovery Mode** - Recovery menu (AT commands via USB)

For devices in **Download Mode** (Odin), use `example_odin_device_detection.py` instead.

## Interface Overview

```
┌─────────────────────────────────────────┐
│   Samsung Firmware Downloader           │
├─────────────────────────────────────────┤
│ Status: Waiting for device...          │
├─────────────────────────────────────────┤
│ Device Information:                     │
│ Model: SM-A536B                         │
│ Firmware: A536BXXSHFYI1                 │
│ Region: EUX                             │
│ IMEI: 350498050169632                   │
├─────────────────────────────────────────┤
│ Download Progress:                      │
│ ████████████████░░░░  75%               │
│ Downloading: 6.0 GB / 8.0 GB            │
├─────────────────────────────────────────┤
│ [Start Monitoring] [Stop Monitoring]    │
└─────────────────────────────────────────┘
```

## Configuration

Firmware is saved to:
- **Encrypted**: `data/firmware/` (configurable via `FIRM_DATA_DIR`)
- **Decrypted**: `data/decrypted/` (configurable via `FIRM_DECRYPT_DIR`)

## Error Messages

- **"No firmware available"** - Model/region not found or no updates available
- **"Device error"** - Cannot read device information (check drivers/cables)
- **"Error checking firmware"** - Network or FOTA server issue

## Troubleshooting

**No Device Detected:**
1. Check USB cable connection
2. Install Samsung USB drivers (Windows)
3. Enable USB debugging (Android settings)
4. Try recovery mode (Volume Up + Home + Power)

**Permission Errors (Linux):**
```bash
sudo usermod -a -G dialout $USER
# Logout and login again
```

**Import Errors:**
```bash
# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

## License

MIT License - See LICENSE file for details

Copyright (c) 2025 nanosamfw contributors
