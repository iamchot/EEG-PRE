from __future__ import annotations

import asyncio
import threading
import time
import weakref
from collections import defaultdict, deque
from collections.abc import Callable
from typing import TypeVar

import numpy as np

from fastapi import WebSocket
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.dataset_collection import CollectionSession, CollectionSessionState, TrialState
from app.schemas.muse import MuseBridgeState, MuseOwner
from app.services.muse_ble import MuseBleDevice
from app.services.muse_bridge_manager import ManagedMuseBridgeManager, managed_muse_bridge_manager
from app.services.collection_state_machine import CollectionStateMachine, InvalidTransitionError
from app.services.collection_state_response import collection_state_response
from app.services.muse_device_lease import DeviceLease, DeviceLeaseUnavailableError
from app.services.muse_stream import LSLMuseStreamSource, MuseStreamError, MuseStreamSource
from app.services.raw_eeg_writer import AtomicEEGWriter, EEGSample
from app.services.signal_processor import SensorQuality, estimate_sensor_state


T = TypeVar("T")

class CollectionContextUnavailableError(RuntimeError):
    """Raised when capture is requested without a live Muse WebSocket context."""


class CollectionConnectionManager:
    """Own and serialize every access to an active collection runner."""

    def __init__(
        self,
        source_factory: Callable[[], MuseStreamSource] | None = None,
        bridge_manager: ManagedMuseBridgeManager | None = None,
    ):
        self._source_factory = source_factory
        self._bridge_manager = bridge_manager or managed_muse_bridge_manager
        self._clients: dict[int, set[WebSocket]] = defaultdict(set)
        self._runners: dict[int, CollectionStateMachine] = {}
        self._runner_sessions: dict[int, Session] = {}
        self._sources: dict[int, MuseStreamSource] = {}
        self._connected_sources: set[int] = set()
        self._tasks: dict[int, asyncio.Task] = {}
        self._ensure_locks: dict[int, asyncio.Lock] = {}
        self._sequences: dict[int, int] = defaultdict(int)
        self._lock_registry_guard = threading.Lock()
        self._locks: weakref.WeakValueDictionary[int, threading.RLock] = weakref.WeakValueDictionary()
        # Rolling EEG sample buffer for Web Bluetooth sessions.
        # Stores the last _WEB_BT_BUFFER_SIZE averaged samples as numpy arrays [tp9,af7,af8,tp10].
        # muse-js delivers ~21 averaged samples/sec (12 raw samples per electrode packet at 256 Hz).
        # 64 samples ≈ 3 seconds of history → sensor quality transitions in ~3 s, not ~12 s.
        self._web_bt_buffers: dict[int, deque] = defaultdict(lambda: deque(maxlen=64))
        # Debounce: per-session, per-channel asymmetric hysteresis.
        # streak: int per channel.  +2 per 'good' packet, -1 per 'poor' packet.
        # Crosses +GOOD_THRESH  → show green.  Crosses -POOR_THRESH → show orange.
        # The asymmetry means brief artifacts (blinks, eye-moves) do NOT knock a
        # green sensor back to orange, but sustained noise does.
        _CHANS = ("tp9", "af7", "af8", "tp10")
        self._quality_streak: dict[int, dict[str, int]] = defaultdict(
            lambda: {ch: 0 for ch in _CHANS}
        )
        # Last DISPLAYED state per channel (the sticky value shown in the horseshoe).
        # Start at 'poor' (orange !) so the user sees immediate feedback on connection
        # rather than a grey '...' that looks like the system isn't working.
        self._quality_display: dict[int, dict[str, str]] = defaultdict(
            lambda: {ch: "poor" for ch in _CHANS}
        )
        self._last_web_bt_sample_at: dict[int, float] = {}
        self._last_web_bt_broadcast_at: dict[int, float] = {}
        self._last_web_bt_timestamp: dict[int, float] = {}

    def run(
        self,
        db: Session,
        session: CollectionSession,
        operation: Callable[[CollectionStateMachine], T],
    ) -> T:
        """Run one request operation under the Session's per-runner lock."""
        with self._session_lock(session.id):
            runner = self._get_runner_unlocked(db, session)
            return operation(runner)

    def run_active(self, session_id: int, operation: Callable[[CollectionStateMachine], T]) -> T:
        """Run one stream/lifecycle operation against an existing runner."""
        with self._session_lock(session_id):
            runner = self._runners.get(session_id)
            if runner is None:
                raise LookupError("Collection runner is not active")
            return operation(runner)

    def run_capture(
        self,
        db: Session,
        session: CollectionSession,
        operation: Callable[[CollectionStateMachine], T],
    ) -> T:
        """Run a capture boundary only while its WebSocket/source context is live."""
        with self._session_lock(session.id):
            if not self._has_live_source_unlocked(session.id):
                raise CollectionContextUnavailableError(
                    "A live Muse connection is required for collection capture"
                )
            runner = self._get_runner_unlocked(db, session)
            return operation(runner)

    def release_if_idle(self, session_id: int) -> bool:
        """Close an HTTP-only runner once no capture or live client can use it."""
        with self._session_lock(session_id):
            if self._clients.get(session_id) or self._sources.get(session_id):
                return False
            task = self._tasks.get(session_id)
            if task is not None and not task.done():
                return False
            if session_id not in self._runners and session_id not in self._runner_sessions:
                return False
            self._drop_runner_unlocked(session_id)
            return True

    async def connect(self, session_id: int, websocket: WebSocket, db: Session) -> None:
        session = db.get(CollectionSession, session_id)
        if session is None:
            raise LookupError("Collection session not found")
        with self._session_lock(session_id):
            self._clients[session_id].add(websocket)
        state = self.run(db, session, lambda runner: runner.state())
        await self.broadcast(session_id, state)
        asyncio.create_task(self.ensure_source(session_id))

    def clear_web_bt_buffer(self, session_id: int, *, preserve_active_flag: bool = False) -> None:
        """Discard accumulated EEG samples and debounce state for a session.

        Call this whenever a new Muse headset is selected so that stale quality
        history from the previous connection does not pollute the quality estimate
        for the new session.
        """
        self._web_bt_buffers.pop(session_id, None)
        self._quality_streak.pop(session_id, None)
        if not preserve_active_flag:
            self._last_web_bt_sample_at.pop(session_id, None)
        self._quality_display.pop(session_id, None)
        self._last_web_bt_broadcast_at.pop(session_id, None)
        self._last_web_bt_timestamp.pop(session_id, None)

    # ── Quality debounce ──────────────────────────────────────────────────────

    # Asymmetric debounce parameters:
    #   good packet: streak += _GOOD_GAIN  (gain fast — confirmed contact)
    #   poor packet: streak -= _POOR_LOSS  (lose slow — tolerate brief artifacts)
    #   show green when streak >= _GOOD_THRESH
    #   show orange when streak <= -_POOR_THRESH
    _GOOD_GAIN   = 2   # +2 per good packet
    _POOR_LOSS   = 1   # -1 per poor packet
    _GOOD_THRESH = 6   # 3 clean packets to go green  (~140 ms) — fast enough to be usable
    _POOR_THRESH = 6   # 6 bad packets to go orange   (~280 ms) — tolerates brief blinks

    def _apply_quality_debounce(
        self,
        session_id: int,
        sensors: dict[str, "SensorQuality"],
    ) -> dict[str, "SensorQuality"]:
        """Apply per-channel asymmetric hysteresis to raw quality estimates.

        Asymmetry: gaining green (+2/packet) is faster than losing it (-1/packet).
        This lets a properly-worn sensor become green quickly (~5 clean packets)
        while brief artifacts — blinks, eye movements, swallowing (~2-5 packets) —
        do NOT knock it back to orange.  Only sustained noise (>8 packets, ~380 ms)
        transitions back to orange.
        """
        streaks = self._quality_streak[session_id]
        displays = self._quality_display[session_id]
        stable: dict[str, SensorQuality] = {}
        for ch, sq in sensors.items():
            s = streaks.get(ch, 0)
            # Update streak asymmetrically
            if sq.state == "good":
                s = min(s + self._GOOD_GAIN, self._GOOD_THRESH)
            elif sq.state == "poor":
                s = max(s - self._POOR_LOSS, -self._POOR_THRESH)
            elif sq.state in ("unknown", "stale"):
                # Drift toward 0 without active signal
                s = max(s - self._POOR_LOSS, 0) if s > 0 else min(s + 1, 0)
            streaks[ch] = s

            # Only update displayed state when crossing a threshold;
            # hold previous value in the transitional zone (true hysteresis).
            if s >= self._GOOD_THRESH:
                displays[ch] = "good"
            elif s <= -self._POOR_THRESH:
                displays[ch] = "poor"
            # else: keep displays[ch] unchanged — this is the sticky behaviour

            stable[ch] = SensorQuality(
                state=displays[ch],
                quality_score=sq.quality_score,
                timestamp=sq.timestamp,
            )
        return stable


    async def disconnect(self, session_id: int, websocket: WebSocket) -> None:
        with self._session_lock(session_id):
            clients = self._clients.get(session_id)
            if clients is not None:
                clients.discard(websocket)
            if clients:
                return
            self._clients.pop(session_id, None)
            self._last_web_bt_sample_at.pop(session_id, None)
        await self.stop_source(session_id)
        with self._session_lock(session_id):
            runner = self._runners.get(session_id)
            if runner is not None:
                self._interrupt_if_active_unlocked(runner)
            self._drop_runner_unlocked(session_id)

    async def ensure_source(self, session_id: int) -> None:
        ensure_lock = self._ensure_locks.setdefault(session_id, asyncio.Lock())
        async with ensure_lock:
            await self._ensure_source(session_id)

    async def _ensure_source(self, session_id: int) -> None:
        """Start or restart acquisition when a client and selected device exist."""
        with self._session_lock(session_id):
            if not self._clients.get(session_id):
                return
            existing = self._tasks.get(session_id)
            if existing is not None and not existing.done():
                return
            runner = self._runners.get(session_id)
            if runner is None or not runner.session.device_id:
                return
            if runner.session.state in {
                CollectionSessionState.completed,
                CollectionSessionState.failed,
                CollectionSessionState.withdrawn,
            }:
                return
            now = time.monotonic()
            if (
                len(self._web_bt_buffers.get(session_id, ())) > 0
                or (now - self._last_web_bt_sample_at.get(session_id, 0.0)) < 15.0
            ):
                return
            device_id = runner.session.device_id
            device_name = getattr(runner.session, "device_name", None) or "Muse"
        owner = MuseOwner(kind="collection", session_id=session_id)
        bridge_status = await self._bridge_manager.connect(
            owner,
            MuseBleDevice(address=device_id, name=device_name),
        )
        if bridge_status.state is not MuseBridgeState.connected:
            return
        installed = False
        try:
            with self._session_lock(session_id):
                if not self._clients.get(session_id) or self._tasks.get(session_id) is not None:
                    return
                runner = self._runners.get(session_id)
                if runner is None or runner.session.device_id != device_id:
                    return
                if self._source_factory is None:
                    settings = get_settings()
                    source = LSLMuseStreamSource(
                        expected_sampling_rate_hz=settings.collection_sampling_rate_hz,
                        sampling_tolerance_hz=settings.collection_sampling_tolerance_hz,
                    )
                else:
                    source = self._source_factory()
                source_clock = getattr(source, "source_clock", None)
                source_sequence = getattr(source, "latest_source_sequence", None)
                source_boundary = getattr(source, "synchronize_boundary", None)
                if callable(source_clock) and callable(source_sequence):
                    runner.bind_source(
                        source_clock,
                        source_sequence,
                        source_boundary if callable(source_boundary) else None,
                    )
                self._sources[session_id] = source
                self._tasks[session_id] = asyncio.create_task(
                    self._pump(session_id, source, device_id=device_id)
                )
                installed = True
        finally:
            if not installed:
                await self._bridge_manager.release(owner)

    async def stop_source(self, session_id: int) -> None:
        with self._session_lock(session_id):
            task = self._tasks.pop(session_id, None)
            source = self._sources.pop(session_id, None)
            self._connected_sources.discard(session_id)
        if source is not None:
            try:
                await source.disconnect()
            except Exception:
                pass
        current = asyncio.current_task()
        if task is not None and task is not current:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        await self._bridge_manager.release(MuseOwner(kind="collection", session_id=session_id))

    async def publish(self, session_id: int, state=None) -> None:
        if state is None:
            try:
                state = self.run_active(session_id, lambda runner: runner.state())
            except LookupError:
                return
        await self.broadcast(session_id, state)

    async def ingest_web_bluetooth_sample(
        self,
        session_id: int,
        tp9: float,
        af7: float,
        af8: float,
        tp10: float,
        timestamp: float,
    ) -> None:
        """
        Accept a single EEG sample from the browser via Web Bluetooth (muse-js)
        and route it through the collection state machine.

        Maintains a per-session rolling window of the last 64 averaged samples and
        uses estimate_sensor_state() to compute real contact quality from EEG
        amplitude and variance.  Quality states are debounced via
        _apply_quality_debounce() to prevent horseshoe flickering caused by
        natural EEG bursts (alpha waves, blinks).
        """
        # ── 1. Append to per-session rolling buffer ──────────────────────────
        buf = self._web_bt_buffers[session_id]
        buf.append([tp9, af7, af8, tp10])
        self._last_web_bt_sample_at[session_id] = time.monotonic()

        # ── 2. Build samples matrix for quality estimation ────────────────────
        matrix = np.array(buf, dtype=float)   # shape: (N, 4)

        # Channel order: 0=TP9, 1=AF7, 2=AF8, 3=TP10 (same as LSL path)
        _CHANNELS = ("tp9", "af7", "af8", "tp10")
        raw_sensors = {
            ch: estimate_sensor_state(matrix, idx, timestamp, timestamp)
            for idx, ch in enumerate(_CHANNELS)
        }

        # ── 3. Debounce: smooth out per-packet quality flickers ───────────────
        sensors = self._apply_quality_debounce(session_id, raw_sensors)

        # ── 4. Derive quality scores for EEGSample (0-100 scale) ─────────────
        def _qscore(ch: str) -> float:
            return raw_sensors[ch].quality_score   # use raw score for file metadata

        # Guarantee strictly monotonic timestamp for the raw EEG writer
        last_ts = self._last_web_bt_timestamp.get(session_id, 0.0)
        if timestamp <= last_ts:
            timestamp = last_ts + 0.001
        self._last_web_bt_timestamp[session_id] = timestamp

        sample = EEGSample(
            timestamp=timestamp,
            tp9=tp9, af7=af7, af8=af8, tp10=tp10,
            tp9_quality=_qscore("tp9"), af7_quality=_qscore("af7"),
            af8_quality=_qscore("af8"), tp10_quality=_qscore("tp10"),
        )

        # ── 5. Create adapter object for _accept_sample_unlocked ─────────────
        class _WebBtSample:
            """Minimal adapter bridging Web Bluetooth data to the collection pipeline."""
            def __init__(self):
                self.sample = sample
                self.sensors = sensors
                self.sensor_timestamps = {ch: timestamp for ch in _CHANNELS}
                self.sampling_rate_hz = 256.0
                self.sampling_rate_ok = True
                self.capture_eligible = True
                self.source_sequence = None

        incoming = _WebBtSample()
        try:
            def _step(runner: CollectionStateMachine):
                before = runner.state()
                after, captured = self._accept_sample_unlocked(runner, incoming)
                return before, after, captured

            before, state, _ = self.run_active(session_id, _step)
            now_mono = time.monotonic()
            last_bc = self._last_web_bt_broadcast_at.get(session_id, 0.0)
            state_changed = (
                state.state != before.state
                or state.trial_state != before.trial_state
                or state.active_baseline != before.active_baseline
                or state.completed_trials != before.completed_trials
            )
            # Throttle WebSocket broadcast to ~4 Hz (interval >= 250ms) to prevent
            # main-thread UI congestion and DB session contention, while still
            # broadcasting immediately on any discrete phase change.
            if state_changed or (now_mono - last_bc) >= 0.25:
                self._last_web_bt_broadcast_at[session_id] = now_mono
                await self.broadcast(session_id, state)
        except LookupError:
            pass  # No active runner for this session yet


    async def broadcast(self, session_id: int, state, *, error: str | None = None) -> None:
        lock = self._session_lock(session_id)
        with lock:
            self._sequences[session_id] += 1
            sequence = self._sequences[session_id]
            clients = tuple(self._clients.get(session_id, ()))
            runner_db = self._runner_sessions.get(session_id)
            payload = collection_state_response(runner_db, state).model_dump(mode="json")
        payload = {"sequence": sequence, **payload}
        if error:
            payload["stream_error"] = error
        dead = []
        for websocket in clients:
            try:
                await websocket.send_json(payload)
            except Exception:
                dead.append(websocket)
        with lock:
            for websocket in dead:
                self._clients[session_id].discard(websocket)
            self._cleanup_metadata_unlocked(session_id)

    async def _pump(
        self,
        session_id: int,
        source: MuseStreamSource,
        runner: CollectionStateMachine | None = None,
        *,
        device_id: str | None = None,
    ) -> None:
        # Supplying runner is useful for isolated adapter tests; production
        # always registers it before starting the task.
        if runner is not None:
            with self._session_lock(session_id):
                self._runners.setdefault(session_id, runner)
        try:
            if device_id is None:
                device_id = self.run_active(session_id, lambda active: active.session.device_id)
            if not device_id:
                return
            await source.connect(device_id)
            with self._session_lock(session_id):
                if self._sources.get(session_id) is source:
                    self._connected_sources.add(session_id)
            async for incoming in source.samples():
                state, captured = self.run_active(
                    session_id,
                    lambda active: self._accept_sample_unlocked(active, incoming),
                )
                if captured:
                    await self.broadcast(session_id, state)
            state = self.run_active(
                session_id,
                lambda active: self._interrupt_and_state_unlocked(active),
            )
            await self.broadcast(session_id, state, error="Muse disconnected")
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            try:
                state = self.run_active(
                    session_id,
                    lambda active: self._interrupt_and_state_unlocked(active),
                )
            except Exception:
                return
            safe_error = str(exc) if isinstance(exc, MuseStreamError) else "Muse stream failed"
            await self.broadcast(session_id, state, error=safe_error)
        finally:
            try:
                await source.disconnect()
            except Exception:
                pass
            current = asyncio.current_task()
            with self._session_lock(session_id):
                self._connected_sources.discard(session_id)
                if self._tasks.get(session_id) is current:
                    self._tasks.pop(session_id, None)
                if self._sources.get(session_id) is source:
                    self._sources.pop(session_id, None)
                self._cleanup_metadata_unlocked(session_id)

    @staticmethod
    def _accept_sample_unlocked(runner: CollectionStateMachine, incoming) -> tuple[object, bool]:
        before = runner.state()
        observation = getattr(incoming, "quality_observation", None)
        if observation is None:
            quality_state = runner.observe_quality(
                incoming.sensors,
                sampling_rate_hz=incoming.sampling_rate_hz,
                sampling_rate_ok=incoming.sampling_rate_ok,
            )
        else:
            quality_state = runner.observe_quality(observation)
        capture_active = before.active_baseline is not None or before.trial_state in {
            TrialState.rest,
            TrialState.stimulus,
            TrialState.rating,
        }
        if not capture_active or not incoming.capture_eligible:
            return runner.state(), True
        runner.accept_sample(
            incoming.sample,
            sensor_timestamps=incoming.sensor_timestamps,
            sampling_rate_ok=quality_state.sampling_rate_ok,
            source_sequence=getattr(incoming, "source_sequence", None),
        )
        state = runner.state()
        settings = get_settings()
        if (
            state.state is CollectionSessionState.baseline
            and state.wall_clock_seconds >= settings.collection_baseline_wall_seconds
            and state.accepted_clean_seconds >= settings.collection_baseline_min_clean_seconds
        ):
            state = runner.finish_baseline()
        return state, True

    @classmethod
    def _interrupt_and_state_unlocked(cls, runner: CollectionStateMachine):
        cls._interrupt_if_active_unlocked(runner)
        return runner.state()

    @staticmethod
    def _interrupt_if_active_unlocked(runner: CollectionStateMachine) -> None:
        if runner.state().state in {CollectionSessionState.baseline, CollectionSessionState.in_progress}:
            try:
                runner.interrupt("Muse disconnected")
            except InvalidTransitionError:
                pass

    def _get_runner_unlocked(
        self,
        db: Session,
        session: CollectionSession,
    ) -> CollectionStateMachine:
        runner = self._runners.get(session.id)
        if runner is not None and runner.db.get_bind() is not db.get_bind():
            self._drop_runner_unlocked(session.id)
            runner = None
        if runner is None:
            settings = get_settings()
            runner_db = Session(bind=db.get_bind(), expire_on_commit=False)
            try:
                owned_session = runner_db.get(CollectionSession, session.id)
                if owned_session is None:
                    raise LookupError("Collection session not found")
                runner = CollectionStateMachine.recover(
                    runner_db,
                    owned_session,
                    writer_factory=lambda marker_clock: AtomicEEGWriter(
                        settings.collection_raw_dir,
                        clock=marker_clock,
                    ),
                )
            except BaseException:
                self._close_session_safely(runner_db)
                raise
            self._runners[session.id] = runner
            self._runner_sessions[session.id] = runner_db
        return runner

    def _drop_runner_unlocked(self, session_id: int) -> None:
        self._runners.pop(session_id, None)
        runner_db = self._runner_sessions.pop(session_id, None)
        if runner_db is not None:
            self._close_session_safely(runner_db)
        self._cleanup_metadata_unlocked(session_id)

    def _session_lock(self, session_id: int) -> threading.RLock:
        with self._lock_registry_guard:
            lock = self._locks.get(session_id)
            if lock is None:
                lock = threading.RLock()
                self._locks[session_id] = lock
            return lock

    def _cleanup_metadata_unlocked(self, session_id: int) -> None:
        if not self._clients.get(session_id):
            self._clients.pop(session_id, None)
        task = self._tasks.get(session_id)
        if task is not None and task.done():
            self._tasks.pop(session_id, None)
        if any((
            self._clients.get(session_id),
            self._runners.get(session_id),
            self._runner_sessions.get(session_id),
            self._sources.get(session_id),
            self._tasks.get(session_id),
            session_id in self._connected_sources,
        )):
            return
        self._sequences.pop(session_id, None)

    @staticmethod
    def _close_session_safely(runner_db: Session) -> None:
        try:
            runner_db.close()
        except Exception:
            pass

    def _has_live_source_unlocked(self, session_id: int) -> bool:
        task = self._tasks.get(session_id)
        has_lsl = bool(
            self._clients.get(session_id)
            and self._sources.get(session_id) is not None
            and session_id in self._connected_sources
            and task is not None
            and not task.done()
        )
        now = time.monotonic()
        has_web_bt = bool(
            self._clients.get(session_id)
            and (
                len(self._web_bt_buffers.get(session_id, ())) > 0
                or (now - self._last_web_bt_sample_at.get(session_id, 0.0)) < 10.0
            )
        )
        return has_lsl or has_web_bt


collection_manager = CollectionConnectionManager()
