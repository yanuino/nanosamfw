# SPDX-License-Identifier: MIT
# Copyright (c) 2025 nanosamfw contributors

"""Main GUI application for Samsung Firmware Downloader.

This module provides the main application window and device monitoring logic.
"""

import ctypes
import logging
import sys
import threading
import time
import tkinter as tk
import zipfile
from pathlib import Path
from typing import Optional

import customtkinter as ctk
import pyperclip

from device import DeviceNotFoundError, read_device_info_at
from device.errors import DeviceError
from download import check_and_prepare_firmware, cleanup_repository, download_and_decrypt, init_db
from download.config import PATHS
from fus.errors import FOTAError, InformError


class FirmwareDownloaderApp(ctk.CTk):
    """Main application window for Samsung Firmware Downloader.

    Monitors for connected Samsung devices and automatically downloads firmware
    when a device is detected and firmware is available.

    Attributes:
        monitoring: Flag indicating if device monitoring is active.
        download_in_progress: Flag indicating if download is in progress.
    """

    def __init__(self):
        """Initialize the application window."""
        super().__init__()

        # Initialize database
        init_db()

        # Setup logging
        self._setup_logging()

        # Window configuration
        self.title("Samsung Firmware Downloader")
        # Set application/window icon from AppIcons
        self._set_app_icon()
        self.geometry("1024x768")
        self.minsize(1024, 768)

        # Set appearance
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # State flags
        self.monitoring = False
        self.download_in_progress = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.startup_cleanup_done = False
        # Progress throttling state
        self._last_progress_time: float = 0.0
        self._last_progress_pct: dict[str, float] = {
            "download": 0.0,
            "decrypt": 0.0,
            "extract": 0.0,
        }
        # Per-stage timing/bytes state for throughput and end time
        self._stage_start_time: dict[str, float] = {}
        self._stage_last_done: dict[str, int] = {}

        # Run startup cleanup before building main UI
        self._run_startup_cleanup()

    def _run_startup_cleanup(self) -> None:
        """Perform repository cleanup with splash progress before showing UI.

        Creates a temporary frame with a progress bar and status label. The
        main application widgets are only created after cleanup completes.
        """
        # Splash frame (full window)
        self.splash_frame = ctk.CTkFrame(self)
        self.splash_frame.pack(fill="both", expand=True, padx=40, pady=40)

        title = ctk.CTkLabel(
            self.splash_frame,
            text="Initializing Repository",
            font=ctk.CTkFont(size=26, weight="bold"),
        )
        title.pack(pady=(0, 30))

        self.cleanup_status = ctk.CTkLabel(
            self.splash_frame,
            text="Scanning firmware records...",
            font=ctk.CTkFont(size=14),
            justify="left",
        )
        self.cleanup_status.pack(fill="x", pady=(0, 20))

        self.cleanup_progress = ctk.CTkProgressBar(self.splash_frame)
        self.cleanup_progress.pack(fill="x", pady=(0, 10))
        self.cleanup_progress.set(0)

        self.cleanup_details = ctk.CTkLabel(
            self.splash_frame,
            text="",
            font=ctk.CTkFont(size=12),
            justify="left",
        )
        self.cleanup_details.pack(fill="x", pady=(0, 10))

        # Run cleanup in background thread to keep UI responsive
        threading.Thread(target=self._perform_cleanup, daemon=True).start()

    def _set_app_icon(self) -> None:
        """Configure the window/taskbar icon from the AppIcons folder.

        Prefers `.ico` on Windows, otherwise falls back to a PNG.
        Keeps a reference to the image to prevent garbage collection.
        """
        try:
            icons_dir = Path(__file__).resolve().parent.parent / "AppIcons"
            if sys.platform.startswith("win"):
                # Help Windows taskbar use the same icon
                try:
                    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("nanosamfw.GUI")
                except (AttributeError, OSError):
                    pass

                ico_path = icons_dir / "app_icon.ico"
                if not ico_path.exists():
                    # pick any .ico if named differently
                    icos = list(icons_dir.glob("*.ico"))
                    if icos:
                        ico_path = icos[0]
                if ico_path.exists():
                    try:
                        self.iconbitmap(default=str(ico_path))
                        return
                    except (tk.TclError, OSError):
                        # Fallback to PNG if iconbitmap fails
                        pass

            # Non-Windows or fallback path: use a PNG
            # Prefer a medium/large size if available
            png_candidates = [
                icons_dir / "256.png",
                icons_dir / "128.png",
                icons_dir / "64.png",
                icons_dir / "32.png",
            ]
            png_path = next((p for p in png_candidates if p.exists()), None)
            if not png_path:
                # last resort: any PNG
                any_png = list(icons_dir.glob("*.png"))
                png_path = any_png[0] if any_png else None

            if png_path and png_path.exists():
                try:
                    img = tk.PhotoImage(file=str(png_path))
                    # True applies to both toplevel and taskbar where supported
                    self.iconphoto(True, img)
                    # Keep reference
                    self._icon_img = img  # type: ignore[attr-defined]
                except (tk.TclError, OSError):
                    pass
        except (tk.TclError, OSError, AttributeError):
            # Never block UI due to icon issues
            pass

    def _perform_cleanup(self) -> None:
        """Execute repository cleanup via download service and then build UI."""

        def progress_cb(processed: int, total: int, missing: int, deleted: int, dec_deleted: int):
            pct = processed / total if total else 1.0
            self.after(0, lambda v=pct: self.cleanup_progress.set(v))
            self.after(
                0,
                lambda: self.cleanup_details.configure(
                    text=(
                        f"Processed {processed}/{total} | Missing encrypted: {missing} | "
                        f"Records deleted: {deleted} | Decrypted deleted: {dec_deleted}"
                    )
                ),
            )

        # Start cleanup
        self.after(0, lambda: self.cleanup_status.configure(text="Cleaning repository..."))
        stats = cleanup_repository(progress_cb)
        summary = (
            f"Cleanup complete. Inspected: {stats['total_records']} | Missing: {stats['missing_encrypted']} | "
            f"Deleted: {stats['records_deleted']} | Decrypted removed: {stats['decrypted_deleted']}"
        )
        self.after(0, lambda: self.cleanup_status.configure(text=summary))
        self.after(0, lambda: self.cleanup_progress.set(1.0))
        time.sleep(0.5)
        self.after(0, self._finish_startup)

    def _finish_startup(self) -> None:
        """Destroy splash and build main application widgets."""
        if hasattr(self, "splash_frame"):
            self.splash_frame.destroy()
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
        # Main container with padding
        main_frame = ctk.CTkFrame(self)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # Title
        title_label = ctk.CTkLabel(
            main_frame,
            text="Samsung Firmware Downloader",
            font=ctk.CTkFont(size=24, weight="bold"),
        )
        title_label.pack(pady=(0, 20))

        # Status frame
        status_frame = ctk.CTkFrame(main_frame)
        status_frame.pack(fill="x", pady=10)

        ctk.CTkLabel(status_frame, text="Status:", font=ctk.CTkFont(size=14, weight="bold")).pack(
            anchor="w", padx=10, pady=(10, 5)
        )

        self.status_label = ctk.CTkLabel(
            status_frame,
            text="Stopped. Press 'Start Monitoring' to begin device detection",
            font=ctk.CTkFont(size=12),
        )
        self.status_label.pack(anchor="w", padx=10, pady=(0, 10))

        # Device info frame
        device_frame = ctk.CTkFrame(main_frame)
        device_frame.pack(fill="x", pady=10)

        ctk.CTkLabel(
            device_frame, text="Device Information:", font=ctk.CTkFont(size=14, weight="bold")
        ).pack(anchor="w", padx=10, pady=(10, 5))

        # Grid for entries
        entries_frame = ctk.CTkFrame(device_frame)
        entries_frame.pack(fill="x", padx=10, pady=(0, 10))

        def _make_row(row: int, label: str) -> ctk.CTkEntry:
            ctk.CTkLabel(entries_frame, text=label, font=ctk.CTkFont(size=12, weight="bold")).grid(
                row=row, column=0, sticky="w", pady=4
            )
            entry = ctk.CTkEntry(entries_frame, font=ctk.CTkFont(size=12))
            entry.grid(row=row, column=1, sticky="ew", padx=(10, 0), pady=4)
            entries_frame.grid_columnconfigure(1, weight=1)
            # Make read-only
            entry.configure(state="disabled")
            return entry

        self.model_entry = _make_row(0, "Model")
        self.firmware_entry = _make_row(1, "Firmware")
        self.region_entry = _make_row(2, "Region/CSC")
        self.imei_entry = _make_row(3, "IMEI")

        # Placeholders
        self._set_device_placeholders()

        # Progress frame
        progress_frame = ctk.CTkFrame(main_frame)
        progress_frame.pack(fill="x", pady=10)

        ctk.CTkLabel(
            progress_frame, text="Progress:", font=ctk.CTkFont(size=14, weight="bold")
        ).pack(anchor="w", padx=10, pady=(10, 5))

        # Unified progress bar (download + decrypt)
        self.download_progress_bar = ctk.CTkProgressBar(progress_frame)
        self.download_progress_bar.pack(fill="x", padx=10, pady=(0, 2))
        self.download_progress_bar.set(0)
        self.download_progress_bar.pack_forget()
        self.download_progress_label = ctk.CTkLabel(
            progress_frame, text="", font=ctk.CTkFont(size=11)
        )
        self.download_progress_label.pack(anchor="w", padx=10, pady=(0, 8))
        self.download_progress_label.pack_forget()

        # Message label for highlighted text (shown when not downloading)
        self.progress_message = ctk.CTkLabel(
            progress_frame,
            text="Waiting for device",
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=("#3B8ED0", "#1F6AA5"),  # Blue background
            corner_radius=8,
            height=40,
        )
        self.progress_message.pack(fill="x", padx=10, pady=(0, 10))

        # Firmware components frame
        components_frame = ctk.CTkFrame(main_frame)
        components_frame.pack(fill="x", pady=10)

        ctk.CTkLabel(
            components_frame, text="Firmware Components:", font=ctk.CTkFont(size=14, weight="bold")
        ).pack(anchor="w", padx=10, pady=(10, 5))

        # Grid for component entries
        comp_entries_frame = ctk.CTkFrame(components_frame)
        comp_entries_frame.pack(fill="x", padx=10, pady=(0, 10))

        def _make_comp_row(row: int, label: str) -> ctk.CTkEntry:
            label_widget = ctk.CTkLabel(
                comp_entries_frame,
                text=label,
                font=ctk.CTkFont(size=12, weight="bold"),
                cursor="hand2",
            )
            label_widget.grid(row=row, column=0, sticky="w", pady=4)
            entry = ctk.CTkEntry(comp_entries_frame, font=ctk.CTkFont(size=11))
            entry.grid(row=row, column=1, sticky="ew", padx=(10, 0), pady=4)
            comp_entries_frame.grid_columnconfigure(1, weight=1)
            entry.configure(state="disabled")
            original_fg = entry.cget("fg_color")

            # Make label clickable to copy entry value to clipboard
            def _copy_to_clipboard(e):
                value = entry.get()
                if value and value != "-":
                    try:
                        pyperclip.copy(value)
                        self._log("info", f"Copied {label} path to clipboard: {value}")
                        # Brief visual feedback
                        entry.configure(fg_color="#2CC985")
                        self.after(200, lambda: entry.configure(fg_color=original_fg))
                    except Exception as ex:
                        self._log("error", f"Failed to copy to clipboard: {ex}")

            label_widget.bind("<Button-1>", _copy_to_clipboard)
            entry.bind("<Button-1>", _copy_to_clipboard)
            return entry

        self.ap_entry = _make_comp_row(0, "AP")
        self.bl_entry = _make_comp_row(1, "BL")
        self.cp_entry = _make_comp_row(2, "CP")
        self.csc_entry = _make_comp_row(3, "CSC")
        self.home_entry = _make_comp_row(4, "HOME")

    def update_status(self, message: str):
        """Update status label with thread-safe scheduling.

        Args:
            message: Status message to display.
        """
        self.after(0, lambda: self.status_label.configure(text=message))

    def _set_device_placeholders(self) -> None:
        """Set placeholder text for device fields (no device detected)."""

        def _set(e: ctk.CTkEntry, text: str):
            e.configure(state="normal")
            e.delete(0, "end")
            e.insert(0, text)
            e.configure(state="disabled")

        _set(self.model_entry, "-")
        _set(self.firmware_entry, "-")
        _set(self.region_entry, "-")
        _set(self.imei_entry, "-")

    def update_device_fields(self, model: str, firmware: str, region: str, imei: str) -> None:
        """Update individual device info entries (read-only display).

        Args:
            model: Device model.
            firmware: Firmware version.
            region: Region/CSC code.
            imei: IMEI string.
        """

        def _set(e: ctk.CTkEntry, text: str):
            e.configure(state="normal")
            e.delete(0, "end")
            e.insert(0, text)
            e.configure(state="disabled")

        def _update():
            _set(self.model_entry, model or "-")
            _set(self.firmware_entry, firmware or "-")
            _set(self.region_entry, region or "-")
            _set(self.imei_entry, imei or "-")

        self.after(0, _update)

    def _clear_component_entries(self) -> None:
        """Clear all firmware component entries."""

        def _clear(e: ctk.CTkEntry):
            e.configure(state="normal")
            e.delete(0, "end")
            e.configure(state="disabled")

        _clear(self.ap_entry)
        _clear(self.bl_entry)
        _clear(self.cp_entry)
        _clear(self.csc_entry)
        _clear(self.home_entry)

    def _populate_component_entries(self, unzip_dir: Path) -> None:
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
                for prefix in components.keys():
                    if name.startswith(prefix):
                        components[prefix] = str(file_path.resolve())
                        break

        def _update():
            _set(self.ap_entry, components["AP"] or "-")
            _set(self.bl_entry, components["BL"] or "-")
            _set(self.cp_entry, components["CP"] or "-")
            _set(self.csc_entry, components["CSC"] or "-")
            _set(self.home_entry, components["HOME"] or "-")

        self.after(0, _update)

    def update_progress(self, stage: str, done: int, total: int):
        """Unified progress update for both download and decrypt stages.

        Args:
            stage: "download" or "decrypt".
            done: Bytes processed so far.
            total: Total bytes for stage.
        """
        # Throttle UI updates to avoid massive Tk event queue and slowdowns
        now = time.monotonic()
        last_time = getattr(self, "_last_progress_time", 0.0)
        last_pct = self._last_progress_pct.get(stage, 0.0)

        pct = done / total if total > 0 else 0.0
        pct_delta = pct - last_pct

        # Conditions to push an update:
        # - Completion
        # - Significant visual change (>= 1%)
        # - Or at least every 100ms
        should_update = done >= total or pct_delta >= 0.01 or (now - last_time) >= 0.1

        if not should_update:
            return

        # Record last update markers
        self._last_progress_time = now
        self._last_progress_pct[stage] = pct

        # Initialize/reset per-stage timers if needed (new stage or restart)
        last_done = self._stage_last_done.get(stage, -1)
        if stage not in self._stage_start_time or done < last_done:
            self._stage_start_time[stage] = now
            last_done = 0
        self._stage_last_done[stage] = done

        mb_done = done / (1024 * 1024)
        mb_total = total / (1024 * 1024)
        elapsed = max(0.0, now - self._stage_start_time.get(stage, now))
        speed_bps = (done / elapsed) if elapsed > 0.0 else 0.0
        speed_mbps = speed_bps / (1024 * 1024)

        # Compute ETA based on current average speed
        eta_secs = ((total - done) / speed_bps) if (speed_bps > 0 and total > 0) else None

        def _fmt_eta(sec: float | None) -> str:
            if sec is None:
                return "--:--"
            sec_i = int(sec)
            h, r = divmod(sec_i, 3600)
            m, s = divmod(r, 60)
            if h:
                return f"{h:d}:{m:02d}:{s:02d}"
            return f"{m:d}:{s:02d}"

        eta_str = _fmt_eta(eta_secs)

        # Format elapsed HH:MM:SS
        def _fmt_dur(sec: float) -> str:
            sec_i = int(sec)
            h, r = divmod(sec_i, 3600)
            m, s = divmod(r, 60)
            if h:
                return f"{h:d}:{m:02d}:{s:02d}"
            return f"{m:d}:{s:02d}"

        elapsed_str = _fmt_dur(elapsed)

        if stage == "extract":
            # Extract stage uses file count, not bytes
            prefix = "Extracting"
            label = f"{prefix}: {done} / {total} files • Elapsed {elapsed_str} • ETA {eta_str}"
        else:
            prefix = "Downloading" if stage == "download" else "Decrypting"
            if speed_mbps > 0:
                label = (
                    f"{prefix}: {mb_done:.1f} MB / {mb_total:.1f} MB • "
                    f"{speed_mbps:.1f} MB/s • Elapsed {elapsed_str} • ETA {eta_str}"
                )
            else:
                label = f"{prefix}: {mb_done:.1f} MB / {mb_total:.1f} MB • Elapsed {elapsed_str}"

        def _update():
            self.progress_message.pack_forget()
            if not self.download_progress_bar.winfo_ismapped():
                self.download_progress_bar.pack(fill="x", padx=10, pady=(0, 2))
                self.download_progress_label.pack(anchor="w", padx=10, pady=(0, 8))
            self.download_progress_bar.set(pct)
            self.download_progress_label.configure(text=label)

        self.after(0, _update)

    def update_progress_message(self, message: str, color: str = "info"):
        """Update progress message with color coding.

        Args:
            message: Message to display.
            color: Color type - "info" (blue), "success" (green), "warning" (orange), "error" (red).
        """
        colors = {
            "info": ("#3B8ED0", "#1F6AA5"),
            "success": ("#2CC985", "#2FA572"),
            "warning": ("#FF9500", "#E68600"),
            "error": ("#FF453A", "#E0342F"),
        }
        fg_color = colors.get(color, colors["info"])

        def _update():
            self.download_progress_bar.pack_forget()
            self.download_progress_label.pack_forget()
            self.progress_message.pack(fill="x", padx=10, pady=(0, 10))
            self.progress_message.configure(text=message, fg_color=fg_color)

        self.after(0, _update)

    def start_monitoring(self):
        """Start device monitoring in background thread (auto-start)."""
        if not self.monitoring:
            self.monitoring = True
            self.update_status("Monitoring for devices...")
            self.update_progress_message("Waiting for device", "info")
            self.monitor_thread = threading.Thread(target=self._monitor_devices, daemon=True)
            self.monitor_thread.start()

    # stop_monitoring removed (no longer user-invoked buttons). Kept minimal for future use.
    def stop_monitoring(self):  # pragma: no cover
        self.monitoring = False
        self.update_status("Monitoring stopped")
        self.update_progress_message("Monitoring stopped", "info")

    def _monitor_devices(self):
        """Background thread monitoring for device connections."""
        device_connected = False
        last_device_model = None

        while self.monitoring:
            try:
                # Try to detect device via AT commands
                device = read_device_info_at()

                # Device found
                if not device_connected:
                    # New device connection
                    device_connected = True
                    last_device_model = device.model
                    self._log("info", f"Device connected: {device.model}/{device.sales_code}")

                    # Device found - update UI
                    self.update_device_fields(
                        device.model,
                        device.firmware_version,
                        device.sales_code,
                        device.imei,
                    )
                    self.update_status("Device detected! Checking firmware...")

                    # Check for firmware via FOTA and repository cache
                    try:
                        self._log("info", f"Checking FOTA for {device.model}/{device.sales_code}")
                        latest, is_cached = check_and_prepare_firmware(
                            device.model, device.sales_code, device.imei, device.firmware_version
                        )
                        self._log("info", f"FOTA returned version: {latest} (cached: {is_cached})")

                        if latest == device.firmware_version:
                            msg = f"Firmware already latest version: {latest}"
                            self._log("info", msg)
                            self.update_status("Device connected")
                            self.update_progress_message(msg, "success")
                        elif is_cached:
                            # Firmware already downloaded, just decrypt and extract
                            msg = f"Firmware {latest} found in repository. Preparing..."
                            self._log("info", msg)
                            self.update_status("Device connected - Preparing cached firmware")
                            self.update_progress_message(msg, "info")

                            self.download_in_progress = True

                            def progress_cb(stage: str, done: int, total: int):
                                self.update_progress(stage, done, total)

                            try:
                                # Use cached firmware - will skip download
                                firmware, decrypted = download_and_decrypt(
                                    device.model,
                                    device.sales_code,
                                    device.imei,
                                    device.firmware_version,
                                    resume=True,
                                    progress_cb=progress_cb,
                                )

                                msg = f"Cached firmware ready! Version: {firmware.version_code}"
                                self._log("info", f"{msg} decrypted to {decrypted}")

                                # Extract firmware (same logic as download path)
                                try:
                                    decrypted_path = Path(decrypted)
                                    if decrypted_path.exists() and decrypted_path.suffix in [
                                        ".zip",
                                        ".ZIP",
                                    ]:
                                        self.update_status("Device connected - Extracting firmware")
                                        unzip_dir = decrypted_path.parent / decrypted_path.stem
                                        unzip_dir.mkdir(parents=True, exist_ok=True)

                                        with zipfile.ZipFile(decrypted_path, "r") as zip_ref:
                                            members = zip_ref.namelist()
                                            total_files = len(members)
                                            for idx, member in enumerate(members, 1):
                                                zip_ref.extract(member, unzip_dir)
                                                self.update_progress("extract", idx, total_files)

                                        self._log(
                                            "info", f"Extracted cached firmware to {unzip_dir}"
                                        )
                                        self._populate_component_entries(unzip_dir)
                                        msg = f"Firmware ready! Version: {firmware.version_code}"
                                except zipfile.BadZipFile:
                                    self._log("error", "Cached file is not a valid ZIP archive")
                                except Exception as ex:
                                    self._log("error", f"Extraction failed: {ex}")

                                self.update_status("Device connected")
                                self.update_progress_message(msg, "success")
                                self.download_in_progress = False

                            except InformError.BadStatus as ex:
                                status_msg = str(ex)
                                if "400" in status_msg:
                                    msg = "Please update via OTA (Over-The-Air)"
                                    self._log("warning", "FUS error 400: Firmware not available")
                                    color = "warning"
                                elif "408" in status_msg:
                                    msg = "Invalid model, CSC, or IMEI. Please check device information"
                                    self._log("error", f"FUS error 408: {msg}")
                                    color = "error"
                                else:
                                    msg = f"FUS server error: {ex}"
                                    self._log("error", msg)
                                    color = "error"

                                self.update_status("Device connected")
                                self.update_progress_message(msg, color)
                                self.download_in_progress = False
                        else:
                            # Download firmware via FUS
                            self.download_in_progress = True
                            self._log(
                                "info",
                                f"Downloading {latest} (current: {device.firmware_version})",
                            )
                            self.update_status("Device connected - Downloading firmware")

                            def progress_cb(stage: str, done: int, total: int):
                                self.update_progress(stage, done, total)

                            try:
                                # Reset unified bar
                                self.download_progress_bar.set(0)
                                firmware, decrypted = download_and_decrypt(
                                    device.model,
                                    device.sales_code,
                                    device.imei,
                                    device.firmware_version,
                                    resume=True,
                                    progress_cb=progress_cb,
                                )

                                msg = f"Download complete! Version: {firmware.version_code}"
                                self._log("info", f"{msg} saved to {decrypted}")

                                # Unzip firmware
                                try:
                                    decrypted_path = Path(decrypted)
                                    if decrypted_path.exists() and decrypted_path.suffix in [
                                        ".zip",
                                        ".ZIP",
                                    ]:
                                        self.update_status("Device connected - Extracting firmware")
                                        unzip_dir = decrypted_path.parent / decrypted_path.stem
                                        unzip_dir.mkdir(parents=True, exist_ok=True)

                                        with zipfile.ZipFile(decrypted_path, "r") as zip_ref:
                                            members = zip_ref.namelist()
                                            total_files = len(members)
                                            for idx, member in enumerate(members, 1):
                                                zip_ref.extract(member, unzip_dir)
                                                # Update progress: use file count as "bytes"
                                                self.update_progress("extract", idx, total_files)

                                        self._log("info", f"Extracted firmware to {unzip_dir}")
                                        self._populate_component_entries(unzip_dir)
                                        msg = (
                                            f"Firmware extracted! Version: {firmware.version_code}"
                                        )
                                except zipfile.BadZipFile:
                                    self._log("error", "Downloaded file is not a valid ZIP archive")
                                except Exception as ex:
                                    self._log("error", f"Extraction failed: {ex}")

                                self.update_status("Device connected")
                                self.update_progress_message(msg, "success")
                                self.download_in_progress = False

                            except InformError.BadStatus as ex:
                                # Check status code to determine error type
                                status_msg = str(ex)
                                if "400" in status_msg:
                                    msg = "Please update via OTA (Over-The-Air)"
                                    self._log("warning", "FUS error 400: Firmware not available")
                                    color = "warning"
                                elif "408" in status_msg:
                                    msg = "Invalid model, CSC, or IMEI. Please check device information"
                                    self._log("error", f"FUS error 408: {msg}")
                                    color = "error"
                                else:
                                    msg = f"FUS server error: {ex}"
                                    self._log("error", msg)
                                    color = "error"

                                self.update_status("Device connected")
                                self.update_progress_message(msg, color)
                                self.download_in_progress = False

                    except FOTAError.ModelOrRegionNotFound:
                        msg = "Model or CSC not recognized by FOTA"
                        self._log("warning", f"{msg}: {device.model}/{device.sales_code}")
                        self.update_status("Device connected")
                        self.update_progress_message(msg, "warning")
                    except FOTAError.NoFirmware:
                        msg = "No firmware available from FOTA"
                        self._log("warning", f"{msg} for {device.model}/{device.sales_code}")
                        self.update_status("Device connected")
                        self.update_progress_message(msg, "warning")
                    except FOTAError as ex:
                        # Generic FOTA communication error: keep it out of progress zone
                        msg = f"FOTA error: {ex}"
                        self._log("error", msg)
                        self.update_status("Device connected - Firmware check error")
                        # Revert progress area to waiting (no unmanaged error text shown)
                        self.update_progress_message("Waiting for device", "info")
                    except (OSError, IOError, ValueError, RuntimeError) as ex:
                        # Generic non-firmware error during check/download
                        msg = f"Error: {ex}"
                        self._log("error", msg)
                        self.update_status("Device connected - Firmware operation error")
                        self.update_progress_message("Waiting for device", "info")
                        self.download_in_progress = False

                    # Wait for device disconnect after processing
                    self.update_status("Waiting for device disconnect...")

                # Device still connected, wait for disconnect
                time.sleep(1)

            except DeviceNotFoundError:
                # Device disconnected or not present
                if device_connected:
                    # Device was connected, now disconnected
                    self._log("info", f"Device disconnected: {last_device_model}")
                    device_connected = False
                    last_device_model = None
                    self.update_status("Device disconnected. Waiting for new device...")
                    self._set_device_placeholders()
                    self._clear_component_entries()
                    self.update_progress_message("Waiting for device", "info")

                # Wait before checking again
                time.sleep(1)

            except DeviceError as ex:
                msg = f"Device error: {ex}"
                self._log("error", msg)
                # Reset connection state to allow fresh detection attempts
                device_connected = False
                last_device_model = None
                self.update_status("Device error detected - Retrying detection")
                self._set_device_placeholders()
                self._clear_component_entries()
                # Keep progress zone clean of communication errors
                self.update_progress_message("Waiting for device", "info")
                time.sleep(2)

            except (OSError, IOError, ValueError, RuntimeError) as ex:
                msg = f"Unexpected error: {ex}"
                self._log("error", msg)
                device_connected = False
                last_device_model = None
                self.update_status("Error occurred - Retrying detection")
                self._set_device_placeholders()
                self._clear_component_entries()
                self.update_progress_message("Waiting for device", "info")
                time.sleep(2)

    def run(self):
        """Start the application main loop."""
        self.mainloop()


def main():
    """Entry point for the GUI application."""
    app = FirmwareDownloaderApp()
    app.run()


if __name__ == "__main__":
    main()
