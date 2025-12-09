# SPDX-License-Identifier: MIT
# Copyright (c) 2025 nanosamfw contributors

"""Samsung Firmware Downloader GUI Application.

This package provides a graphical user interface for automatic Samsung firmware
downloading using CustomTkinter. The application monitors for connected Samsung
devices and automatically downloads the latest firmware when available.

Main Components:
    - DeviceMonitor: Background thread monitoring for device connections
    - FirmwareDownloader: Main application window with progress tracking
    - Auto-detection: Supports both AT commands and Odin protocol

Features:
    - Automatic device detection (AT commands and Odin mode)
    - Real-time firmware availability checking
    - Progress bars for download and decryption
    - Dark/light theme support
    - Cross-platform (Windows, Linux, macOS)

Example:
    Run the GUI application::

        python -m app

    Or programmatically::

        from app import FirmwareDownloaderApp

        app = FirmwareDownloaderApp()
        app.run()

Copyright (c) 2025 nanosamfw contributors
SPDX-License-Identifier: MIT
"""

from app.gui import FirmwareDownloaderApp

__all__ = ["FirmwareDownloaderApp"]
