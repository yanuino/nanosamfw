# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Vladislav Tislenko (keklick1337)
# Copyright (c) 2025 Yannick Locque (yanuino)

"""Download module configuration.

This module provides configuration for download paths and directories used
throughout the download module.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Paths:
    """Configuration paths for download operations.

    This dataclass holds all filesystem paths used by the download module,
    including the data directory, database path, and downloads directory.

    Attributes:
        data_dir: Root directory for application data storage.
        db_path: Path to the SQLite database file.
        downloads_dir: Directory where firmware files are downloaded.
    """

    data_dir: Path
    db_path: Path
    downloads_dir: Path


def _resolve_paths() -> Paths:
    """Resolve and create configuration paths.

    Determines the root data directory from the FIRM_DATA_DIR environment
    variable or uses './data' as default, then constructs all required paths.

    Returns:
        Paths: Configuration object containing all resolved filesystem paths.

    Note:
        The data directory can be overridden by setting the FIRM_DATA_DIR
        environment variable.
    """
    data_root = Path(os.environ.get("FIRM_DATA_DIR", "./data")).resolve()
    return Paths(
        data_dir=data_root,
        db_path=data_root / "firmware.db",
        downloads_dir=data_root / "downloads",
    )


PATHS = _resolve_paths()
"""Global paths configuration instance.

This constant provides access to all configured paths used by the download module.
"""
