#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 nanosamfw contributors

"""Launcher script for Samsung Firmware Downloader GUI.

This script launches the CustomTkinter GUI application for automatic
Samsung firmware downloading.

Usage:
    python launch_gui.py
"""

import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.gui import main  # pylint: disable=C0413,C0415

if __name__ == "__main__":
    main()
