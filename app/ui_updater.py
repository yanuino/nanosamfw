# SPDX-License-Identifier: MIT
# Copyright (c) 2025 nanosamfw contributors

"""Thread-safe UI update helpers for the GUI application.

This module provides helper functions for updating UI widgets from background
threads using Tkinter's after() mechanism for thread safety.
"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import customtkinter as ctk

if TYPE_CHECKING:
    from tkinter import Tk


class UIUpdater:
    """Manages thread-safe updates to UI widgets.

    All methods use the Tkinter after() mechanism to ensure updates
    happen on the main UI thread, avoiding race conditions.

    Attributes:
        root: Root Tkinter window for scheduling updates.
        widgets: Dictionary of widget references.
        logger: Logger instance for operation logging.
    """

    def __init__(self, root: "Tk", widgets: dict):
        """Initialize UI updater.

        Args:
            root: Root Tkinter window for after() scheduling.
            widgets: Dictionary containing all widget references.
        """
        self.root = root
        self.widgets = widgets
        self.logger = logging.getLogger(__name__)

    def update_status(self, message: str) -> None:
        """Update status label with thread-safe scheduling.

        Args:
            message: Status message to display.
        """
        self.root.after(0, lambda: self.widgets["status_label"].configure(text=message))

    def update_device_fields(
        self, model: str, firmware: str, region: str, imei: str, aid: str = "-", cc: str = "-"
    ) -> None:
        """Update device info entries (read-only display).

        Args:
            model: Device model.
            firmware: Firmware version.
            region: Region/CSC code.
            imei: IMEI string.
            aid: Application ID.
            cc: Country Code.
        """

        def _set(e: ctk.CTkEntry, text: str):
            e.configure(state="normal")
            e.delete(0, "end")
            e.insert(0, text)
            e.configure(state="disabled")

        def _update():
            _set(self.widgets["model_entry"], model or "-")
            _set(self.widgets["firmware_entry"], firmware or "-")
            _set(self.widgets["region_entry"], region or "-")
            _set(self.widgets["aid_entry"], aid or "-")
            _set(self.widgets["cc_entry"], cc or "-")
            _set(self.widgets["imei_entry"], imei or "-")

        self.root.after(0, _update)

    def set_device_placeholders(self) -> None:
        """Set placeholder text for device fields (no device detected)."""

        def _set(e: ctk.CTkEntry, text: str):
            e.configure(state="normal")
            e.delete(0, "end")
            e.insert(0, text)
            e.configure(state="disabled")

        def _update():
            _set(self.widgets["model_entry"], "-")
            _set(self.widgets["firmware_entry"], "-")
            _set(self.widgets["region_entry"], "-")
            _set(self.widgets["aid_entry"], "-")
            _set(self.widgets["cc_entry"], "-")
            _set(self.widgets["imei_entry"], "-")

        self.root.after(0, _update)

    def clear_component_entries(self) -> None:
        """Clear all firmware component entries."""

        def _clear(e: ctk.CTkEntry):
            e.configure(state="normal")
            e.delete(0, "end")
            e.configure(state="disabled")

        def _update():
            _clear(self.widgets["ap_entry"])
            _clear(self.widgets["bl_entry"])
            _clear(self.widgets["cp_entry"])
            _clear(self.widgets["csc_entry"])
            _clear(self.widgets["home_entry"])

        self.root.after(0, _update)

    def populate_component_entries(self, unzip_dir: Path) -> None:
        """Populate firmware component entries from unzipped directory.

        Args:
            unzip_dir: Directory containing unzipped firmware files.
        """

        def _set(e: ctk.CTkEntry, text: str):
            e.configure(state="normal")
            e.delete(0, "end")
            e.insert(0, text)
            e.configure(state="disabled")

        # Find files by prefix
        components: dict[str, str | None] = {
            "AP": None,
            "BL": None,
            "CP": None,
            "CSC": None,
            "HOME": None,
        }
        for file_path in unzip_dir.iterdir():
            if file_path.is_file():
                name = file_path.name
                for prefix in components:
                    if name.startswith(prefix):
                        components[prefix] = str(file_path.resolve())
                        break

        def _update():
            _set(self.widgets["ap_entry"], components["AP"] or "-")
            _set(self.widgets["bl_entry"], components["BL"] or "-")
            _set(self.widgets["cp_entry"], components["CP"] or "-")
            _set(self.widgets["csc_entry"], components["CSC"] or "-")
            _set(self.widgets["home_entry"], components["HOME"] or "-")

        self.root.after(0, _update)

    def update_progress_bar(self, stage: str, done: int, total: int, label: str) -> None:
        """Update progress bar and label.

        Args:
            stage: Stage name ("download", "decrypt", or "extract").
            done: Bytes or files processed.
            total: Total bytes or files.
            label: Formatted progress label text.
        """
        pct = done / total if total > 0 else 0.0
        self.logger.debug("Progress update - stage: %s, %.1f%% (%d/%d)", stage, pct * 100, done, total)

        def _update():
            self.widgets["progress_message"].pack_forget()
            if not self.widgets["progress_bar_container"].winfo_ismapped():
                self.widgets["progress_bar_container"].pack(fill="x", padx=10, pady=(0, 10))
            self.widgets["download_progress_bar"].set(pct)
            self.widgets["download_progress_label"].configure(text=label)

        self.root.after(0, _update)

    def update_progress_message(self, message: str, color: str = "info") -> None:
        """Update progress message with color coding.

        Args:
            message: Message to display.
            color: Color type - "info", "success", "warning", "error".
        """
        colors = {
            "info": ("#3B8ED0", "#1F6AA5"),
            "success": ("#2CC985", "#2FA572"),
            "warning": ("#FF9500", "#E68600"),
            "error": ("#FF453A", "#E0342F"),
        }
        fg_color = colors.get(color, colors["info"])

        def _update():
            self.widgets["progress_bar_container"].pack_forget()
            self.widgets["progress_message"].pack(fill="x", padx=10, pady=(0, 10))
            self.widgets["progress_message"].configure(text=message, fg_color=fg_color)

        self.root.after(0, _update)

    def update_stop_button_state(self, download_in_progress: bool, stop_task: bool) -> None:
        """Update stop button enabled/disabled state.

        Args:
            download_in_progress: Whether download is active.
            stop_task: Whether stop has been requested.
        """

        def _update():
            if download_in_progress and not stop_task:
                self.widgets["stop_button"].configure(state="normal")
            else:
                self.widgets["stop_button"].configure(state="disabled")

        self.root.after(0, _update)

    def update_cleanup_status(self, status: str, progress: float, details: str) -> None:
        """Update cleanup status during startup.

        Args:
            status: Status message.
            progress: Progress value (0.0 to 1.0).
            details: Detailed information.
        """

        def _update():
            if "cleanup_status" in self.widgets:
                self.widgets["cleanup_status"].configure(text=status)
            if "cleanup_progress" in self.widgets:
                self.widgets["cleanup_progress"].set(progress)
            if "cleanup_details" in self.widgets:
                self.widgets["cleanup_details"].configure(text=details)

        self.root.after(0, _update)
