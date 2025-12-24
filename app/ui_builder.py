# SPDX-License-Identifier: MIT
# Copyright (c) 2025 nanosamfw contributors

"""UI widget creation and layout for the GUI application.

This module handles creation of all UI frames, widgets, and their layout
configuration using customtkinter.
"""

import logging
from collections.abc import Callable

import customtkinter as ctk
import pyperclip

from app.config import AppConfig


class UIBuilder:
    """Builds and configures all UI widgets for the application.

    Attributes:
        root: Root window for widget creation.
        config: Application configuration.
        logger: Logger instance.
    """

    def __init__(self, root: ctk.CTk, config: AppConfig):
        """Initialize UI builder.

        Args:
            root: Root CTk window.
            config: Application configuration.
        """
        self.root = root
        self.config = config
        self.logger = logging.getLogger(__name__)

    def create_main_widgets(self, stop_callback: Callable[[], None]) -> dict:
        """Create and layout all main application widgets.

        Args:
            stop_callback: Callback function for stop button clicks.

        Returns:
            Dictionary containing all widget references.
        """
        widgets = {}

        # Main container with padding
        main_frame = ctk.CTkFrame(self.root)
        main_frame.pack(fill="both", expand=True, padx=5, pady=5)

        # Title
        # title_label = ctk.CTkLabel(
        #     main_frame,
        #     text="Samsung Firmware Downloader",
        #     font=ctk.CTkFont(size=24, weight="bold"),
        # )
        # title_label.pack(pady=(0, 20))

        # Create all sub-frames
        self._create_status_frame(main_frame, widgets)
        self._create_device_info_frame(main_frame, widgets)
        self._create_progress_frame(main_frame, widgets, stop_callback)
        self._create_components_frame(main_frame, widgets)
        self._create_settings_frame(main_frame, widgets)

        return widgets

    def _create_status_frame(self, parent, widgets: dict) -> None:
        """Create status display frame.

        Args:
            parent: Parent widget.
            widgets: Widget dictionary to populate.
        """
        status_frame = ctk.CTkFrame(parent)
        status_frame.pack(fill="x", padx=5, pady=5)

        ctk.CTkLabel(status_frame, text="Status:", font=ctk.CTkFont(size=14, weight="bold")).pack(
            anchor="w", padx=10, pady=(10, 5)
        )

        status_label = ctk.CTkLabel(
            status_frame,
            text="Stopped. Press 'Start Monitoring' to begin device detection",
            font=ctk.CTkFont(size=12),
        )
        status_label.pack(anchor="w", padx=10, pady=(0, 10))
        widgets["status_label"] = status_label

    def _create_device_info_frame(self, parent, widgets: dict) -> None:
        """Create device information frame with entries.

        Args:
            parent: Parent widget.
            widgets: Widget dictionary to populate.
        """
        device_frame = ctk.CTkFrame(parent)
        device_frame.pack(fill="x", padx=5, pady=(0, 5))

        ctk.CTkLabel(device_frame, text="Device Information:", font=ctk.CTkFont(size=14, weight="bold")).pack(
            anchor="w", padx=10, pady=(10, 5)
        )

        # Grid for entries
        entries_frame = ctk.CTkFrame(device_frame)
        entries_frame.pack(fill="x", padx=10, pady=(0, 10))

        def _make_full_row(row: int, label: str) -> ctk.CTkEntry:
            ctk.CTkLabel(entries_frame, text=label, font=ctk.CTkFont(size=12, weight="bold")).grid(
                row=row, column=0, sticky="w", padx=4, pady=4
            )
            entry = ctk.CTkEntry(entries_frame, font=ctk.CTkFont(size=12))
            entry.grid(row=row, column=1, columnspan=5, sticky="ew", padx=(10, 4), pady=4)
            entry.configure(state="disabled")
            return entry

        def _make_col(row: int, col: int, label: str) -> ctk.CTkEntry:
            ctk.CTkLabel(entries_frame, text=label, font=ctk.CTkFont(size=12, weight="bold")).grid(
                row=row, column=col * 2, sticky="w", pady=4, padx=(10, 0) if col > 0 else 4
            )
            entry = ctk.CTkEntry(entries_frame, font=ctk.CTkFont(size=12))
            entry.grid(row=row, column=col * 2 + 1, sticky="ew", padx=(10, 4), pady=4)
            entry.configure(state="disabled")
            return entry

        # Configure columns for equal width
        entries_frame.grid_columnconfigure(1, weight=1)
        entries_frame.grid_columnconfigure(3, weight=1)
        entries_frame.grid_columnconfigure(5, weight=1)

        widgets["model_entry"] = _make_full_row(0, "Model")
        widgets["firmware_entry"] = _make_full_row(1, "Firmware")
        widgets["region_entry"] = _make_col(2, 0, "Region/CSC")
        widgets["aid_entry"] = _make_col(2, 1, "AID")
        widgets["cc_entry"] = _make_col(2, 2, "CC")
        widgets["imei_entry"] = _make_full_row(3, "IMEI")

    def _create_progress_frame(self, parent, widgets: dict, stop_callback) -> None:
        """Create progress display frame.

        Args:
            parent: Parent widget.
            widgets: Widget dictionary to populate.
            stop_callback: Callback for stop button.
        """
        progress_frame = ctk.CTkFrame(parent)
        progress_frame.pack(fill="x", padx=5, pady=(0, 5))

        ctk.CTkLabel(progress_frame, text="Progress:", font=ctk.CTkFont(size=14, weight="bold")).pack(
            anchor="w", padx=10, pady=(10, 5)
        )

        # Container for progress bar and stop button
        progress_bar_container = ctk.CTkFrame(progress_frame, fg_color="transparent")
        progress_bar_container.pack(fill="x", padx=10, pady=(0, 10))
        progress_bar_container.pack_forget()  # Hidden by default
        widgets["progress_bar_container"] = progress_bar_container

        # Progress bar frame (left side, expandable)
        progress_bar_frame = ctk.CTkFrame(progress_bar_container, fg_color="transparent")
        progress_bar_frame.pack(side="left", fill="both", expand=True, padx=(0, 10))

        download_progress_bar = ctk.CTkProgressBar(progress_bar_frame)
        download_progress_bar.pack(fill="x", pady=(0, 2))
        download_progress_bar.set(0)
        widgets["download_progress_bar"] = download_progress_bar

        download_progress_label = ctk.CTkLabel(progress_bar_frame, text="", font=ctk.CTkFont(size=11))
        download_progress_label.pack(anchor="w")
        widgets["download_progress_label"] = download_progress_label

        # Stop button (right side, fixed width)
        stop_button = ctk.CTkButton(
            progress_bar_container,
            text="Stop Task",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#FF453A",
            hover_color="#E0342F",
            command=stop_callback,
            width=100,
            bg_color="transparent",
        )
        stop_button.pack(side="right")
        widgets["stop_button"] = stop_button

        # Message label for highlighted text
        progress_message = ctk.CTkLabel(
            progress_frame,
            text="Waiting for device",
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=("#3B8ED0", "#1F6AA5"),
            corner_radius=8,
            height=40,
        )
        progress_message.pack(fill="x", padx=10, pady=(0, 10))
        widgets["progress_message"] = progress_message

    def _create_components_frame(self, parent, widgets: dict) -> None:
        """Create firmware components frame.

        Args:
            parent: Parent widget.
            widgets: Widget dictionary to populate.
        """
        components_frame = ctk.CTkFrame(parent)
        components_frame.pack(fill="x", padx=5, pady=(0, 5))

        ctk.CTkLabel(components_frame, text="Firmware Components:", font=ctk.CTkFont(size=14, weight="bold")).pack(
            anchor="w", padx=10, pady=(10, 5)
        )

        # Grid for component entries
        comp_entries_frame = ctk.CTkFrame(components_frame)
        comp_entries_frame.pack(fill="x", padx=10, pady=(0, 10))

        def _make_comp_row(row: int, label: str, *, hidden: bool = False) -> ctk.CTkEntry:
            label_widget = ctk.CTkLabel(
                comp_entries_frame,
                text=label,
                font=ctk.CTkFont(size=12, weight="bold"),
                cursor="hand2" if not hidden else "",
            )
            label_widget.grid(row=row, column=0, sticky="w", padx=4, pady=4)
            entry = ctk.CTkEntry(comp_entries_frame, font=ctk.CTkFont(size=11))
            entry.grid(row=row, column=1, sticky="ew", padx=(10, 4), pady=4)
            comp_entries_frame.grid_columnconfigure(1, weight=1)
            entry.configure(state="disabled")
            original_fg = entry.cget("fg_color")

            # Make label clickable to copy entry value to clipboard
            def _copy_to_clipboard(_e):
                value = entry.get()
                if value and value != "-":
                    try:
                        pyperclip.copy(value)
                        self.logger.info("Copied %s path to clipboard: %s", label, value)
                        # Brief visual feedback
                        entry.configure(fg_color="#2CC985")
                        self.root.after(1000, lambda: entry.configure(fg_color=original_fg))
                    except (OSError, RuntimeError) as ex:
                        self.logger.error("Failed to copy to clipboard: %s", ex)

            if not hidden:
                label_widget.bind("<Button-1>", _copy_to_clipboard)
                entry.bind("<Button-1>", _copy_to_clipboard)
            else:
                # Hide the widgets but keep them instantiated
                label_widget.grid_remove()
                entry.grid_remove()

            return entry

        widgets["ap_entry"] = _make_comp_row(0, "BL")
        widgets["bl_entry"] = _make_comp_row(1, "AP")
        widgets["cp_entry"] = _make_comp_row(2, "CP")
        widgets["csc_entry"] = _make_comp_row(3, "CSC")
        widgets["home_entry"] = _make_comp_row(4, "HOME", hidden=True)

    def _create_settings_frame(self, parent, widgets: dict) -> None:
        """Create settings frame with checkboxes.

        Args:
            parent: Parent widget.
            widgets: Widget dictionary to populate.
        """
        settings_frame = ctk.CTkFrame(parent)
        settings_frame.pack(fill="x", padx=5, pady=(0, 5))

        # Horizontal container
        settings_container = ctk.CTkFrame(settings_frame, fg_color="transparent")
        settings_container.pack(fill="x", padx=10, pady=10)

        # Dry run checkbox
        dryrun_checkbox = ctk.CTkCheckBox(
            settings_container,
            text="Dry run",
            font=ctk.CTkFont(size=12),
        )
        if not self.config.btn_dryrun:
            dryrun_checkbox.configure(state="disabled")
        dryrun_checkbox.pack(side="left", padx=(0, 20))
        widgets["dryrun_checkbox"] = dryrun_checkbox

        # Auto FUS Mode checkbox
        autofus_checkbox = ctk.CTkCheckBox(
            settings_container,
            text="Auto FUS Mode",
            font=ctk.CTkFont(size=12),
        )
        if self.config.auto_fusmode:
            autofus_checkbox.select()
            autofus_checkbox.configure(state="disabled")
        elif not self.config.btn_autofus:
            autofus_checkbox.configure(state="disabled")
        autofus_checkbox.pack(side="left", padx=(0, 20))
        widgets["autofus_checkbox"] = autofus_checkbox

        # CSC Filter label
        csc_label_text = f"CSC Filter: {self.config.csc_filter}" if self.config.csc_filter else "CSC Filter: (none)"
        csc_filter_label = ctk.CTkLabel(
            settings_container,
            text=csc_label_text,
            font=ctk.CTkFont(size=12),
        )
        csc_filter_label.pack(side="left", padx=(0, 20))
        widgets["csc_filter_label"] = csc_filter_label

    def create_splash_widgets(self) -> dict:
        """Create splash screen widgets for startup cleanup.

        Returns:
            Dictionary containing splash widget references.
        """
        widgets = {}

        splash_frame = ctk.CTkFrame(self.root)
        splash_frame.pack(fill="both", expand=True, padx=40, pady=40)
        widgets["splash_frame"] = splash_frame

        title = ctk.CTkLabel(
            splash_frame,
            text="Initializing Repository",
            font=ctk.CTkFont(size=26, weight="bold"),
        )
        title.pack(pady=(0, 30))

        cleanup_status = ctk.CTkLabel(
            splash_frame,
            text="Scanning firmware records...",
            font=ctk.CTkFont(size=14),
            justify="left",
        )
        cleanup_status.pack(fill="x", pady=(0, 20))
        widgets["cleanup_status"] = cleanup_status

        cleanup_progress = ctk.CTkProgressBar(splash_frame)
        cleanup_progress.pack(fill="x", pady=(0, 10))
        cleanup_progress.set(0)
        widgets["cleanup_progress"] = cleanup_progress

        cleanup_details = ctk.CTkLabel(
            splash_frame,
            text="",
            font=ctk.CTkFont(size=12),
            justify="left",
        )
        cleanup_details.pack(fill="x", pady=(0, 10))
        widgets["cleanup_details"] = cleanup_details

        return widgets
