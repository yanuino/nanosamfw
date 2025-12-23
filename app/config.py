# SPDX-License-Identifier: MIT
# Copyright (c) 2025 nanosamfw contributors

"""Configuration management for the GUI application.

This module handles loading and validation of configuration settings from
the config.toml file.
"""

import logging
import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass
class AppConfig:
    """Application configuration settings.

    Attributes:
        btn_dryrun: Show/hide "Dry run" checkbox in GUI.
        btn_autofus: Show/hide "Auto FUS Mode" checkbox in GUI.
        auto_fusmode: Automatically enter device into FUS mode when needed.
        csc_filter: Comma-separated list of CSC codes to filter devices.
    """

    btn_dryrun: bool
    btn_autofus: bool
    auto_fusmode: bool
    csc_filter: str


def load_config(config_path: Path | None = None) -> AppConfig:
    """Load configuration from config.toml file.

    Args:
        config_path: Path to config.toml file. If None, uses app/config.toml.

    Returns:
        AppConfig instance with loaded or default settings.
    """
    if config_path is None:
        config_path = Path(__file__).parent / "config.toml"

    logger = logging.getLogger(__name__)

    try:
        with open(config_path, "rb") as f:
            config = tomllib.load(f)

        # GUI settings
        gui_config = config.get("gui", {})
        btn_dryrun = gui_config.get("btn_dryrun", False)
        btn_autofus = gui_config.get("btn_autofus", True)

        # Device settings
        device_config = config.get("devices", {})
        auto_fusmode = device_config.get("auto_fusmode", True)
        csc_filter = device_config.get("csc_filter", "").strip()

        logger.info(
            "Config loaded: dryrun=%s, autofus=%s, auto_fusmode=%s, csc_filter=%s",
            btn_dryrun,
            btn_autofus,
            auto_fusmode,
            csc_filter,
        )

        return AppConfig(
            btn_dryrun=btn_dryrun,
            btn_autofus=btn_autofus,
            auto_fusmode=auto_fusmode,
            csc_filter=csc_filter,
        )

    except (FileNotFoundError, OSError) as ex:
        # Use defaults if config file not found
        logger.warning("Config file not found or error reading: %s. Using defaults.", ex)
        return AppConfig(
            btn_dryrun=False,
            btn_autofus=True,
            auto_fusmode=True,
            csc_filter="",
        )
