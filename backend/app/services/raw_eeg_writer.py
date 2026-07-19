from __future__ import annotations

import csv
import hashlib
import math
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence, TextIO


CSV_HEADER = (
    "timestamp",
    "tp9",
    "af7",
    "af8",
    "tp10",
    "tp9_quality",
    "af7_quality",
    "af8_quality",
    "tp10_quality",
    "marker",
)

_PARTICIPANT_CODE = re.compile(r"P[0-9]+\Z")
_SAFE_COMPONENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*\Z")


@dataclass(frozen=True, slots=True)
class EEGSample:
    timestamp: float
    tp9: float
    af7: float
    af8: float
    tp10: float
    tp9_quality: float
    af7_quality: float
    af8_quality: float
    tp10_quality: float
    marker: str = ""


@dataclass(frozen=True, slots=True)
class RawFileResult:
    relative_path: str
    sha256: str
    byte_size: int
    row_count: int
    first_timestamp: float | None
    last_timestamp: float | None


class AtomicEEGWriter:
    """Write one pseudonymous EEG capture without exposing partial files as final."""

    def __init__(self, collection_raw_dir: str | Path, *, clock: Callable[[], float] = time.time):
        self._root = Path(collection_raw_dir).resolve()
        self._clock = clock
        self._file: TextIO | None = None
        self._csv: csv.writer | None = None
        self._partial_path: Path | None = None
        self._final_path: Path | None = None
        self._state = "new"
        self._row_count = 0
        self._first_timestamp: float | None = None
        self._last_timestamp: float | None = None

    def start(self, path_parts: Sequence[str]) -> None:
        if self._state != "new":
            raise RuntimeError(f"writer has already been {self._state}")

        final_path, partial_path = self._safe_paths(path_parts)
        if final_path.exists() or partial_path.exists():
            raise FileExistsError("an EEG capture already exists at this path")

        final_path.parent.mkdir(parents=True, exist_ok=True)
        # Re-resolve after mkdir to close an existing-directory/symlink escape.
        resolved_parent = final_path.parent.resolve()
        if not resolved_parent.is_relative_to(self._root):
            raise ValueError("path resolves outside collection_raw_dir")
        self._final_path = resolved_parent / final_path.name
        self._partial_path = resolved_parent / partial_path.name
        if self._final_path.exists() or self._partial_path.exists():
            raise FileExistsError("an EEG capture already exists at this path")

        try:
            self._file = self._partial_path.open("x", encoding="utf-8", newline="")
            self._csv = csv.writer(self._file, lineterminator="\n")
            self._csv.writerow(CSV_HEADER)
        except Exception:
            self._discard_partial(state="new", reset_paths=True)
            raise
        self._state = "started"

    def append(self, sample: EEGSample) -> None:
        self._ensure_started()
        values = (
            sample.timestamp,
            sample.tp9,
            sample.af7,
            sample.af8,
            sample.tp10,
            sample.tp9_quality,
            sample.af7_quality,
            sample.af8_quality,
            sample.tp10_quality,
        )
        if not all(math.isfinite(value) for value in values):
            raise ValueError("EEG sample values must be finite")
        self._validate_timestamp(sample.timestamp)
        if "\n" in sample.marker or "\r" in sample.marker:
            raise ValueError("sample marker must be a single line")
        self._write_row((*values, sample.marker))

    def mark(self, marker: str) -> None:
        self._ensure_started()
        if not marker.strip() or "\n" in marker or "\r" in marker:
            raise ValueError("marker must be non-empty and single-line")
        timestamp = float(self._clock())
        if not math.isfinite(timestamp):
            raise ValueError("marker timestamp must be finite")
        self._validate_timestamp(timestamp)
        self._write_row((timestamp, "", "", "", "", "", "", "", "", marker))

    def finalize(self) -> RawFileResult:
        if self._state == "finalized":
            raise RuntimeError("writer has already been finalized")
        self._ensure_started()
        assert self._file is not None
        assert self._partial_path is not None
        assert self._final_path is not None

        try:
            self._file.flush()
            os.fsync(self._file.fileno())
            self._file.close()
            self._file = None

            # Calculate every fallible piece of the result while the capture is
            # still partial. After os.replace succeeds, returning the already
            # constructed immutable result cannot strand a final file without
            # its checksum/size metadata.
            contents = self._partial_path.read_bytes()
            result = RawFileResult(
                relative_path=str(self._final_path.relative_to(self._root)),
                sha256=hashlib.sha256(contents).hexdigest(),
                byte_size=len(contents),
                row_count=self._row_count,
                first_timestamp=self._first_timestamp,
                last_timestamp=self._last_timestamp,
            )
            if self._final_path.exists():
                raise FileExistsError("an EEG capture already exists at this path")
            os.replace(self._partial_path, self._final_path)
        except Exception:
            self._discard_partial(state="aborted")
            raise

        self._state = "finalized"
        return result

    def abort(self) -> None:
        if self._state == "finalized":
            raise RuntimeError("writer has already been finalized")
        self._discard_partial(state="aborted")

    def _safe_paths(self, path_parts: Sequence[str]) -> tuple[Path, Path]:
        if len(path_parts) != 3 or any(not isinstance(part, str) for part in path_parts):
            raise ValueError("path must contain participant code, session ID, and capture ID")
        participant, *remaining = path_parts
        if not _PARTICIPANT_CODE.fullmatch(participant):
            raise ValueError("path participant must be a pseudonymous code such as P001")
        if any(not _SAFE_COMPONENT.fullmatch(part) for part in remaining):
            raise ValueError("path components may contain only letters, numbers, '_' and '-'")

        parent = (self._root / participant / remaining[0]).resolve(strict=False)
        if not parent.is_relative_to(self._root):
            raise ValueError("path resolves outside collection_raw_dir")
        final_path = parent / f"{remaining[1]}.csv"
        partial_path = parent / f"{remaining[1]}.partial"
        if not final_path.resolve(strict=False).is_relative_to(self._root):
            raise ValueError("path resolves outside collection_raw_dir")
        return final_path, partial_path

    def _ensure_started(self) -> None:
        if self._state != "started":
            raise RuntimeError(f"writer is {self._state}; an active capture is required")

    def _validate_timestamp(self, timestamp: float) -> None:
        if self._last_timestamp is not None and timestamp <= self._last_timestamp:
            raise ValueError("timestamps must be strictly monotonic")

    def _write_row(self, row: tuple[object, ...]) -> None:
        assert self._csv is not None
        timestamp = float(row[0])
        try:
            self._csv.writerow(row)
        except Exception:
            # csv/TextIO may have emitted some bytes before raising. The only
            # safe recovery is to invalidate and remove the whole capture.
            self._discard_partial(state="aborted")
            raise
        self._row_count += 1
        if self._first_timestamp is None:
            self._first_timestamp = timestamp
        self._last_timestamp = timestamp

    def _discard_partial(self, *, state: str, reset_paths: bool = False) -> None:
        file = self._file
        self._file = None
        self._csv = None
        if file is not None:
            try:
                descriptor = file.fileno()
            except (OSError, ValueError):
                descriptor = None
            try:
                file.close()
            except Exception:
                # A failing TextIO flush can also make close() fail. Release the
                # descriptor directly so Windows permits deletion of the partial.
                if descriptor is not None:
                    try:
                        os.close(descriptor)
                    except OSError:
                        pass
        if self._partial_path is not None:
            self._partial_path.unlink(missing_ok=True)
        self._state = state
        if reset_paths:
            self._partial_path = None
            self._final_path = None
            self._row_count = 0
            self._first_timestamp = None
            self._last_timestamp = None
