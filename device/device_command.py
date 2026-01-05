"""Device commands for advanced operations like entering download mode.

This module provides high-level command functions that coordinate multiple
low-level device operations, such as rebooting into download mode.

Copyright (c) 2024 nanosamfw contributors
SPDX-License-Identifier: MIT
"""

import time
from typing import Callable, Optional

from device.at_client import enter_download_mode
from device.detector import get_first_device
from device.errors import DeviceATError, DeviceOdinError
from device.odin_client import is_odin_mode


def enter_odin_mode(
    port_name: Optional[str] = None,
    *,
    wait_timeout: float = 10.0,
    check_interval: float = 0.5,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> bool:
    """Enter Odin (download) mode and wait for device to be ready.

    Sends AT+FUS? command to device to reboot into download mode, then polls
    for the device to appear in Odin mode. Provides progress updates via callback.

    Args:
        port_name: Serial port name (e.g., "COM3" on Windows, "/dev/ttyACM0" on Linux).
            If None, auto-detects the first Samsung device port.
        wait_timeout: Maximum time to wait for device to enter Odin mode (seconds)
        check_interval: Time between Odin mode checks (seconds)
        progress_callback: Optional callback for progress messages

    Returns:
        True if device successfully entered Odin mode, False if timeout

    Raises:
        DeviceATError: If sending AT+FUS? command fails
        DeviceOdinError: If checking Odin mode fails (communication error, not timeout)
        DeviceNotFoundError: If auto-detection fails

    Example:
        >>> from device import enter_odin_mode
        >>> if enter_odin_mode():
        ...     print("Device ready in download mode")
        ... else:
        ...     print("Timeout waiting for download mode")
    """

    def _log(msg: str):
        if progress_callback:
            progress_callback(msg)

    # Auto-detect if port not provided
    target_port = port_name
    if target_port is None:
        device = get_first_device()
        target_port = device.port_name

    # Step 1: Send AT+FUS? command to reboot into download mode
    _log("Sending AT+FUS? command to enter download mode...")
    try:
        enter_download_mode(target_port, timeout=1.0)
    except DeviceATError as ex:
        _log(f"Error sending AT+FUS? command: {ex}")
        raise

    # Step 2: Wait for device to reboot and appear in Odin mode
    time.sleep(10.0)  # Initial wait before checking

    _log("Waiting for device to reboot...")
    start_time = time.monotonic()
    deadline = start_time + wait_timeout

    while time.monotonic() < deadline:
        try:
            time.sleep(check_interval)
            if is_odin_mode(target_port, timeout=2.0):
                elapsed = time.monotonic() - start_time
                _log(f"Device entered Odin mode ({elapsed:.1f}s)")
                return True
        except DeviceOdinError:
            # Communication error - device might still be rebooting
            # Continue checking until timeout
            pass

        time.sleep(check_interval)

    # Timeout reached
    elapsed = time.monotonic() - start_time
    _log(f"Timeout waiting for Odin mode after {elapsed:.1f}s")
    return False
