# SPDX-License-Identifier: MIT
# Copyright (c) 2025 nanosamfw contributors

"""Main GUI application for Samsung Firmware Downloader.

This module provides the main application window, coordinating UI components,
device monitoring, and firmware operations.
"""

import ctypes
import logging
import sys
import tempfile
import threading
import time
import tkinter as tk
from importlib.resources import files
from typing import Optional

import customtkinter as ctk

from app.config import load_config
from app.device_monitor import DeviceMonitor
from app.progress_tracker import ProgressTracker
from app.ui_builder import UIBuilder
from app.ui_updater import UIUpdater
from download import cleanup_repository, init_db
from download.config import PATHS
from download.service import get_session_id


class FirmwareDownloaderApp(ctk.CTk):
    """Main application window for Samsung Firmware Downloader.

    Monitors for connected Samsung devices and automatically downloads firmware
    when a device is detected and firmware is available.

    Attributes:
        monitoring: Flag indicating if device monitoring is active.
        download_in_progress: Flag indicating if download is in progress.
        stop_task: Flag to stop active download/decrypt/extract.
    """

    def __init__(self):
        """Initialize the application window."""
        super().__init__()

        # Initialize database
        init_db()

        # Setup logging
        self._setup_logging()

        # Log session ID from service
        self.logger.info("Session ID: %s", get_session_id())

        # Load configuration
        self.config = load_config()

        # Window configuration
        self.title("Samsung Firmware Downloader")
        self._set_app_icon()
        self.geometry("1024x")
        self.minsize(1024, 0)

        # Set appearance
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # State flags
        self.monitoring = False
        self.download_in_progress = False
        self.stop_task = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.startup_cleanup_done = False

        # Initialize UI builder
        self.ui_builder = UIBuilder(self, self.config)

        # Run startup cleanup before building main UI
        self._run_startup_cleanup()

    def _run_startup_cleanup(self) -> None:
        """Perform repository cleanup with splash progress before showing UI.

        Creates a temporary frame with a progress bar and status label. The
        main application widgets are only created after cleanup completes.
        """
        # Create splash widgets
        splash_widgets = self.ui_builder.create_splash_widgets()
        self.splash_widgets = splash_widgets

        # Run cleanup in background thread to keep UI responsive
        threading.Thread(target=self._perform_cleanup, daemon=True).start()

    def _set_app_icon(self) -> None:
        """Configure the window/taskbar icon using importlib.resources.

        Prefers `.ico` on Windows, otherwise falls back to a PNG.
        Uses importlib.resources for reliable packaging.
        """
        try:
            icons = files('AppIcons') if files('AppIcons').is_dir() else None
            if not icons:
                return

            if sys.platform.startswith("win"):
                # Help Windows taskbar use the same icon
                try:
                    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("nanosamfw.GUI")
                except (AttributeError, OSError):
                    # Ignore failure to set AppUserModelID; not critical for UI operation
                    pass

                # Try app_icon.ico or any .ico
                ico_candidates = ['app_icon.ico'] + [f.name for f in icons.iterdir() if f.name.endswith('.ico')]
                for ico_name in ico_candidates:
                    try:
                        ico_data = (icons / ico_name).read_bytes()
                        # iconbitmap needs a file path, write to temp
                        with tempfile.NamedTemporaryFile(suffix='.ico', delete=False) as tmp:
                            tmp.write(ico_data)
                            tmp_path = tmp.name
                        self.iconbitmap(default=tmp_path)
                        # Keep temp file reference for cleanup
                        self._icon_tmp = tmp_path  # type: ignore[attr-defined]
                        return
                    except (KeyError, FileNotFoundError, tk.TclError, OSError):
                        continue

            # Non-Windows or fallback: use PNG
            png_candidates = ['256.png', '128.png', '64.png', '32.png']
            for png_name in png_candidates:
                try:
                    png_data = (icons / png_name).read_bytes()
                    img = tk.PhotoImage(data=png_data)
                    self.iconphoto(True, img)
                    self._icon_img = img  # type: ignore[attr-defined]
                    return
                except (KeyError, FileNotFoundError, tk.TclError, OSError):
                    continue

        except (ImportError, tk.TclError, OSError, AttributeError):
            # Never block UI due to icon issues
            pass

    def _perform_cleanup(self) -> None:
        """Execute repository cleanup via download service and then build UI."""

        def progress_cb(processed: int, total: int, missing: int, deleted: int, dec_deleted: int):
            pct = processed / total if total else 1.0
            self.after(0, lambda v=pct: self.splash_widgets["cleanup_progress"].set(v))
            self.after(
                0,
                lambda: self.splash_widgets["cleanup_details"].configure(
                    text=(
                        f"Processed {processed}/{total} | Missing encrypted: {missing} | "
                        f"Records deleted: {deleted} | Decrypted deleted: {dec_deleted}"
                    )
                ),
            )

        # Start cleanup
        self.after(0, lambda: self.splash_widgets["cleanup_status"].configure(text="Cleaning repository..."))
        stats = cleanup_repository(progress_cb)
        summary = (
            f"Cleanup complete. Inspected: {stats['total_records']} | Missing: {stats['missing_encrypted']} | "
            f"Deleted: {stats['records_deleted']} | Decrypted removed: {stats['decrypted_deleted']}"
        )
        self.after(0, lambda: self.splash_widgets["cleanup_status"].configure(text=summary))
        self.after(0, lambda: self.splash_widgets["cleanup_progress"].set(1.0))
        time.sleep(0.5)
        self.after(0, self._finish_startup)

    def _finish_startup(self) -> None:
        """Destroy splash and build main application widgets."""
        if "splash_frame" in self.splash_widgets:
            self.splash_widgets["splash_frame"].destroy()
        self._create_widgets()
        self.startup_cleanup_done = True
        # Auto-start monitoring after UI is ready
        self.start_monitoring()

    def _setup_logging(self):
        """Setup logging to file in data directory."""
        log_dir = PATHS.data_dir
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "app.log"

        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler(log_file, mode="a", encoding="utf-8"),
            ],
        )
        self.logger = logging.getLogger(__name__)
        self.logger.info("=" * 60)
        self.logger.info("Application started")

    def _log(self, level: str, message: str):
        """Log message with timestamp.

        Args:
            level: Log level (info, warning, error).
            message: Message to log.
        """
        log_func = getattr(self.logger, level, self.logger.info)
        log_func(message)

    def _create_widgets(self):
        """Create and layout all UI widgets."""
        # pylint: disable=W0201  # Widgets initialized here after splash screen
        # Create main widgets using UI builder
        self.widgets = self.ui_builder.create_main_widgets(stop_callback=self.stop_current_task)

        # Initialize UI updater with widget references
        self.ui_updater = UIUpdater(self, self.widgets)

        # Initialize progress tracker
        def progress_ui_callback(stage: str, done: int, total: int, label: str):
            self.ui_updater.update_progress_bar(stage, done, total, label)

        self.progress_tracker = ProgressTracker(progress_ui_callback)

        # Initialize device monitor
        def progress_callback(stage: str, done: int, total: int):
            self.progress_tracker.update_progress(stage, done, total)

        def stop_check() -> bool:
            return self.stop_task

        csc_filter_list = self._parse_csc_filter()
        self.device_monitor = DeviceMonitor(
            self.ui_updater,
            progress_callback,
            stop_check,
            csc_filter=csc_filter_list,
            unzip_home_csc=self.config.unzip_home_csc,
        )

        # Set initial placeholders
        self.ui_updater.set_device_placeholders()

    def start_monitoring(self):
        """Start device monitoring in background thread (auto-start)."""
        if not self.monitoring:
            self.monitoring = True
            self.ui_updater.update_status("Monitoring for devices...")
            self.ui_updater.update_progress_message("Waiting for device", "info")
            self.monitor_thread = threading.Thread(target=self._run_monitor, daemon=True)
            self.monitor_thread.start()

    def _parse_csc_filter(self) -> list[str]:
        """Parse CSC filter config into a list of uppercase codes.

        Empty string = allow all devices
        Comma-separated values = only allow those CSC codes

        Returns:
            List of uppercase CSC codes to allow, or empty list to allow all.
        """
        if not getattr(self.config, "csc_filter", ""):
            return []
        return [c.strip().upper() for c in self.config.csc_filter.split(",") if c.strip()]

    def _run_monitor(self):
        """Run device monitor in background thread."""
        self.device_monitor.start()

    def stop_monitoring(self):  # pragma: no cover
        """Stop device monitoring."""
        self.monitoring = False
        self.device_monitor.stop()
        self.ui_updater.update_status("Monitoring stopped")
        self.ui_updater.update_progress_message("Monitoring stopped", "info")

    def stop_current_task(self):
        """Stop any active download, decrypt, or extract task.

        Device monitoring remains active. The stop flag is checked in download loops.
        """
        if self.device_monitor.download_in_progress:
            self._log("info", "User requested task stop")
            self.stop_task = True
            self.ui_updater.update_status("Stopping task...")

    def run(self):
        """Start the application main loop."""
        self.mainloop()


def main():
    """Entry point for the GUI application."""
    app = FirmwareDownloaderApp()
    app.run()


if __name__ == "__main__":
    main()
