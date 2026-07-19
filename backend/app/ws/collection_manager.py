from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Callable
from dataclasses import asdict

from fastapi import WebSocket
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.dataset_collection import CollectionSession, CollectionSessionState, TrialState
from app.services.collection_state_machine import (
    CollectionStateMachine,
    InvalidTransitionError,
)
from app.services.muse_stream import LSLMuseStreamSource, MuseStreamSource
from app.services.raw_eeg_writer import AtomicEEGWriter


class CollectionConnectionManager:
    def __init__(self, source_factory: Callable[[], MuseStreamSource] = LSLMuseStreamSource):
        self._source_factory = source_factory
        self._clients: dict[int, set[WebSocket]] = defaultdict(set)
        self._runners: dict[int, CollectionStateMachine] = {}
        self._runner_sessions: dict[int, Session] = {}
        self._sources: dict[int, MuseStreamSource] = {}
        self._tasks: dict[int, asyncio.Task] = {}
        self._sequences: dict[int, int] = defaultdict(int)

    def get_runner(self, db: Session, session: CollectionSession) -> CollectionStateMachine:
        runner = self._runners.get(session.id)
        if runner is not None and runner.db.get_bind() is not db.get_bind():
            self._drop_runner(session.id)
            runner = None
        if runner is None:
            settings = get_settings()
            runner_db = Session(bind=db.get_bind(), expire_on_commit=False)
            owned_session = runner_db.get(CollectionSession, session.id)
            if owned_session is None:
                runner_db.close()
                raise LookupError("Collection session not found")
            runner = CollectionStateMachine.recover(
                runner_db,
                owned_session,
                writer_factory=lambda marker_clock: AtomicEEGWriter(
                    settings.collection_raw_dir,
                    clock=marker_clock,
                ),
            )
            self._runners[session.id] = runner
            self._runner_sessions[session.id] = runner_db
        return runner

    async def connect(self, session_id: int, websocket: WebSocket, db: Session) -> None:
        session = db.get(CollectionSession, session_id)
        if session is None:
            raise LookupError("Collection session not found")
        self._clients[session_id].add(websocket)
        runner = self.get_runner(db, session)
        await self.broadcast(session_id, runner.state())
        if session.device_id and session_id not in self._tasks:
            source = self._source_factory()
            self._sources[session_id] = source
            self._tasks[session_id] = asyncio.create_task(self._pump(session_id, source, runner))

    async def disconnect(self, session_id: int, websocket: WebSocket) -> None:
        clients = self._clients.get(session_id)
        if clients is not None:
            clients.discard(websocket)
        if clients:
            return
        self._clients.pop(session_id, None)
        task = self._tasks.pop(session_id, None)
        source = self._sources.pop(session_id, None)
        if source is not None:
            try:
                await source.disconnect()
            except Exception:
                pass
        if task is not None:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
        runner = self._runners.get(session_id)
        if runner is not None and runner.state().state in {
            CollectionSessionState.baseline,
            CollectionSessionState.in_progress,
        }:
            try:
                runner.interrupt("Muse disconnected")
            except InvalidTransitionError:
                pass
        self._drop_runner(session_id)

    async def publish(self, session_id: int) -> None:
        runner = self._runners.get(session_id)
        if runner is not None:
            await self.broadcast(session_id, runner.state())

    async def broadcast(self, session_id: int, state, *, error: str | None = None) -> None:
        self._sequences[session_id] += 1
        payload = state if isinstance(state, dict) else {
            key: (value.value if hasattr(value, "value") else value)
            for key, value in asdict(state).items()
        }
        payload = {"sequence": self._sequences[session_id], **payload}
        if error:
            payload["stream_error"] = error
        dead = []
        for websocket in tuple(self._clients.get(session_id, ())):
            try:
                await websocket.send_json(payload)
            except Exception:
                dead.append(websocket)
        for websocket in dead:
            self._clients[session_id].discard(websocket)

    async def _pump(
        self,
        session_id: int,
        source: MuseStreamSource,
        runner: CollectionStateMachine,
    ) -> None:
        try:
            device_id = runner.session.device_id
            if device_id is None:
                return
            await source.connect(device_id)
            async for incoming in source.samples():
                before = runner.state()
                capture_active = before.active_baseline is not None or before.trial_state in {
                    TrialState.rest,
                    TrialState.stimulus,
                    TrialState.rating,
                }
                if not capture_active:
                    continue
                runner.accept_sample(incoming.sample, sensor_timestamps=incoming.sensor_timestamps)
                state = runner.state()
                settings = get_settings()
                if (
                    state.state is CollectionSessionState.baseline
                    and state.wall_clock_seconds >= settings.collection_baseline_wall_seconds
                    and state.accepted_clean_seconds >= settings.collection_baseline_min_clean_seconds
                ):
                    state = runner.finish_baseline()
                await self.broadcast(session_id, state)
            self._interrupt_if_active(runner)
            await self.broadcast(session_id, runner.state(), error="Muse disconnected")
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._interrupt_if_active(runner)
            await self.broadcast(session_id, runner.state(), error=str(exc))

    @staticmethod
    def _interrupt_if_active(runner: CollectionStateMachine) -> None:
        if runner.state().state in {CollectionSessionState.baseline, CollectionSessionState.in_progress}:
            try:
                runner.interrupt("Muse disconnected")
            except Exception:
                pass

    def _drop_runner(self, session_id: int) -> None:
        self._runners.pop(session_id, None)
        runner_db = self._runner_sessions.pop(session_id, None)
        if runner_db is not None:
            runner_db.close()


collection_manager = CollectionConnectionManager()
