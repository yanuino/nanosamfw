# SPDX-License-Identifier: MIT
# Copyright (c) 2025 nanosamfw contributors

"""Device monitoring and firmware orchestration logic.

This module handles device detection, firmware checking, downloading,
decrypting, and extracting in a background thread.
"""

import logging
import time
from pathlib import Path
from typing import Callable

from device import DeviceNotFoundError, enter_odin_mode, read_device_info_at
from device.errors import DeviceATError, DeviceError
from download import check_and_prepare_firmware, download_and_decrypt, extract_firmware
from fus.errors import FOTAModelOrRegionNotFound, FOTANoFirmware, InformError


class DeviceMonitor:
    """Monitors for Samsung device connections and orchestrates firmware operations.

    Runs in a background thread, detecting devices via AT commands, checking
    for firmware updates, and coordinating download/decrypt/extract operations.

    CSC Filter Logic:
    - Empty filter (default) = accept all devices
    - Non-empty filter = only accept devices with CSC in the filter list

    Attributes:
        ui_updater: UIUpdater instance for thread-safe UI updates.
        progress_callback: Callback for progress updates.
        stop_check: Function that returns True if task should stop.
        disconnect_callback: Optional callback invoked when device disconnects.
        csc_filter: Set of allowed CSC codes (empty = accept all).
        ignore_home_csc: Whether to hide HOME_CSC files from the UI display.
        logger: Logger instance.
    """

    def __init__(
        self,
        ui_updater,
        progress_callback: Callable[[str, int, int], None],
        stop_check: Callable[[], bool],
        disconnect_callback: Callable[[], None] | None = None,
        csc_filter: list[str] | None = None,
        ignore_home_csc: bool = False,
        autofus_checkbox=None,
    ):
        """Initialize device monitor.

        Args:
            ui_updater: UIUpdater instance for UI updates.
            progress_callback: Function(stage, done, total) for progress updates.
            stop_check: Function returning True if task should be stopped.
            disconnect_callback: Optional callback invoked when device disconnects.
            csc_filter: Optional list of allowed CSC codes (case-insensitive).
                Empty list = accept all devices. Non-empty = only accept listed CSCs.
            ignore_home_csc: Whether to hide HOME_CSC files from UI display.
            autofus_checkbox: Optional reference to the Auto FUS Mode checkbox widget.
                If provided, its current state is checked at runtime for entering download mode.
        """
        self.ui_updater = ui_updater
        self.progress_callback = progress_callback
        self.stop_check = stop_check
        self.disconnect_callback = disconnect_callback
        self.csc_filter: set[str] = {c.strip().upper() for c in csc_filter} if csc_filter else set()
        self.ignore_home_csc = ignore_home_csc
        self.autofus_checkbox = autofus_checkbox
        self.logger = logging.getLogger(__name__)
        self.monitoring = False
        self.download_in_progress = False

    def start(self) -> None:
        """Start device monitoring loop (call from background thread)."""
        self.monitoring = True
        self._monitor_loop()

    def stop(self) -> None:
        """Stop device monitoring."""
        self.monitoring = False

    def _monitor_loop(self) -> None:
        """Main device monitoring loop."""
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
                    self.logger.info("Device connected: %s", device.model)
                    self.logger.info("CSC: %s, AID: %s, CC: %s", device.sales_code, device.aid, device.cc)
                    self.logger.info(
                        "IMEI: %s, SN: %s, LOCK: %s",
                        device.imei,
                        device.serial_number,
                        device.lock_status,
                    )
                    self.logger.info("Firmware: %s", device.firmware_version)

                    # Clear old component paths from previous device
                    self.ui_updater.clear_component_entries()

                    # Update device fields first (before any filtering check)
                    self.ui_updater.update_device_fields(
                        device.model,
                        device.firmware_version,
                        device.sales_code,
                        device.imei,
                        aid=device.aid or "-",
                        cc=device.cc or "-",
                    )

                    # Check CSC filter (empty = allow all, non-empty = only allow listed CSCs)
                    device_csc = (device.sales_code or "").strip().upper()
                    if self.csc_filter and device_csc and device_csc not in self.csc_filter:
                        self.logger.info("Device rejected by CSC filter: %s (%s)", device.model, device_csc)
                        self.ui_updater.update_status("Device filtered by CSC")
                        self.ui_updater.update_progress_message("CSC Filtered", "warning")
                        # Skip processing for this device, wait for disconnect
                        time.sleep(1)
                        continue

                    self.ui_updater.update_status("Device detected! Checking firmware...")

                    # Check for firmware and handle download/decrypt/extract
                    self._handle_firmware_check(device)

                    # Wait for device disconnect after processing
                    self.ui_updater.update_status("Waiting for device disconnect...")

                # Device still connected, wait for disconnect
                time.sleep(1)

            except DeviceNotFoundError:
                # Device disconnected or not present
                if device_connected:
                    # Device was connected, now disconnected
                    self.logger.info("Device disconnected: %s", last_device_model)
                    device_connected = False
                    last_device_model = None
                    self.ui_updater.update_status("Device disconnected. Waiting for new device...")
                    self.ui_updater.set_device_placeholders()
                    # Keep component paths visible until new device connects
                    self.ui_updater.update_progress_message("Waiting for device", "info")

                    # Reset stop flag for next device
                    if self.disconnect_callback:
                        self.disconnect_callback()

                # Wait before checking again
                time.sleep(1)

            except DeviceError as ex:
                msg = f"Device error: {ex}"
                self.logger.error(msg)
                # Reset connection state to allow fresh detection attempts
                device_connected = False
                last_device_model = None
                self.ui_updater.update_status("Device error detected - Retrying detection")
                self.ui_updater.set_device_placeholders()
                # Keep component paths visible until new device connects
                # Keep progress zone clean of communication errors
                self.ui_updater.update_progress_message("Waiting for device", "info")
                time.sleep(2)

            except (OSError, IOError, ValueError, RuntimeError) as ex:
                msg = f"Unexpected error: {ex}"
                self.logger.error(msg)
                device_connected = False
                last_device_model = None
                self.ui_updater.update_status("Error occurred - Retrying detection")
                self.ui_updater.set_device_placeholders()
                # Keep component paths visible until new device connects
                self.ui_updater.update_progress_message("Waiting for device", "info")
                time.sleep(2)

    def _handle_firmware_check(self, device) -> None:
        """Check for firmware updates and handle download/decrypt/extract.

        Args:
            device: ATDeviceInfo instance with device information.
        """
        try:
            self.logger.info("Checking FOTA for %s/%s", device.model, device.sales_code)
            latest, is_cached = check_and_prepare_firmware(
                device.model,
                device.sales_code,
                device.imei,
                device.firmware_version,
                serial_number=device.serial_number,
                lock_status=device.lock_status,
                aid=device.aid,
                cc=device.cc,
            )
            self.logger.info("FOTA returned version: %s (cached: %s)", latest, is_cached)

            if latest == device.firmware_version:
                msg = f"Firmware already latest version: {latest}"
                self.logger.info(msg)
                self.ui_updater.update_status("Device connected")
                self.ui_updater.update_progress_message(msg, "success")

            elif is_cached:
                # Firmware already downloaded, just decrypt and extract
                self._handle_cached_firmware(device, latest)

            else:
                # Download firmware via FUS
                self._handle_firmware_download(device, latest)

        except FOTAModelOrRegionNotFound:
            msg = "Model or CSC not recognized by FOTA"
            self.logger.warning("%s: %s/%s", msg, device.model, device.sales_code)
            self.ui_updater.update_status("Device connected")
            self.ui_updater.update_progress_message(msg, "warning")

        except FOTANoFirmware:
            msg = "No firmware available from FOTA"
            self.logger.warning("%s for %s/%s", msg, device.model, device.sales_code)
            self.ui_updater.update_status("Device connected")
            self.ui_updater.update_progress_message(msg, "warning")

        except (OSError, IOError, ValueError, RuntimeError) as ex:
            # Generic non-firmware error during check/download
            msg = f"Error: {ex}"
            self.logger.error(msg)
            self.ui_updater.update_status("Device connected - Firmware operation error")
            self.ui_updater.update_progress_message("Waiting for device", "info")
            self.download_in_progress = False
            self.ui_updater.update_stop_button_state(self.download_in_progress, self.stop_check())

    def _handle_cached_firmware(self, device, latest: str) -> None:
        """Handle cached firmware preparation (decrypt and extract).

        Args:
            device: ATDeviceInfo instance.
            latest: Latest firmware version string.
        """
        msg = f"Firmware {latest} found in repository. Preparing..."
        self.logger.info(msg)
        self.ui_updater.update_status("Device connected - Preparing cached firmware")
        self.ui_updater.update_progress_message(msg, "info")

        self.download_in_progress = True
        self.ui_updater.update_stop_button_state(self.download_in_progress, False)

        try:
            # Use cached firmware - will skip download
            firmware, decrypted = download_and_decrypt(
                device.model,
                device.sales_code,
                device.imei,
                device.firmware_version,
                version=latest,  # Pass version to avoid duplicate FOTA query
                resume=True,
                progress_cb=self.progress_callback,
                stop_check=self.stop_check,
                serial_number=device.serial_number,
                lock_status=device.lock_status,
                aid=device.aid,
                cc=device.cc,
            )

            msg = f"Cached firmware ready! Version: {firmware.version_code}"
            self.logger.info("%s decrypted to %s", msg, decrypted)

            # Extract firmware
            self._extract_firmware(Path(decrypted), firmware.version_code)

            self.ui_updater.update_status("Device connected")
            self.ui_updater.update_progress_message(msg, "success")
            self.download_in_progress = False
            self.ui_updater.update_stop_button_state(self.download_in_progress, False)

        except RuntimeError as ex:
            self._handle_runtime_error(ex)

        except InformError.BadStatus as ex:
            self._handle_fus_error(ex)

    def _handle_firmware_download(self, device, latest: str) -> None:
        """Handle firmware download, decrypt, and extract.

        Args:
            device: ATDeviceInfo instance.
            latest: Latest firmware version string.
        """
        self.download_in_progress = True
        self.ui_updater.update_stop_button_state(self.download_in_progress, False)
        self.logger.info("Downloading %s (current: %s)", latest, device.firmware_version)
        self.ui_updater.update_status("Device connected - Downloading firmware")

        try:
            firmware, decrypted = download_and_decrypt(
                device.model,
                device.sales_code,
                device.imei,
                device.firmware_version,
                version=latest,  # Pass version to avoid duplicate FOTA query
                resume=True,
                progress_cb=self.progress_callback,
                stop_check=self.stop_check,
                serial_number=device.serial_number,
                lock_status=device.lock_status,
                aid=device.aid,
                cc=device.cc,
            )

            msg = f"Download complete! Version: {firmware.version_code}"
            self.logger.info("%s saved to %s", msg, decrypted)

            # Extract firmware
            self._extract_firmware(Path(decrypted), firmware.version_code)

            self.ui_updater.update_status("Device connected")
            self.ui_updater.update_progress_message(msg, "success")
            self.download_in_progress = False
            self.ui_updater.update_stop_button_state(self.download_in_progress, False)

        except RuntimeError as ex:
            self._handle_runtime_error(ex)

        except InformError.BadStatus as ex:
            self._handle_fus_error(ex)

    def _extract_firmware(self, decrypted_path: Path, version: str) -> None:
        """Extract firmware ZIP file, compute checksums, and clean up files.

        Uses the download service to extract the firmware file, compute MD5
        checksums for components, and automatically clean up encrypted and
        decrypted files after successful extraction.
        If Auto FUS Mode checkbox is checked, enters download mode after extraction.

        Args:
            decrypted_path: Path to decrypted firmware file.
            version: Firmware version string (version_code).
        """
        try:
            if decrypted_path.exists() and decrypted_path.suffix.lower() in [".zip"]:
                self.ui_updater.update_status("Device connected - Extracting firmware")

                unzip_dir = extract_firmware(
                    decrypted_path,
                    version_code=version,
                    cleanup_after=True,  # Clean up encrypted and decrypted files
                    progress_cb=self.progress_callback,
                    stop_check=self.stop_check,
                )

                self.logger.info("Extracted firmware to %s", unzip_dir)
                self.ui_updater.populate_component_entries(unzip_dir, ignore_home_csc=self.ignore_home_csc)

                # Check if Auto FUS Mode checkbox is currently checked
                if self.autofus_checkbox and self.autofus_checkbox.get():
                    self._enter_download_mode_auto()

        except ValueError as ex:
            self.logger.error("Extraction error: %s", ex)
        except (OSError, IOError, RuntimeError) as ex:
            if "stopped" in str(ex).lower():
                self.logger.info("Extraction task stopped: %s", ex)
            else:
                self.logger.error("Extraction failed: %s", ex)

    def _handle_runtime_error(self, ex: RuntimeError) -> None:
        """Handle runtime errors (typically user-stopped tasks).

        Args:
            ex: RuntimeError exception.
        """
        if "stopped" in str(ex).lower():
            self.logger.info("Task stopped: %s", ex)
            self.ui_updater.update_status("Device connected")
            self.ui_updater.update_progress_message("Task stopped", "warning")
        else:
            self.logger.error("Runtime error: %s", ex)
            self.ui_updater.update_status("Device connected - Error")
            self.ui_updater.update_progress_message("Waiting for device", "info")

        self.download_in_progress = False
        self.ui_updater.update_stop_button_state(self.download_in_progress, False)

    def _handle_fus_error(self, ex: InformError.BadStatus) -> None:
        """Handle FUS server errors.

        Args:
            ex: InformError.BadStatus exception.
        """
        status_msg = str(ex)
        if "400" in status_msg:
            msg = "Please update via OTA (Over-The-Air)"
            self.logger.warning("FUS error 400: Firmware not available")
            color = "warning"
        elif "408" in status_msg:
            msg = "Invalid model, CSC, or IMEI. Please check device information"
            self.logger.error("FUS error 408: %s", msg)
            color = "error"
        else:
            msg = f"FUS server error: {ex}"
            self.logger.error(msg)
            color = "error"

        self.ui_updater.update_status("Device connected")
        self.ui_updater.update_progress_message(msg, color)
        self.download_in_progress = False
        self.ui_updater.update_stop_button_state(self.download_in_progress, False)

    def _enter_download_mode_auto(self) -> None:
        """Automatically enter download mode after firmware extraction.

        Sends AT+FUS? command and waits for device to appear in Odin mode.
        Updates UI with progress messages during the transition.
        """
        try:
            self.ui_updater.update_status("Device connected - Entering download mode")
            self.ui_updater.update_progress_message("Sending download mode command...", "info")

            def progress_cb(msg: str):
                self.logger.info("Auto FUS Mode: %s", msg)
                self.ui_updater.update_progress_message(msg, "info")

            # Attempt to enter Odin mode (auto-detects device)
            success = enter_odin_mode(wait_timeout=30.0, progress_callback=progress_cb)

            if success:
                msg = "Device successfully entered download mode! Ready for flashing"
                self.logger.info(msg)
                self.ui_updater.update_status("Device in download mode")
                self.ui_updater.update_progress_message(msg, "success")
            else:
                msg = "Timeout waiting for download mode. Device may not support AT+FUS? command"
                self.logger.warning(msg)
                self.ui_updater.update_status("Device connected")
                self.ui_updater.update_progress_message(msg, "warning")

        except DeviceATError as ex:
            msg = f"Error entering download mode: {ex}"
            self.logger.error(msg)
            self.ui_updater.update_status("Device connected - Download mode error")
            self.ui_updater.update_progress_message(msg, "error")

        except (OSError, IOError, ValueError, RuntimeError) as ex:
            msg = f"Unexpected error during download mode transition: {ex}"
            self.logger.error(msg)
            self.ui_updater.update_status("Device connected - Error")
            self.ui_updater.update_progress_message("Waiting for device", "info")
