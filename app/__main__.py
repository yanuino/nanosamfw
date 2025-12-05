# SPDX-License-Identifier: MIT
# Copyright (c) 2025 nanosamfw contributors

"""Entry point for running the GUI application as a module.

Usage:
    python -m app
    python app/__main__.py
    python app/gui.py
"""

import sys
from pathlib import Path

# Ensure project root is in path for imports (device, download, fus)
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.gui import main  # pylint: disable=C0413,C0415

if __name__ == "__main__":
    main()
