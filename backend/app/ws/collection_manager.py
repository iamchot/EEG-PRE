from __future__ import annotations

import asyncio
import hashlib
import threading
import weakref
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

from fastapi import WebSocket
from filelock import FileLock, Timeout
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.dataset_collection import CollectionSession, CollectionSessionState, TrialState
from app.services.collection_state_machine import CollectionStateMachine, InvalidTransitionError
from app.services.collection_state_response import collection_state_response
from app.services.muse_stream import LSLMuseStreamSource, MuseStreamError, MuseStreamSource
from app.services.raw_eeg_writer import AtomicEEGWriter


T = TypeVar("T")

_device_registry_guard = threading.Lock()
_device_registry: dict[str, object] = {}


class DeviceLeaseUnavailableError(MuseStreamError):
    """Public, device-neutral conflict raised when acquisition is already owned."""


class DeviceLease:
    """A nonblocking process registry plus crash-safe OS file lease for one device."""

    def __init__(self, lock_dir: str | Path, device_id: str):
        digest = hashlib.sha256(device_id.encode("utf-8")).hexdigest()
        self.path = Path(lock_dir) / f"{digest}.lock"
        self._digest = digest
        self._owner = object()
        self._lock = FileLock(self.path)
        self._acquired = False

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with _device_registry_guard:
            if self._digest in _device_registry:
                raise DeviceLeaseUnavailableError("Muse device is already in use")
            _device_registry[self._digest] = self._owner
        try:
            self._lock.acquire(timeout=0)
        except BaseException as exc:
            with _device_registry_guard:
                if _device_registry.get(self._digest) is self._owner:
                    _device_registry.pop(self._digest, None)
            if isinstance(exc, Timeout):
                raise DeviceLeaseUnavailableError("Muse device is already in use") from exc
            raise
        self._acquired = True

    def release(self) -> None:
        if not self._acquired:
            return
        try:
            self._lock.release()
        finally:
            with _device_registry_guard:
                if _device_registry.get(self._digest) is self._owner:
                    _device_registry.pop(self._digest, None)
            self._acquired = False


class CollectionContextUnavailableError(RuntimeError):
    """Raised when capture is requested without a live Muse WebSocket context."""


class CollectionConnectionManager:
    """Own and serialize every access to an active collection runner."""

    def __init__(self, source_factory: Callable[[], MuseStreamSource] | None = None):
        self._source_factory = source_factory
        self._clients: dict[int, set[WebSocket]] = defaultdict(set)
        self._runners: dict[int, CollectionStateMachine] = {}
        self._runner_sessions: dict[int, Session] = {}
        self._sources: dict[int, MuseStreamSource] = {}
        self._connected_sources: set[int] = set()
        self._tasks: dict[int, asyncio.Task] = {}
        self._sequences: dict[int, int] = defaultdict(int)
        self._lock_registry_guard = threading.Lock()
        self._locks: weakref.WeakValueDictionary[int, threading.RLock] = weakref.WeakValueDictionary()

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
        await self.ensure_source(session_id)

    async def disconnect(self, session_id: int, websocket: WebSocket) -> None:
        with self._session_lock(session_id):
            clients = self._clients.get(session_id)
            if clients is not None:
                clients.discard(websocket)
            if clients:
                return
            self._clients.pop(session_id, None)
        await self.stop_source(session_id)
        with self._session_lock(session_id):
            runner = self._runners.get(session_id)
            if runner is not None:
                self._interrupt_if_active_unlocked(runner)
            self._drop_runner_unlocked(session_id)

    async def ensure_source(self, session_id: int) -> None:
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
            device_id = runner.session.device_id
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

    async def publish(self, session_id: int, state=None) -> None:
        if state is None:
            try:
                state = self.run_active(session_id, lambda runner: runner.state())
            except LookupError:
                return
        await self.broadcast(session_id, state)

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
        lease = None
        try:
            if device_id is None:
                device_id = self.run_active(session_id, lambda active: active.session.device_id)
            if not device_id:
                return
            lease = DeviceLease(get_settings().collection_lock_dir, device_id)
            lease.acquire()
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
            if lease is not None:
                try:
                    lease.release()
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
        return bool(
            self._clients.get(session_id)
            and self._sources.get(session_id) is not None
            and session_id in self._connected_sources
            and task is not None
            and not task.done()
        )


collection_manager = CollectionConnectionManager()
