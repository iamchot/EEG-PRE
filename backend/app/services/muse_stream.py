from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator, Callable, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from app.services.raw_eeg_writer import EEGSample


CHANNELS = ("tp9", "af7", "af8", "tp10")


class MuseStreamError(RuntimeError):
    """A safe, operator-facing Muse stream failure."""


@dataclass(frozen=True, slots=True)
class MuseDevice:
    id: str
    name: str


@dataclass(frozen=True, slots=True)
class MuseSample:
    sample: EEGSample
    sensor_timestamps: dict[str, float]


class MuseStreamSource(Protocol):
    async def discover(self) -> list[MuseDevice]: ...
    async def connect(self, device_id: str) -> None: ...
    def samples(self) -> AsyncIterator[MuseSample]: ...
    async def disconnect(self) -> None: ...


class LSLMuseStreamSource:
    """Cancellation-friendly adapter around pylsl's blocking API."""

    def __init__(
        self,
        *,
        discovery_timeout: float = 2.0,
        pull_timeout: float = 0.25,
        stale_after_seconds: float = 2.0,
        clock: Callable[[], float] | None = None,
    ):
        self.discovery_timeout = discovery_timeout
        self.pull_timeout = pull_timeout
        self.stale_after_seconds = stale_after_seconds
        self._clock = clock or self._lsl_clock
        self._inlet: Any | None = None
        self._connected = False
        self._channel_names: tuple[str, ...] = CHANNELS

    async def discover(self) -> list[MuseDevice]:
        try:
            streams = await asyncio.wait_for(
                asyncio.to_thread(self._resolve_streams),
                timeout=self.discovery_timeout + 0.5,
            )
        except (TimeoutError, asyncio.TimeoutError) as exc:
            raise MuseStreamError("Muse discovery timed out") from exc
        return [MuseDevice(self._stream_id(stream), self._stream_name(stream)) for stream in streams]

    async def connect(self, device_id: str) -> None:
        if not device_id.strip():
            raise MuseStreamError("Muse device ID is required")
        streams = await self.discover()
        selected = next((item for item in streams if item.id == device_id), None)
        if selected is None:
            raise MuseStreamError("Muse device not found")
        try:
            inlet, names = await asyncio.wait_for(
                asyncio.to_thread(self._open_inlet, device_id),
                timeout=self.discovery_timeout + 0.5,
            )
        except (TimeoutError, asyncio.TimeoutError) as exc:
            raise MuseStreamError("Muse connection timed out") from exc
        self._inlet = inlet
        self._channel_names = self._validate_channel_names(names)
        self._connected = True

    async def samples(self) -> AsyncIterator[MuseSample]:
        if not self._connected or self._inlet is None:
            raise MuseStreamError("Muse stream is not connected")
        while self._connected:
            try:
                values, timestamp = await asyncio.wait_for(
                    asyncio.to_thread(self._pull_sample),
                    timeout=self.pull_timeout + 0.5,
                )
            except (TimeoutError, asyncio.TimeoutError):
                continue
            if values is None or timestamp is None:
                continue
            try:
                yield self.map_sample(values, float(timestamp))
            except MuseStreamError as exc:
                if "stale" not in str(exc).lower():
                    raise

    async def disconnect(self) -> None:
        self._connected = False
        inlet, self._inlet = self._inlet, None
        if inlet is not None:
            await asyncio.wait_for(
                asyncio.to_thread(self._close_inlet, inlet),
                timeout=self.pull_timeout + 0.5,
            )

    def map_sample(self, values: Sequence[float], timestamp: float) -> MuseSample:
        names = self._validate_channel_names(self._channel_names)
        if len(values) < len(names):
            raise MuseStreamError("Muse sample is missing required channels")
        received_at = float(self._clock())
        age = received_at - timestamp
        if age < -self.stale_after_seconds or age > self.stale_after_seconds:
            raise MuseStreamError("Muse sample timestamp is stale")
        indexed = {name: float(values[index]) for index, name in enumerate(names)}
        sample = EEGSample(
            timestamp=timestamp,
            tp9=indexed["tp9"],
            af7=indexed["af7"],
            af8=indexed["af8"],
            tp10=indexed["tp10"],
            tp9_quality=100.0,
            af7_quality=100.0,
            af8_quality=100.0,
            tp10_quality=100.0,
        )
        return MuseSample(sample, {channel: received_at for channel in CHANNELS})

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
        stream = next((item for item in self._resolve_streams() if self._stream_id(item) == device_id), None)
        if stream is None:
            raise MuseStreamError("Muse device not found")
        inlet = StreamInlet(stream, max_buflen=5)
        return inlet, self._read_channel_names(stream)

    def _pull_sample(self):
        return self._inlet.pull_sample(timeout=self.pull_timeout)

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
        if any(normalized.count(channel) != 1 for channel in CHANNELS):
            raise MuseStreamError("Muse stream must contain TP9, AF7, AF8 and TP10 exactly once")
        return normalized

    @staticmethod
    def _lsl_clock() -> float:
        try:
            from pylsl import local_clock
        except ImportError:
            return time.monotonic()
        return float(local_clock())
