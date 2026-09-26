from __future__ import annotations

import asyncio
import math
import threading
import time
from collections import deque
from collections.abc import AsyncIterator, Callable, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from app.services.raw_eeg_writer import EEGSample
from app.services.signal_processor import SensorQuality, estimate_sensor_state

import numpy as np


CHANNELS = ("tp9", "af7", "af8", "tp10")


class MuseStreamError(RuntimeError):
    """A safe, operator-facing Muse stream failure."""


@dataclass(frozen=True, slots=True)
class MuseDevice:
    id: str
    name: str


@dataclass(frozen=True, slots=True)
class MuseQualityObservation:
    sensors: dict[str, SensorQuality]
    sampling_rate_hz: float | None
    source_sequence: int
    source_timestamp: float
    received_at: float
    cadence_valid: bool = False


@dataclass(frozen=True, slots=True)
class MuseSample:
    sample: EEGSample
    sensor_timestamps: dict[str, float]
    sensors: dict[str, SensorQuality]
    sampling_rate_hz: float | None
    sampling_rate_ok: bool
    capture_eligible: bool = True
    source_sequence: int = 0
    received_at: float = 0.0

    @property
    def quality_observation(self) -> MuseQualityObservation:
        return MuseQualityObservation(
            self.sensors,
            self.sampling_rate_hz,
            self.source_sequence,
            self.sample.timestamp,
            self.received_at,
            self.sampling_rate_ok,
        )


class MuseStreamSource(Protocol):
    async def discover(self) -> list[MuseDevice]: ...
    async def connect(self, device_id: str) -> None: ...
    def samples(self) -> AsyncIterator[MuseSample]: ...
    async def disconnect(self) -> None: ...
    def synchronize_boundary(self, operation: Callable[[], Any]) -> Any: ...


class LSLMuseStreamSource:
    """Cancellation-friendly adapter around pylsl's blocking API."""

    def __init__(
        self,
        *,
        discovery_timeout: float = 2.0,
        pull_timeout: float = 0.25,
        stale_after_seconds: float = 2.0,
        expected_sampling_rate_hz: float = 256.0,
        sampling_tolerance_hz: float = 8.0,
        quality_window_samples: int | None = None,
        clock: Callable[[], float] | None = None,
    ):
        self.discovery_timeout = discovery_timeout
        self.pull_timeout = pull_timeout
        self.stale_after_seconds = stale_after_seconds
        self.expected_sampling_rate_hz = float(expected_sampling_rate_hz)
        self.sampling_tolerance_hz = float(sampling_tolerance_hz)
        window = quality_window_samples or max(16, int(round(self.expected_sampling_rate_hz)))
        self._timestamps: deque[float] = deque(maxlen=window)
        self._channel_windows = {channel: deque(maxlen=window) for channel in CHANNELS}
        self._last_values: tuple[float, ...] | None = None
        self._last_source_timestamp: float | None = None
        self._stale_emitted = False
        self._clock = clock or self._lsl_clock
        self._source_sequence = 0
        self._source_sequence_lock = threading.RLock()
        self._inlet: Any | None = None
        self._connected = False
        self._channel_names: tuple[str, ...] = CHANNELS

    async def discover(self) -> list[MuseDevice]:
        try:
            streams = await asyncio.wait_for(
                asyncio.to_thread(self._resolve_streams),
                timeout=max(self.discovery_timeout, 0.01),
            )
        except (TimeoutError, asyncio.TimeoutError) as exc:
            raise MuseStreamError("Muse discovery timed out") from exc
        except MuseStreamError:
            raise
        except Exception as exc:
            raise MuseStreamError("Muse discovery failed") from exc
        try:
            return [MuseDevice(self._stream_id(stream), self._stream_name(stream)) for stream in streams]
        except Exception as exc:
            raise MuseStreamError("Muse discovery failed") from exc

    async def connect(self, device_id: str) -> None:
        if not device_id.strip():
            raise MuseStreamError("Muse device ID is required")
        canonical = device_id.strip().upper()
        streams = await self.discover()
        selected = next(
            (
                item for item in streams
                if item.id.strip().upper() == canonical
                or item.id.strip().upper() == f"MUSE{canonical}"
                or canonical in item.id.strip().upper()
            ),
            None,
        )
        if selected is None:
            raise MuseStreamError("Muse device not found")
        open_task = asyncio.create_task(asyncio.to_thread(self._open_inlet, device_id))
        try:
            inlet, names = await asyncio.wait_for(
                asyncio.shield(open_task),
                timeout=max(self.discovery_timeout, 0.01),
            )
        except (TimeoutError, asyncio.TimeoutError) as exc:
            open_task.add_done_callback(self._close_late_open)
            raise MuseStreamError("Muse connection timed out") from exc
        except asyncio.CancelledError:
            open_task.add_done_callback(self._close_late_open)
            raise
        except MuseStreamError:
            raise
        except Exception as exc:
            raise MuseStreamError("Muse connection failed") from exc
        self._inlet = inlet
        try:
            self._channel_names = self._validate_channel_names(names)
        except Exception:
            await self.disconnect()
            raise
        self._connected = True

    async def samples(self) -> AsyncIterator[MuseSample]:
        if not self._connected or self._inlet is None:
            raise MuseStreamError("Muse stream is not connected")
        while self._connected:
            try:
                values, timestamp, source_sequence = await asyncio.wait_for(
                    asyncio.to_thread(self._pull_sample),
                    timeout=self.pull_timeout + 0.5,
                )
            except (TimeoutError, asyncio.TimeoutError):
                stale = self.stale_observation()
                if stale is not None:
                    yield stale
                continue
            except MuseStreamError:
                raise
            except Exception as exc:
                raise MuseStreamError("Muse sample read failed") from exc
            if values is None or timestamp is None:
                stale = self.stale_observation()
                if stale is not None:
                    yield stale
                continue
            try:
                yield self.map_sample(
                    values,
                    float(timestamp),
                    source_sequence=source_sequence,
                )
            except MuseStreamError as exc:
                if "stale" not in str(exc).lower():
                    raise

    async def disconnect(self) -> None:
        self._connected = False
        inlet, self._inlet = self._inlet, None
        if inlet is not None:
            try:
                await asyncio.wait_for(
                    asyncio.to_thread(self._close_inlet, inlet),
                    timeout=max(self.pull_timeout, 0.01),
                )
            except (TimeoutError, asyncio.TimeoutError) as exc:
                raise MuseStreamError("Muse disconnect timed out") from exc
            except Exception as exc:
                raise MuseStreamError("Muse disconnect failed") from exc

    def map_sample(
        self,
        values: Sequence[float],
        timestamp: float,
        *,
        source_sequence: int | None = None,
    ) -> MuseSample:
        names = self._validate_channel_names(self._channel_names)
        if len(values) < len(names):
            raise MuseStreamError("Muse sample is missing required channels")
        if source_sequence is None:
            source_sequence = self._reserve_source_sequence()
        received_at = float(self._clock())
        age = received_at - timestamp
        if math.isfinite(timestamp) and (
            age < -self.stale_after_seconds or age > self.stale_after_seconds
        ):
            sensors = {
                channel: SensorQuality(state="stale", quality_score=0.0, timestamp=timestamp)
                for channel in CHANNELS
            }
            return self._mapped_sample(
                values,
                names,
                timestamp,
                sensors,
                None,
                False,
                False,
                received_at,
                source_sequence,
            )
        indexed = {name: float(values[index]) for index, name in enumerate(names)}
        self._last_values = tuple(float(value) for value in values)
        if math.isfinite(timestamp):
            self._last_source_timestamp = timestamp
        self._stale_emitted = False
        timestamp_increases = math.isfinite(timestamp) and (
            not self._timestamps or timestamp > self._timestamps[-1]
        )
        if timestamp_increases:
            self._timestamps.append(timestamp)
            for channel in CHANNELS:
                self._channel_windows[channel].append(indexed[channel])
        sampling_rate = self._sampling_rate()
        sampling_ok = bool(
            timestamp_increases
            and sampling_rate is not None
            and abs(sampling_rate - self.expected_sampling_rate_hz) <= self.sampling_tolerance_hz
        )
        matrix = np.column_stack([self._channel_windows[channel] for channel in CHANNELS])
        sensors = {
            channel: estimate_sensor_state(matrix, index, timestamp, timestamp)
            for index, channel in enumerate(CHANNELS)
        }
        return self._mapped_sample(
            values,
            names,
            timestamp,
            sensors,
            sampling_rate,
            sampling_ok,
            True,
            received_at,
            source_sequence,
        )

    def stale_observation(self) -> MuseSample | None:
        if self._last_values is None or self._last_source_timestamp is None or self._stale_emitted:
            return None
        if float(self._clock()) - self._last_source_timestamp <= self.stale_after_seconds:
            return None
        source_sequence = self._reserve_source_sequence()
        self._stale_emitted = True
        sensors = {
            channel: SensorQuality(state="stale", quality_score=0.0, timestamp=self._last_source_timestamp)
            for channel in CHANNELS
        }
        return self._mapped_sample(
            self._last_values,
            self._validate_channel_names(self._channel_names),
            self._last_source_timestamp,
            sensors,
            self._sampling_rate(),
            False,
            False,
            float(self._clock()),
            source_sequence,
        )

    def _mapped_sample(
        self,
        values: Sequence[float],
        names: Sequence[str],
        timestamp: float,
        sensors: dict[str, SensorQuality],
        sampling_rate: float | None,
        sampling_ok: bool,
        capture_eligible: bool,
        received_at: float,
        source_sequence: int | None = None,
    ) -> MuseSample:
        indexed = {name: float(values[index]) for index, name in enumerate(names)}
        sample = EEGSample(
            timestamp=timestamp,
            tp9=indexed["tp9"],
            af7=indexed["af7"],
            af8=indexed["af8"],
            tp10=indexed["tp10"],
            tp9_quality=sensors["tp9"].quality_score,
            af7_quality=sensors["af7"].quality_score,
            af8_quality=sensors["af8"].quality_score,
            tp10_quality=sensors["tp10"].quality_score,
        )
        return MuseSample(
            sample,
            {channel: timestamp for channel in CHANNELS},
            sensors,
            sampling_rate,
            sampling_ok,
            capture_eligible,
            self._source_sequence if source_sequence is None else source_sequence,
            received_at,
        )

    def source_clock(self) -> float:
        return float(self._clock())

    def latest_source_sequence(self) -> int:
        with self._source_sequence_lock:
            return self._source_sequence

    def synchronize_boundary(self, operation: Callable[[], Any]) -> Any:
        with self._source_sequence_lock:
            return operation()

    def _sampling_rate(self) -> float | None:
        if len(self._timestamps) < 16:
            return None
        elapsed = self._timestamps[-1] - self._timestamps[0]
        return None if elapsed <= 0 else (len(self._timestamps) - 1) / elapsed

    def _resolve_streams(self):
        try:
            from pylsl import resolve_byprop
        except ImportError as exc:  # pragma: no cover - depends on local acquisition runtime
            raise MuseStreamError("pylsl is unavailable") from exc
        return resolve_byprop("type", "EEG", timeout=self.discovery_timeout)

    def _open_inlet(self, device_id: str):
        try:
            from pylsl import StreamInlet
        except ImportError as exc:  # pragma: no cover
            raise MuseStreamError("pylsl is unavailable") from exc
        canonical = device_id.strip().upper()
        stream = next(
            (
                item for item in self._resolve_streams()
                if self._matches_device(item, canonical)
            ),
            None,
        )
        if stream is None:
            raise MuseStreamError("Muse device not found")
        inlet = StreamInlet(stream, max_buflen=5)
        return inlet, self._read_channel_names(stream)

    @classmethod
    def _matches_device(cls, stream: Any, canonical: str) -> bool:
        sid = cls._stream_id(stream).strip().upper()
        return sid == canonical or sid == f"MUSE{canonical}" or canonical in sid

    def _pull_sample(self):
        with self._source_sequence_lock:
            values, timestamp = self._inlet.pull_sample(timeout=self.pull_timeout)
            if values is None or timestamp is None:
                return values, timestamp, None
            self._source_sequence += 1
            return values, timestamp, self._source_sequence

    def _reserve_source_sequence(self) -> int:
        with self._source_sequence_lock:
            self._source_sequence += 1
            return self._source_sequence

    def _close_late_open(self, task: asyncio.Future) -> None:
        if task.cancelled():
            return
        try:
            inlet, _names = task.result()
        except Exception:
            return
        asyncio.create_task(self._close_late_inlet(inlet))

    async def _close_late_inlet(self, inlet) -> None:
        try:
            await asyncio.to_thread(self._close_inlet, inlet)
        except Exception:
            pass

    @staticmethod
    def _close_inlet(inlet) -> None:
        close = getattr(inlet, "close_stream", None)
        if close is not None:
            close()

    @staticmethod
    def _stream_id(stream) -> str:
        return str(stream.source_id() or stream.uid() or stream.name())

    @staticmethod
    def _stream_name(stream) -> str:
        return str(stream.name() or "Muse EEG")

    @staticmethod
    def _read_channel_names(stream) -> tuple[str, ...]:
        labels: list[str] = []
        node = stream.desc().child("channels").child("channel")
        for _ in range(int(stream.channel_count())):
            labels.append(str(node.child_value("label")))
            node = node.next_sibling()
        return tuple(labels)

    @staticmethod
    def _validate_channel_names(names: Sequence[str]) -> tuple[str, ...]:
        normalized = tuple(str(name).strip().lower() for name in names)
        if all(channel in normalized for channel in CHANNELS):
            return normalized
        if len(normalized) >= 4:
            return CHANNELS
        raise MuseStreamError("Muse stream must contain at least 4 EEG channels (TP9, AF7, AF8, TP10)")

    @staticmethod
    def _lsl_clock() -> float:
        try:
            from pylsl import local_clock
        except ImportError:
            return time.monotonic()
        return float(local_clock())
