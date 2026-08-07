from __future__ import annotations

import asyncio
import inspect
import os
import subprocess
import sys
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.schemas.muse import MuseBridgeState, MuseConnectionStatus, MuseOwner, MuseScanDevice, MuseScanStatus
from app.services.muse_ble import MuseBleDevice, MuseBleScanner
from app.services.muse_device_lease import DeviceLease, DeviceLeaseUnavailableError


@dataclass(slots=True)
class _Bridge:
    address: str
    owners: set[MuseOwner] = field(default_factory=set)
    lease: DeviceLease | None = None
    process: Any | None = None
    owned_process: bool = False
    state: MuseBridgeState = MuseBridgeState.starting_bridge
    startup_task: asyncio.Task | None = None
    monitor_task: asyncio.Task | None = None
    output_task: asyncio.Task | None = None
    close_task: asyncio.Task | None = None
    reaper_task: asyncio.Task | None = None
    ble_connected: asyncio.Event = field(default_factory=asyncio.Event)
    diagnostics: list[str] = field(default_factory=list)
    closed: bool = False


class ManagedMuseBridgeManager:
    """Coordinate one verified LSL bridge and lease per physical Muse headset."""

    _MAX_SCAN_JOBS = 20

    def __init__(self, *, scanner: Any | None = None, stream_resolver: Callable[[], list[Any]] | None = None,
                 process_factory: Callable[..., Any] | None = None, settings: Any | None = None) -> None:
        self._scanner = scanner or MuseBleScanner
        self._stream_resolver = stream_resolver or self._resolve_streams
        self._process_factory = process_factory or asyncio.create_subprocess_exec
        self._settings = settings
        self._scan_jobs: dict[str, tuple[int, MuseScanStatus, asyncio.Task]] = {}
        self._owner_status: dict[MuseOwner, MuseConnectionStatus] = {}
        self._owners: dict[MuseOwner, str] = {}
        self._bridges: dict[str, _Bridge] = {}
        self._diagnostics: dict[str, list[str]] = {}
        self._quarantined: dict[str, _Bridge] = {}
        self._cleanup_tasks: set[asyncio.Task] = set()
        self._cleanup_timeout = 3.0
        self._guard = asyncio.Lock()

    def _current_settings(self):
        return self._settings or get_settings()

    async def start_scan(self, actor_id: int) -> MuseScanStatus:
        async with self._guard:
            self._prune_scans_unlocked()
            for owner, status, task in self._scan_jobs.values():
                if owner == actor_id and not task.done():
                    return status.model_copy(deep=True)
            scan_id = uuid.uuid4().hex
            status = MuseScanStatus(scan_id=scan_id, state=MuseBridgeState.scanning)
            task = asyncio.create_task(self._run_scan(scan_id, actor_id))
            self._scan_jobs[scan_id] = (actor_id, status, task)
            return status.model_copy(deep=True)

    async def get_scan(self, actor_id: int, scan_id: str) -> MuseScanStatus:
        async with self._guard:
            job = self._scan_jobs.get(scan_id)
            if job is None or job[0] != actor_id:
                raise LookupError("Muse scan is unavailable")
            return job[1].model_copy(deep=True)

    async def _run_scan(self, scan_id: str, actor_id: int) -> None:
        try:
            devices = await self._scanner.scan(timeout=self._current_settings().muse_scan_timeout_seconds)
            status = MuseScanStatus(scan_id=scan_id, state=MuseBridgeState.found if devices else MuseBridgeState.not_found,
                                    devices=[MuseScanDevice(address=item.address, name=item.name) for item in devices])
        except asyncio.CancelledError:
            raise
        except Exception:
            status = MuseScanStatus(scan_id=scan_id, state=MuseBridgeState.failed, detail="scan_failed")
        async with self._guard:
            job = self._scan_jobs.get(scan_id)
            if job is not None and job[0] == actor_id:
                self._scan_jobs[scan_id] = (actor_id, status, job[2])

    def _prune_scans_unlocked(self) -> None:
        completed = [scan_id for scan_id, (_, _, task) in self._scan_jobs.items() if task.done()]
        while len(self._scan_jobs) >= self._MAX_SCAN_JOBS and completed:
            self._scan_jobs.pop(completed.pop(0), None)

    @staticmethod
    def _canonical_address(address: str) -> str:
        return address.strip().upper()

    async def connect(self, owner: MuseOwner, device: MuseBleDevice) -> MuseConnectionStatus:
        async with self._guard:
            address = self._canonical_address(device.address)
            existing_address = self._owners.get(owner)
            if existing_address is not None and existing_address != address:
                self._release_owner_unlocked(owner)

            bridge = self._bridges.get(address)
            if bridge is not None and not bridge.closed:
                if owner not in bridge.owners and len(bridge.owners) > 0:
                    return self._set_status(owner, MuseBridgeState.failed, "device_in_use")

            if bridge is None or bridge.closed:
                bridge = _Bridge(address=address)
                self._bridges[address] = bridge
                bridge.startup_task = asyncio.create_task(self._start_bridge(bridge))

            bridge.owners.add(owner)
            self._owners[owner] = address

            if bridge.state is MuseBridgeState.connected:
                if not self._bridge_is_healthy(bridge):
                    await self._fail_bridge_unlocked(bridge, "bridge_exited")
                else:
                    return self._set_status(owner, MuseBridgeState.connected)
            task = bridge.startup_task
            self._set_status(owner, bridge.state)
        if task is not None:
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                async with self._guard:
                    close_task = self._release_owner_unlocked(owner)
                    self._set_status(owner, MuseBridgeState.idle)
                await self._await_cleanup_barriers(close_task)
                raise
        await self._await_cleanup_barriers(bridge.close_task)
        return await self.status(owner)

    async def _start_bridge(self, bridge: _Bridge) -> None:
        try:
            try:
                bridge.lease = DeviceLease(self._current_settings().collection_lock_dir, bridge.address)
                bridge.lease.acquire()
            except DeviceLeaseUnavailableError:
                async with self._guard:
                    await self._fail_bridge_unlocked(bridge, "device_in_use")
                return
            except Exception:
                async with self._guard:
                    await self._fail_bridge_unlocked(bridge, "bridge_failed")
                return
            if self._matching_stream(bridge.address) is None:
                process = await self._launch_process(bridge.address)
                bridge.process = process
                bridge.owned_process = True
                if bridge.closed:
                    return
                bridge.output_task = asyncio.create_task(self._drain_output(bridge))
                await self._transition(bridge, MuseBridgeState.connecting_bluetooth)
                phase = await self._wait_for_bluetooth(bridge)
                if phase != "connected":
                    async with self._guard:
                        await self._fail_bridge_unlocked(bridge, "bridge_exited" if phase == "exited" else "bluetooth_timeout")
                    return
                await self._transition(bridge, MuseBridgeState.waiting_for_lsl)
                phase = await self._wait_for_lsl(bridge)
                if phase != "connected":
                    async with self._guard:
                        await self._fail_bridge_unlocked(bridge, "bridge_exited" if phase == "exited" else "lsl_timeout")
                    return
            await self._transition(bridge, MuseBridgeState.connected)
            if bridge.owned_process:
                bridge.monitor_task = asyncio.create_task(self._monitor_process(bridge))
        except asyncio.CancelledError:
            raise
        except Exception:
            async with self._guard:
                await self._fail_bridge_unlocked(bridge, "bridge_failed")

    async def _transition(self, bridge: _Bridge, state: MuseBridgeState) -> None:
        async with self._guard:
            if bridge.closed:
                return
            bridge.state = state
            for owner in bridge.owners:
                self._set_status(owner, state)

    async def _monitor_process(self, bridge: _Bridge) -> None:
        try:
            await bridge.process.wait()
        except asyncio.CancelledError:
            raise
        except Exception:
            pass
        async with self._guard:
            if not bridge.closed:
                await self._fail_bridge_unlocked(bridge, "bridge_exited")

    async def status(self, owner: MuseOwner) -> MuseConnectionStatus:
        async with self._guard:
            address = self._owners.get(owner)
            bridge = self._bridges.get(address) if address else None
            if bridge is not None and bridge.state is MuseBridgeState.connected and not self._bridge_is_healthy(bridge):
                await self._fail_bridge_unlocked(bridge, "bridge_exited")
            status = self._owner_status.get(owner) or MuseConnectionStatus(owner=owner, state=MuseBridgeState.idle)
            return status.model_copy(deep=True)

    async def health_snapshot(self) -> MuseBridgeState:
        """Return aggregate state from managed in-memory bridges only."""
        async with self._guard:
            if any(status.state is MuseBridgeState.scanning and not task.done() for _, status, task in self._scan_jobs.values()):
                return MuseBridgeState.scanning
            active = tuple(self._bridges.values())
            for bridge in active:
                if bridge.state is MuseBridgeState.connected and self._bridge_is_healthy(bridge):
                    return MuseBridgeState.connected
            for state in (
                MuseBridgeState.scanning,
                MuseBridgeState.starting_bridge,
                MuseBridgeState.connecting_bluetooth,
                MuseBridgeState.waiting_for_lsl,
            ):
                if any(bridge.state is state for bridge in active):
                    return state
            if any(status.state is MuseBridgeState.failed for status in self._owner_status.values()):
                return MuseBridgeState.failed
            return MuseBridgeState.idle

    def _bridge_is_healthy(self, bridge: _Bridge) -> bool:
        if bridge.closed:
            return False
        if bridge.owned_process and (bridge.process is None or bridge.process.returncode is not None):
            return False
        return self._matching_stream(bridge.address) is not None

    async def release(self, owner: MuseOwner) -> MuseConnectionStatus:
        async with self._guard:
            close_task = self._release_owner_unlocked(owner)
            status = MuseConnectionStatus(owner=owner, state=MuseBridgeState.idle)
            self._owner_status.pop(owner, None)
        await self._await_cleanup_barriers(close_task)
        return status

    async def shutdown(self) -> None:
        async with self._guard:
            scans = [task for _, _, task in self._scan_jobs.values() if not task.done()]
            for task in scans:
                task.cancel()
        await asyncio.gather(*scans, return_exceptions=True)
        async with self._guard:
            self._scan_jobs.clear()
            close_tasks = []
            for bridge in tuple(self._bridges.values()):
                close_tasks.append(self._close_bridge_unlocked(bridge))
            self._owners.clear()
            self._owner_status.clear()
        await self._await_cleanup_barriers(*close_tasks)
        async with self._guard:
            reapers = [bridge.reaper_task for bridge in self._quarantined.values() if bridge.reaper_task is not None]
            cleanup_tasks = tuple(self._cleanup_tasks)
        await self._await_cleanup_barriers(*close_tasks, *cleanup_tasks, *reapers)

    def _release_owner_unlocked(self, owner: MuseOwner) -> asyncio.Task | None:
        address = self._owners.pop(owner, None)
        bridge = self._bridges.get(address) if address else None
        if bridge is None:
            return None
        bridge.owners.discard(owner)
        if not bridge.owners:
            return self._close_bridge_unlocked(bridge)
        return None

    async def _fail_bridge_unlocked(self, bridge: _Bridge, detail: str) -> None:
        if bridge.closed:
            return
        for owner in tuple(bridge.owners):
            self._owners.pop(owner, None)
            self._set_status(owner, MuseBridgeState.failed, detail)
        bridge.owners.clear()
        self._close_bridge_unlocked(bridge)

    def _set_status(self, owner: MuseOwner, state: MuseBridgeState, detail: str | None = None) -> MuseConnectionStatus:
        status = MuseConnectionStatus(owner=owner, state=state, detail=detail)
        self._owner_status[owner] = status
        return status.model_copy(deep=True)

    async def _launch_process(self, address: str):
        command = (str(Path(sys.executable).with_name("muselsl.exe")), "stream", "--address", address,
                   "--backend", "bleak", "--lsltime")
        environment = os.environ.copy()
        environment["PYTHONUNBUFFERED"] = "1"
        result = self._process_factory(*command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
                                       env=environment, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return await result if inspect.isawaitable(result) else result

    async def _wait_for_bluetooth(self, bridge: _Bridge) -> str:
        signal = asyncio.create_task(bridge.ble_connected.wait())
        exited = asyncio.create_task(bridge.process.wait())
        try:
            done, _ = await asyncio.wait(
                {signal, exited}, timeout=self._current_settings().muse_connect_timeout_seconds,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if signal in done:
                return "connected"
            return "exited" if exited in done else "timeout"
        finally:
            for task in (signal, exited):
                if not task.done():
                    task.cancel()
            await asyncio.gather(signal, exited, return_exceptions=True)

    async def _wait_for_lsl(self, bridge: _Bridge) -> str:
        deadline = asyncio.get_running_loop().time() + self._current_settings().muse_lsl_timeout_seconds
        while asyncio.get_running_loop().time() < deadline:
            if bridge.process is not None and bridge.process.returncode is not None:
                return "exited"
            if self._matching_stream(bridge.address) is not None:
                return "connected"
            await asyncio.sleep(0.01)
        return "timeout"

    def _matching_stream(self, address: str):
        canonical = self._canonical_address(address)
        for stream in self._stream_resolver():
            try:
                sid = str(stream.source_id()).strip().upper()
                if (sid == f"MUSE{canonical}" or sid == canonical) and float(stream.nominal_srate()) == 256.0:
                    return stream
            except Exception:
                continue
        return None

    @staticmethod
    def _resolve_streams():
        try:
            from pylsl import resolve_byprop
            return resolve_byprop("type", "EEG", timeout=0)
        except Exception:
            return []

    def _record_diagnostic(self, bridge: _Bridge, line: str) -> None:
        if line:
            bridge.diagnostics.append(line)
            del bridge.diagnostics[:-100]

    async def _drain_output(self, bridge: _Bridge) -> None:
        while not bridge.closed and bridge.process is not None:
            raw = await bridge.process.stdout.readline()
            if not raw:
                return
            line = raw.decode("utf-8", "replace").strip()
            self._record_diagnostic(bridge, line)
            if line == "BLE connected.":
                bridge.ble_connected.set()

    def _close_bridge_unlocked(self, bridge: _Bridge) -> asyncio.Task | None:
        if bridge.closed:
            return bridge.close_task
        bridge.closed = True
        self._bridges.pop(bridge.address, None)
        self._diagnostics[bridge.address] = list(bridge.diagnostics)
        starter = bridge.startup_task
        if starter is not None and not starter.done() and starter is not asyncio.current_task():
            starter.cancel()
            bridge.close_task = self._track_cleanup(asyncio.create_task(self._finish_startup_close(bridge, starter)))
            return bridge.close_task
        bridge.close_task = self._track_cleanup(asyncio.create_task(self._finalize_closed_bridge(bridge)))
        return bridge.close_task

    def _track_cleanup(self, task: asyncio.Task) -> asyncio.Task:
        self._cleanup_tasks.add(task)
        task.add_done_callback(self._cleanup_tasks.discard)
        return task

    async def _finish_startup_close(self, bridge: _Bridge, starter: asyncio.Task) -> None:
        await asyncio.gather(starter, return_exceptions=True)
        await self._finalize_closed_bridge(bridge)

    async def _finalize_closed_bridge(self, bridge: _Bridge) -> None:
        monitor = bridge.monitor_task
        if monitor is not None and monitor is not asyncio.current_task():
            monitor.cancel()
            await asyncio.gather(monitor, return_exceptions=True)
        output = bridge.output_task
        if output is not None and output is not asyncio.current_task():
            output.cancel()
            await asyncio.gather(output, return_exceptions=True)
        exited = True
        try:
            if bridge.owned_process and bridge.process is not None and bridge.process.returncode is None:
                exited = await self._stop_process(bridge.process)
        finally:
            if exited and bridge.lease is not None:
                try:
                    bridge.lease.release()
                except Exception:
                    pass
            elif not exited:
                self._quarantined[bridge.address] = bridge
                bridge.reaper_task = self._track_cleanup(asyncio.create_task(self._reap_quarantine(bridge)))

    async def _reap_quarantine(self, bridge: _Bridge) -> None:
        try:
            await bridge.process.wait()
        except Exception:
            return
        if bridge.process.returncode is None:
            return
        async with self._guard:
            if self._quarantined.get(bridge.address) is bridge:
                self._quarantined.pop(bridge.address, None)
                if bridge.lease is not None:
                    try:
                        bridge.lease.release()
                    except Exception:
                        pass

    async def _await_cleanup_barriers(self, *tasks: asyncio.Task | None) -> None:
        pending = [task for task in tasks if task is not None and not task.done()]
        if not pending:
            return
        await asyncio.wait(pending, timeout=self._cleanup_timeout)

    @staticmethod
    async def _stop_process(process: Any) -> bool:
        if process.returncode is not None:
            return True
        try:
            process.terminate()
        except Exception:
            pass
        try:
            await asyncio.wait_for(process.wait(), timeout=1)
        except Exception:
            pass
        if process.returncode is not None:
            return True
        try:
            process.kill()
        except Exception:
            pass
        try:
            await asyncio.wait_for(process.wait(), timeout=1)
        except Exception:
            pass
        return process.returncode is not None


managed_muse_bridge_manager = ManagedMuseBridgeManager()
