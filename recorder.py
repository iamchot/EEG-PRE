from __future__ import annotations

import csv
import time
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional


class EEGRecorder:
    def __init__(self, channels: Iterable[str]) -> None:
        self.channels = list(channels)
        self._file = None
        self._writer: Optional[csv.writer] = None
        self.path: Optional[Path] = None
        self._last_flush = 0.0
        self._flush_interval = 0.5

    @property
    def is_recording(self) -> bool:
        return self._writer is not None

    def start(self, directory: str | Path = "recordings") -> Path:
        if self.is_recording:
            return self.path  # type: ignore[return-value]

        target_dir = Path(directory)
        target_dir.mkdir(parents=True, exist_ok=True)
        filename = datetime.now().strftime("muse_eeg_%Y%m%d_%H%M%S.csv")
        self.path = target_dir / filename
        self._file = self.path.open("w", newline="", encoding="utf-8")
        self._writer = csv.writer(self._file)
        self._writer.writerow(["timestamp_lsl", "timestamp_iso", *self.channels])
        self._file.flush()
        self._last_flush = time.monotonic()
        return self.path

    def write_samples(self, timestamps: Iterable[float], samples: Iterable[Iterable[float]]) -> None:
        if not self._writer or not self._file:
            return

        rows = []
        for timestamp, sample in zip(timestamps, samples):
            # LSL timestamps are clock-synchronized stream times, not Unix epoch values.
            iso_time = datetime.now().isoformat(timespec="milliseconds")
            rows.append([f"{float(timestamp):.6f}", iso_time, *sample])

        if rows:
            self._writer.writerows(rows)

        now = time.monotonic()
        if now - self._last_flush >= self._flush_interval:
            self._file.flush()
            self._last_flush = now

    def stop(self) -> Optional[Path]:
        path = self.path
        if self._file:
            self._file.flush()
            self._file.close()
        self._file = None
        self._writer = None
        return path
