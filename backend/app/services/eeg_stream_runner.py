from __future__ import annotations

import asyncio

import numpy as np

from app.schemas.muse import MuseBridgeState
from app.services.eeg_service import EEGStateMachine, Phase
from app.services.muse_stream import LSLMuseStreamSource, MuseStreamSource
from app.ws import eeg_manager


class UserEEGStreamRunner:
    """Feed a verified Muse LSL stream into an ordinary user's EEG machine."""

    def __init__(self, source_factory=LSLMuseStreamSource) -> None:
        self._source_factory = source_factory
        self._tasks: dict[int, asyncio.Task] = {}
        self._sources: dict[int, MuseStreamSource] = {}

    async def start(self, session_id: int, machine: EEGStateMachine, bridge_status) -> bool:
        """Start once the shared bridge has verifiably reached LSL-connected."""
        if bridge_status.state is not MuseBridgeState.connected:
            return False
        task = self._tasks.get(session_id)
        if task is not None and not task.done():
            return True
        if not machine.state.device_id:
            return False
        source = self._source_factory()
        self._sources[session_id] = source
        self._tasks[session_id] = asyncio.create_task(self._pump(session_id, machine, source))
        return True

    async def stop(self, session_id: int) -> None:
        task = self._tasks.pop(session_id, None)
        source = self._sources.pop(session_id, None)
        if source is not None:
            try:
                await source.disconnect()
            except Exception:
                pass
        if task is not None and task is not asyncio.current_task():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async def shutdown(self) -> None:
        await asyncio.gather(*(self.stop(session_id) for session_id in tuple(self._tasks)), return_exceptions=True)

    async def _pump(self, session_id: int, machine: EEGStateMachine, source: MuseStreamSource) -> None:
        try:
            await source.connect(machine.state.device_id or "")
            async for incoming in source.samples():
                sample = incoming.sample
                machine.ingest_samples(
                    np.array([[sample.tp9, sample.af7, sample.af8, sample.tp10]], dtype=float),
                    np.array([sample.timestamp], dtype=float),
                )
                await eeg_manager.broadcast(str(session_id), machine.to_ws_dict())
            await self._mark_disconnected(session_id, machine)
        except asyncio.CancelledError:
            raise
        except Exception:
            await self._mark_disconnected(session_id, machine)
        finally:
            try:
                await source.disconnect()
            except Exception:
                pass
            if self._sources.get(session_id) is source:
                self._sources.pop(session_id, None)
            if self._tasks.get(session_id) is asyncio.current_task():
                self._tasks.pop(session_id, None)

    @staticmethod
    async def _mark_disconnected(session_id: int, machine: EEGStateMachine) -> None:
        machine.state.device_state = "disconnected"
        machine.transition_to(Phase.DISCONNECTED)
        await eeg_manager.broadcast(str(session_id), machine.to_ws_dict())


user_eeg_stream_runner = UserEEGStreamRunner()
