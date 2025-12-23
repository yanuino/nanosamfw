# SPDX-License-Identifier: MIT
# Copyright (c) 2025 nanosamfw contributors

"""Progress tracking and calculation for firmware operations.

This module handles progress state management, throttling, ETA calculations,
and throughput monitoring for download, decrypt, and extract operations.
"""

import time
from typing import Callable


class ProgressTracker:
    """Tracks progress for multi-stage firmware operations.

    Manages progress state, throttles UI updates, and calculates ETAs and
    throughput for download, decrypt, and extract stages.

    Attributes:
        update_callback: Callback function(stage, done, total, label) for UI updates.
    """

    def __init__(self, update_callback: Callable[[str, int, int, str], None]):
        """Initialize progress tracker.

        Args:
            update_callback: Function to call with progress updates.
                Signature: (stage: str, done: int, total: int, label: str) -> None
        """
        self.update_callback = update_callback
        self._last_progress_time: float = 0.0
        self._last_progress_pct: dict[str, float] = {
            "download": 0.0,
            "decrypt": 0.0,
            "extract": 0.0,
        }
        self._stage_start_time: dict[str, float] = {}
        self._stage_last_done: dict[str, int] = {}

    def update_progress(self, stage: str, done: int, total: int) -> None:
        """Update progress for a specific stage.

        Throttles updates to avoid overwhelming the UI. Updates are pushed when:
        - Task completes (done >= total)
        - Progress changes by >= 1%
        - At least 100ms has elapsed since last update

        Args:
            stage: Stage name ("download", "decrypt", or "extract").
            done: Bytes or files processed so far.
            total: Total bytes or files for stage.
        """
        # Throttle UI updates to avoid massive Tk event queue and slowdowns
        now = time.monotonic()
        last_time = self._last_progress_time
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
        self._stage_last_done[stage] = done

        mb_done = done / (1024 * 1024)
        mb_total = total / (1024 * 1024)
        elapsed = max(0.0, now - self._stage_start_time.get(stage, now))
        speed_bps = (done / elapsed) if elapsed > 0.0 else 0.0
        speed_mbps = speed_bps / (1024 * 1024)

        # Compute ETA based on current average speed
        eta_secs = ((total - done) / speed_bps) if (speed_bps > 0 and total > 0) else None
        eta_str = self._format_eta(eta_secs)
        elapsed_str = self._format_duration(elapsed)

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

        # Call the UI update callback
        self.update_callback(stage, done, total, label)

    def reset(self) -> None:
        """Reset all progress state for new operation."""
        self._last_progress_time = 0.0
        self._last_progress_pct = {
            "download": 0.0,
            "decrypt": 0.0,
            "extract": 0.0,
        }
        self._stage_start_time.clear()
        self._stage_last_done.clear()

    @staticmethod
    def _format_eta(sec: float | None) -> str:
        """Format ETA seconds as HH:MM:SS or MM:SS.

        Args:
            sec: Seconds remaining, or None if unknown.

        Returns:
            Formatted ETA string or "--:--" if unknown.
        """
        if sec is None:
            return "--:--"
        sec_i = int(sec)
        h, r = divmod(sec_i, 3600)
        m, s = divmod(r, 60)
        if h:
            return f"{h:d}:{m:02d}:{s:02d}"
        return f"{m:d}:{s:02d}"

    @staticmethod
    def _format_duration(sec: float) -> str:
        """Format elapsed seconds as HH:MM:SS or MM:SS.

        Args:
            sec: Elapsed seconds.

        Returns:
            Formatted duration string.
        """
        sec_i = int(sec)
        h, r = divmod(sec_i, 3600)
        m, s = divmod(r, 60)
        if h:
            return f"{h:d}:{m:02d}:{s:02d}"
        return f"{m:d}:{s:02d}"
