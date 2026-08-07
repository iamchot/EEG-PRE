import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

from app.schemas.muse import MuseBridgeState, MuseOwner
from app.services.muse_ble import MuseBleDevice
from app.services.muse_bridge_manager import ManagedMuseBridgeManager


class FakeStream:
    def __init__(self, source_id: str, rate: float):
        self._source_id = source_id
        self._rate = rate

    def source_id(self):
        return self._source_id

    def nominal_srate(self):
        return self._rate


class NeverEndingReader:
    async def readline(self):
        await asyncio.Event().wait()


class LinesReader:
    def __init__(self, lines=()):
        self._lines = asyncio.Queue()
        for line in lines:
            self._lines.put_nowait(line.encode("utf-8") + b"\n")

    async def readline(self):
        return await self._lines.get()


class FakeProcess:
    def __init__(self, lines=(), returncode=None):
        self.stdout = LinesReader(lines) if lines else NeverEndingReader()
        self.returncode = returncode
        self.terminated = 0
        self.killed = 0

    async def wait(self):
        while self.returncode is None:
            await asyncio.sleep(0)
        return self.returncode

    def terminate(self):
        self.terminated += 1
        self.returncode = 0

    def kill(self):
        self.killed += 1
        self.returncode = 0


def settings(tmp_path, **overrides):
    values = dict(
        collection_lock_dir=str(tmp_path / "locks"),
        muse_scan_timeout_seconds=0.2,
        muse_connect_timeout_seconds=0.05,
        muse_lsl_timeout_seconds=0.05,
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def test_start_scan_returns_scanning_before_the_hardware_scan_finishes(tmp_path):
    async def scenario():
        started = asyncio.Event()
        finish = asyncio.Event()

        class Scanner:
            async def scan(self, *, timeout):
                assert timeout == 0.2
                started.set()
                await finish.wait()
                return [MuseBleDevice(address="AA:BB", name="Muse-A1")]

        manager = ManagedMuseBridgeManager(scanner=Scanner(), settings=settings(tmp_path))
        scan = await manager.start_scan(actor_id=7)
        assert scan.state is MuseBridgeState.scanning
        await started.wait()
        assert (await manager.get_scan(7, scan.scan_id)).state is MuseBridgeState.scanning
        finish.set()
        await asyncio.sleep(0)
        finished = await manager.get_scan(7, scan.scan_id)
        assert finished.state is MuseBridgeState.found
        assert [(device.address, device.name) for device in finished.devices] == [("AA:BB", "Muse-A1")]

    asyncio.run(scenario())


def test_connect_declares_connected_only_after_matching_256_hz_lsl_stream(tmp_path):
    async def scenario():
        resolve_calls = 0
        process = FakeProcess(["BLE connected."])

        def resolve():
            nonlocal resolve_calls
            resolve_calls += 1
            return [] if resolve_calls == 1 else [FakeStream("MuseAA:BB", 256)]

        manager = ManagedMuseBridgeManager(
            stream_resolver=resolve,
            process_factory=lambda *args, **kwargs: process,
            settings=settings(tmp_path),
        )
        owner = MuseOwner(kind="collection", session_id=4)
        task = asyncio.create_task(manager.connect(owner, MuseBleDevice("AA:BB", "Muse-A1")))
        await asyncio.sleep(0)
        assert (await manager.status(owner)).state is not MuseBridgeState.connected
        status = await task
        assert status.state is MuseBridgeState.connected
        assert resolve_calls >= 2
        await manager.shutdown()

    asyncio.run(scenario())


def test_connect_starts_one_hidden_process_with_the_exact_safe_command(tmp_path):
    async def scenario():
        calls = []
        process = FakeProcess(["BLE connected."])

        def launch(*args, **kwargs):
            calls.append((args, kwargs))
            return process

        resolves = 0

        def resolve():
            nonlocal resolves
            resolves += 1
            return [] if resolves == 1 else [FakeStream("MuseEE:FF", 256)]

        manager = ManagedMuseBridgeManager(
            stream_resolver=resolve,
            process_factory=launch,
            settings=settings(tmp_path),
        )
        await manager.connect(MuseOwner(kind="collection", session_id=4), MuseBleDevice("AA:BB", "Muse-A1"))
        assert calls[0][0] == (
            str(Path(sys.executable).with_name("muselsl.exe")),
            "stream", "--address", "AA:BB", "--backend", "bleak", "--lsltime",
        )
        assert calls[0][1]["env"]["PYTHONUNBUFFERED"] == "1"
        assert calls[0][1]["creationflags"] != 0
        await manager.shutdown()

    asyncio.run(scenario())


def test_connect_rejects_a_second_manager_lease_for_the_same_address(tmp_path):
    async def scenario():
        stream = lambda: [FakeStream("MuseAA:BB", 256)]
        first = ManagedMuseBridgeManager(stream_resolver=stream, settings=settings(tmp_path))
        second = ManagedMuseBridgeManager(stream_resolver=stream, settings=settings(tmp_path))
        device = MuseBleDevice("AA:BB", "Muse-A1")
        await first.connect(MuseOwner(kind="collection", session_id=1), device)
        status = await second.connect(MuseOwner(kind="collection", session_id=2), device)
        assert status.state is MuseBridgeState.failed
        assert status.detail == "device_in_use"
        await first.shutdown()
        await second.shutdown()

    asyncio.run(scenario())


def test_exclusive_single_session_ownership_rejects_second_owner(tmp_path):
    async def scenario():
        launches = []
        process = FakeProcess(["BLE connected."])
        resolve_calls = 0

        def resolve():
            nonlocal resolve_calls
            resolve_calls += 1
            return [] if resolve_calls == 1 else [FakeStream("MuseAA:BB", 256)]

        def launch(*args, **kwargs):
            launches.append((args, kwargs))
            return process

        manager = ManagedMuseBridgeManager(
            stream_resolver=resolve, process_factory=launch, settings=settings(tmp_path),
        )
        device = MuseBleDevice("AA:BB", "Muse-A1")
        first = MuseOwner(kind="user", session_id=1)
        second = MuseOwner(kind="collection", session_id=2)
        
        # First owner connects successfully
        status1 = await manager.connect(first, device)
        assert status1.state is MuseBridgeState.connected

        # Second owner attempting to connect to the same physical address must be rejected
        status2 = await manager.connect(second, device)
        assert status2.state is MuseBridgeState.failed
        assert status2.detail == "device_in_use"

        # Idempotent reconnect for the FIRST owner should still succeed
        status1_reconnect = await manager.connect(first, device)
        assert status1_reconnect.state is MuseBridgeState.connected

        await manager.release(first)
        assert process.terminated == 1
        await manager.shutdown()

    asyncio.run(scenario())


def test_connect_canonicalizes_address_formatting(tmp_path):
    async def scenario():
        process = FakeProcess(["BLE connected."])
        resolve_calls = 0

        def resolve():
            nonlocal resolve_calls
            resolve_calls += 1
            return [] if resolve_calls == 1 else [FakeStream("MuseAA:BB:CC:DD:EE:FF", 256)]

        manager = ManagedMuseBridgeManager(
            stream_resolver=resolve, process_factory=lambda *args, **kwargs: process, settings=settings(tmp_path),
        )
        # First owner connects with lowercase address
        device_lower = MuseBleDevice("aa:bb:cc:dd:ee:ff", "Muse-A1")
        first = MuseOwner(kind="user", session_id=1)
        assert (await manager.connect(first, device_lower)).state is MuseBridgeState.connected

        # Second owner connects with uppercase address with leading/trailing spaces
        device_upper = MuseBleDevice(" AA:BB:CC:DD:EE:FF ", "Muse-A1")
        second = MuseOwner(kind="collection", session_id=2)
        status2 = await manager.connect(second, device_upper)
        assert status2.state is MuseBridgeState.failed
        assert status2.detail == "device_in_use"

        await manager.release(first)
        await manager.shutdown()

    asyncio.run(scenario())


def test_release_owner_cleans_up_owner_status_and_restores_health(tmp_path):
    async def scenario():
        process = FakeProcess(returncode=1)
        manager = ManagedMuseBridgeManager(
            stream_resolver=lambda: [], process_factory=lambda *args, **kwargs: process,
            settings=settings(tmp_path),
        )
        owner = MuseOwner(kind="user", session_id=1)
        status = await manager.connect(owner, MuseBleDevice("AA:BB", "Muse-A1"))
        assert status.state is MuseBridgeState.failed
        assert (await manager.health_snapshot()) is MuseBridgeState.failed

        # Releasing owner must prune owner_status and restore aggregate health to idle
        rel_status = await manager.release(owner)
        assert rel_status.state is MuseBridgeState.idle
        assert (await manager.health_snapshot()) is MuseBridgeState.idle
        assert owner not in manager._owner_status

        await manager.shutdown()

    asyncio.run(scenario())


def test_shutdown_clears_owner_status_map(tmp_path):
    async def scenario():
        process = FakeProcess(returncode=1)
        manager = ManagedMuseBridgeManager(
            stream_resolver=lambda: [], process_factory=lambda *args, **kwargs: process,
            settings=settings(tmp_path),
        )
        owner = MuseOwner(kind="user", session_id=1)
        await manager.connect(owner, MuseBleDevice("AA:BB", "Muse-A1"))
        assert len(manager._owner_status) > 0

        await manager.shutdown()
        assert len(manager._owner_status) == 0

    asyncio.run(scenario())



def test_connect_handles_early_process_exit_without_exposing_output(tmp_path):
    async def scenario():
        process = FakeProcess(returncode=1)
        manager = ManagedMuseBridgeManager(
            stream_resolver=lambda: [], process_factory=lambda *args, **kwargs: process,
            settings=settings(tmp_path),
        )
        status = await manager.connect(MuseOwner(kind="user", session_id=1), MuseBleDevice("AA:BB", "Muse-A1"))
        assert status.state is MuseBridgeState.failed
        assert status.detail == "bridge_exited"
        assert not hasattr(status, "diagnostics")

    asyncio.run(scenario())


def test_connect_fails_on_ble_and_lsl_timeouts_and_cleans_up_owned_processes(tmp_path):
    async def scenario():
        no_ble = FakeProcess()
        manager = ManagedMuseBridgeManager(
            stream_resolver=lambda: [], process_factory=lambda *args, **kwargs: no_ble,
            settings=settings(tmp_path, muse_connect_timeout_seconds=0.01),
        )
        status = await manager.connect(MuseOwner(kind="user", session_id=1), MuseBleDevice("AA:BB", "Muse-A1"))
        assert (status.state, status.detail, no_ble.terminated) == (MuseBridgeState.failed, "bluetooth_timeout", 1)

        no_lsl = FakeProcess(["BLE connected."])
        manager = ManagedMuseBridgeManager(
            stream_resolver=lambda: [], process_factory=lambda *args, **kwargs: no_lsl,
            settings=settings(tmp_path, muse_lsl_timeout_seconds=0.01),
        )
        status = await manager.connect(MuseOwner(kind="user", session_id=2), MuseBleDevice("CC:DD", "Muse-A2"))
        assert (status.state, status.detail, no_lsl.terminated) == (MuseBridgeState.failed, "lsl_timeout", 1)

    asyncio.run(scenario())


def test_cancellation_and_shutdown_terminate_only_owned_bridge_processes(tmp_path):
    async def scenario():
        owned = FakeProcess()
        manager = ManagedMuseBridgeManager(
            stream_resolver=lambda: [], process_factory=lambda *args, **kwargs: owned,
            settings=settings(tmp_path),
        )
        task = asyncio.create_task(manager.connect(MuseOwner(kind="user", session_id=1), MuseBleDevice("AA:BB", "Muse-A1")))
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        task.cancel()
        with __import__("pytest").raises(asyncio.CancelledError):
            await task
        assert owned.terminated == 1

        external = FakeProcess()
        launches = []

        def launch(*args, **kwargs):
            launches.append((args, kwargs))
            return external

        adopted = ManagedMuseBridgeManager(
            stream_resolver=lambda: [FakeStream("MuseCC:DD", 256)],
            process_factory=launch,
            settings=settings(tmp_path),
        )
        owner = MuseOwner(kind="user", session_id=2)
        status = await adopted.connect(owner, MuseBleDevice("CC:DD", "Muse-A2"))
        assert status.state is MuseBridgeState.connected
        await adopted.release(owner)
        await adopted.shutdown()
        assert launches == []
        assert external.terminated == 0

    asyncio.run(scenario())


def test_bridge_keeps_only_the_last_hundred_diagnostic_lines(tmp_path):
    async def scenario():
        process = FakeProcess([f"diagnostic {index}" for index in range(101)] + ["BLE connected."])
        manager = ManagedMuseBridgeManager(
            stream_resolver=lambda: [], process_factory=lambda *args, **kwargs: process,
            settings=settings(tmp_path, muse_lsl_timeout_seconds=0.01),
        )
        await manager.connect(MuseOwner(kind="user", session_id=1), MuseBleDevice("AA:BB", "Muse-A1"))
        diagnostics = manager._diagnostics["AA:BB"]
        assert len(diagnostics) == 100
        assert diagnostics[0] == "diagnostic 2"
        assert diagnostics[-1] == "BLE connected."

    asyncio.run(scenario())


def test_overlapping_owners_wait_for_one_startup_result_and_fail_together(tmp_path):
    async def scenario():
        reader = LinesReader()
        process = FakeProcess()
        process.stdout = reader
        stream_ready = False

        def resolve():
            return [FakeStream("MuseAA:BB", 256)] if stream_ready else []

        manager = ManagedMuseBridgeManager(
            stream_resolver=resolve,
            process_factory=lambda *args, **kwargs: process,
            settings=settings(tmp_path),
        )
        first = MuseOwner(kind="user", session_id=1)
        second = MuseOwner(kind="user", session_id=1)
        one = asyncio.create_task(manager.connect(first, MuseBleDevice("AA:BB", "Muse-A1")))
        two = asyncio.create_task(manager.connect(second, MuseBleDevice("AA:BB", "Muse-A1")))
        await asyncio.sleep(0)
        assert not one.done() and not two.done()
        stream_ready = True
        reader._lines.put_nowait(b"BLE connected.\n")
        assert (await one).state is MuseBridgeState.connected
        assert (await two).state is MuseBridgeState.connected
        await manager.shutdown()

        failing = FakeProcess()
        manager = ManagedMuseBridgeManager(
            stream_resolver=lambda: [], process_factory=lambda *args, **kwargs: failing,
            settings=settings(tmp_path, muse_connect_timeout_seconds=0.01),
        )
        one = asyncio.create_task(manager.connect(first, MuseBleDevice("CC:DD", "Muse-A2")))
        two = asyncio.create_task(manager.connect(second, MuseBleDevice("CC:DD", "Muse-A2")))
        assert (await one).detail == "bluetooth_timeout"
        assert (await two).detail == "bluetooth_timeout"
        assert (await manager.status(second)).state is MuseBridgeState.failed

    asyncio.run(scenario())


def test_post_connection_process_exit_invalidates_status_and_releases_lease(tmp_path):
    async def scenario():
        process = FakeProcess(["BLE connected."])
        resolves = 0

        def resolve():
            nonlocal resolves
            resolves += 1
            return [] if resolves == 1 else [FakeStream("MuseAA:BB", 256)]

        manager = ManagedMuseBridgeManager(
            stream_resolver=resolve,
            process_factory=lambda *args, **kwargs: process,
            settings=settings(tmp_path),
        )
        owner = MuseOwner(kind="user", session_id=1)
        await manager.connect(owner, MuseBleDevice("AA:BB", "Muse-A1"))
        process.returncode = 1
        await asyncio.sleep(0)
        assert (await manager.status(owner)).detail == "bridge_exited"
        assert "AA:BB" not in manager._bridges
        await manager.shutdown()

    asyncio.run(scenario())


def test_lease_setup_error_is_translated_to_a_safe_bridge_status(tmp_path, monkeypatch):
    async def scenario():
        import app.services.muse_bridge_manager as module

        class BrokenLease:
            def __init__(self, *_args):
                raise OSError("C:/secret/operator/locks denied")

        monkeypatch.setattr(module, "DeviceLease", BrokenLease)
        manager = ManagedMuseBridgeManager(settings=settings(tmp_path))
        status = await manager.connect(MuseOwner(kind="user", session_id=1), MuseBleDevice("AA:BB", "Muse-A1"))
        assert (status.state, status.detail) == (MuseBridgeState.failed, "bridge_failed")

    asyncio.run(scenario())


def test_cleanup_waits_for_kill_and_releases_the_lease_when_termination_raises(tmp_path):
    async def scenario():
        class ResistantProcess(FakeProcess):
            def __init__(self):
                super().__init__(["BLE connected."])
                self.waits = 0

            async def wait(self):
                self.waits += 1
                if self.returncode is None:
                    await asyncio.Event().wait()
                return self.returncode

            def terminate(self):
                raise OSError("terminate denied")

            def kill(self):
                self.killed += 1
                self.returncode = 0

        process = ResistantProcess()
        resolves = 0

        def resolve():
            nonlocal resolves
            resolves += 1
            return [] if resolves == 1 else [FakeStream("MuseEE:FF", 256)]

        manager = ManagedMuseBridgeManager(
            stream_resolver=resolve,
            process_factory=lambda *args, **kwargs: process,
            settings=settings(tmp_path),
        )
        owner = MuseOwner(kind="user", session_id=1)
        await manager.connect(owner, MuseBleDevice("EE:FF", "Muse-A1"))
        assert "EE:FF" in manager._bridges
        bridge = manager._bridges["EE:FF"]
        await manager.release(owner)
        assert bridge.close_task is not None and bridge.close_task.done()
        assert process.killed == 1
        assert process.waits >= 2
        assert "EE:FF" not in manager._bridges

    asyncio.run(scenario())


def test_ble_marker_must_be_an_exact_line_and_shutdown_cancels_scans(tmp_path):
    async def scenario():
        process = FakeProcess(["prefix BLE connected."])
        manager = ManagedMuseBridgeManager(
            stream_resolver=lambda: [],
            process_factory=lambda *args, **kwargs: process,
            settings=settings(tmp_path, muse_connect_timeout_seconds=0.01),
        )
        status = await manager.connect(MuseOwner(kind="user", session_id=1), MuseBleDevice("AA:BB", "Muse-A1"))
        assert status.detail == "bluetooth_timeout"

        started = asyncio.Event()

        class Scanner:
            async def scan(self, *, timeout):
                started.set()
                await asyncio.Event().wait()

        manager = ManagedMuseBridgeManager(scanner=Scanner(), settings=settings(tmp_path))
        await manager.start_scan(1)
        await started.wait()
        await manager.shutdown()
        assert manager._scan_jobs == {}

    asyncio.run(scenario())


def test_last_owner_release_cleans_a_process_returned_by_a_delayed_factory(tmp_path):
    async def scenario():
        created = asyncio.Event()
        allow_creation = asyncio.Event()
        process = FakeProcess()

        async def launch(*args, **kwargs):
            created.set()
            try:
                await allow_creation.wait()
            except asyncio.CancelledError:
                return process
            return process

        manager = ManagedMuseBridgeManager(
            stream_resolver=lambda: [], process_factory=launch, settings=settings(tmp_path),
        )
        owner = MuseOwner(kind="user", session_id=1)
        connecting = asyncio.create_task(manager.connect(owner, MuseBleDevice("AA:BB", "Muse-A1")))
        await created.wait()
        await manager.release(owner)
        await asyncio.gather(connecting, return_exceptions=True)
        await asyncio.sleep(0)
        assert process.terminated == 1
        assert manager._bridges == {}
        assert manager._quarantined == {}

    asyncio.run(scenario())


def test_second_owner_gets_device_in_use_while_first_owner_connecting(tmp_path):
    async def scenario():
        reader = LinesReader()
        process = FakeProcess()
        process.stdout = reader

        manager = ManagedMuseBridgeManager(
            stream_resolver=lambda: [], process_factory=lambda *args, **kwargs: process, settings=settings(tmp_path),
        )
        first = MuseOwner(kind="user", session_id=1)
        second = MuseOwner(kind="collection", session_id=2)
        one = asyncio.create_task(manager.connect(first, MuseBleDevice("AA:BB", "Muse-A1")))
        await asyncio.sleep(0)

        # Second owner attempting to connect to same address while first is connecting receives device_in_use
        status2 = await manager.connect(second, MuseBleDevice("AA:BB", "Muse-A1"))
        assert status2.state is MuseBridgeState.failed
        assert status2.detail == "device_in_use"

        one.cancel()
        with __import__("pytest").raises(asyncio.CancelledError):
            await one
        await manager.shutdown()

    asyncio.run(scenario())


def test_one_output_drain_keeps_post_ble_diagnostics_bounded_while_lsl_waits(tmp_path):
    async def scenario():
        class CountingReader(LinesReader):
            def __init__(self):
                super().__init__(["BLE connected."] + [f"late {index}" for index in range(101)])
                self.reads = 0

            async def readline(self):
                result = await super().readline()
                self.reads += 1
                return result

        process = FakeProcess()
        reader = CountingReader()
        process.stdout = reader
        manager = ManagedMuseBridgeManager(
            stream_resolver=lambda: [FakeStream("MuseAA:BB", 256)] if reader.reads >= 102 else [],
            process_factory=lambda *args, **kwargs: process,
            settings=settings(tmp_path, muse_lsl_timeout_seconds=0.2),
        )
        owner = MuseOwner(kind="user", session_id=1)
        assert (await manager.connect(owner, MuseBleDevice("AA:BB", "Muse-A1"))).state is MuseBridgeState.connected
        diagnostics = manager._bridges["AA:BB"].diagnostics
        assert len(diagnostics) == 100
        assert diagnostics[-1] == "late 100"
        await manager.shutdown()

    asyncio.run(scenario())


def test_failed_kill_quarantines_the_lease_and_blocks_another_bridge(tmp_path):
    async def scenario():
        class UnkillableProcess(FakeProcess):
            def __init__(self, lines):
                super().__init__(lines)
                self.exited = asyncio.Event()

            async def wait(self):
                await self.exited.wait()
                return self.returncode

            def terminate(self):
                return None

            def kill(self):
                raise OSError("kill denied")

        process = UnkillableProcess(["BLE connected."])
        resolves = 0

        def resolve():
            nonlocal resolves
            resolves += 1
            return [] if resolves == 1 else [FakeStream("MuseAA:BB", 256)]

        manager = ManagedMuseBridgeManager(
            stream_resolver=resolve, process_factory=lambda *args, **kwargs: process, settings=settings(tmp_path),
        )
        owner = MuseOwner(kind="user", session_id=1)
        await manager.connect(owner, MuseBleDevice("AA:BB", "Muse-A1"))
        await manager.release(owner)
        replacement = ManagedMuseBridgeManager(
            stream_resolver=lambda: [FakeStream("MuseAA:BB", 256)], settings=settings(tmp_path),
        )
        status = await replacement.connect(MuseOwner(kind="user", session_id=2), MuseBleDevice("AA:BB", "Muse-A1"))
        assert status.detail == "device_in_use"
        bridge = manager._quarantined["AA:BB"]
        process.returncode = 0
        process.exited.set()
        await bridge.reaper_task
        assert manager._quarantined == {}
        assert bridge.lease._acquired is False

    asyncio.run(scenario())


def test_cancelled_connect_waits_for_delayed_factory_cleanup_before_returning(tmp_path):
    async def scenario():
        created = asyncio.Event()
        process = FakeProcess()

        async def launch(*args, **kwargs):
            created.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                return process

        manager = ManagedMuseBridgeManager(
            stream_resolver=lambda: [], process_factory=launch, settings=settings(tmp_path),
        )
        task = asyncio.create_task(manager.connect(MuseOwner(kind="user", session_id=1), MuseBleDevice("AA:BB", "Muse-A1")))
        await created.wait()
        task.cancel()
        with __import__("pytest").raises(asyncio.CancelledError):
            await task
        assert process.terminated == 1
        assert manager._bridges == {}
        assert manager._quarantined == {}

    asyncio.run(scenario())


def test_late_unkillable_factory_result_quarantines_then_reaps_its_lease(tmp_path):
    async def scenario():
        created = asyncio.Event()

        class Process(FakeProcess):
            def __init__(self):
                super().__init__()
                self.exited = asyncio.Event()

            async def wait(self):
                await self.exited.wait()
                return self.returncode

            def terminate(self):
                return None

            def kill(self):
                raise OSError("kill denied")

        process = Process()

        async def launch(*args, **kwargs):
            created.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                return process

        manager = ManagedMuseBridgeManager(
            stream_resolver=lambda: [], process_factory=launch, settings=settings(tmp_path),
        )
        owner = MuseOwner(kind="user", session_id=1)
        task = asyncio.create_task(manager.connect(owner, MuseBleDevice("AA:BB", "Muse-A1")))
        await created.wait()
        await manager.release(owner)
        await asyncio.gather(task, return_exceptions=True)
        bridge = manager._quarantined["AA:BB"]
        assert bridge.lease._acquired is True
        assert bridge.reaper_task is not None and not bridge.reaper_task.done()
        process.returncode = 0
        process.exited.set()
        await bridge.reaper_task
        assert manager._quarantined == {}
        assert bridge.lease._acquired is False

    asyncio.run(scenario())


def test_shutdown_keeps_an_existing_quarantine_reaper_alive_until_late_exit(tmp_path):
    async def scenario():
        class Process(FakeProcess):
            def __init__(self):
                super().__init__(["BLE connected."])
                self.exited = asyncio.Event()

            async def wait(self):
                await self.exited.wait()
                return self.returncode

            def terminate(self):
                return None

            def kill(self):
                raise OSError("kill denied")

        process = Process()
        calls = 0

        def resolve():
            nonlocal calls
            calls += 1
            return [] if calls == 1 else [FakeStream("MuseAA:BB", 256)]

        manager = ManagedMuseBridgeManager(
            stream_resolver=resolve, process_factory=lambda *args, **kwargs: process, settings=settings(tmp_path),
        )
        owner = MuseOwner(kind="user", session_id=1)
        await manager.connect(owner, MuseBleDevice("AA:BB", "Muse-A1"))
        await manager.release(owner)
        bridge = manager._quarantined["AA:BB"]
        manager._cleanup_timeout = 0.01
        await manager.shutdown()
        assert bridge.reaper_task is not None and not bridge.reaper_task.cancelled()
        process.returncode = 0
        process.exited.set()
        await bridge.reaper_task
        assert manager._quarantined == {}
        assert bridge.lease._acquired is False

    asyncio.run(scenario())


def test_shutdown_observes_a_quarantine_reaper_created_by_close_cleanup(tmp_path):
    async def scenario():
        class Process(FakeProcess):
            def __init__(self):
                super().__init__(["BLE connected."])
                self.exited = asyncio.Event()

            async def wait(self):
                await self.exited.wait()
                return self.returncode

            def terminate(self):
                return None

            def kill(self):
                raise OSError("kill denied")

        process = Process()
        calls = 0

        def resolve():
            nonlocal calls
            calls += 1
            return [] if calls == 1 else [FakeStream("MuseCC:DD", 256)]

        manager = ManagedMuseBridgeManager(
            stream_resolver=resolve, process_factory=lambda *args, **kwargs: process, settings=settings(tmp_path),
        )
        await manager.connect(MuseOwner(kind="user", session_id=1), MuseBleDevice("CC:DD", "Muse-A1"))
        await manager.shutdown()
        bridge = manager._quarantined["CC:DD"]
        assert bridge.reaper_task is not None and not bridge.reaper_task.cancelled()
        process.returncode = 0
        process.exited.set()
        await bridge.reaper_task
        assert manager._quarantined == {}
        assert bridge.lease._acquired is False

    asyncio.run(scenario())


def test_scan_registry_never_exceeds_its_declared_bound(tmp_path):
    async def scenario():
        class Scanner:
            async def scan(self, *, timeout):
                return []

        manager = ManagedMuseBridgeManager(scanner=Scanner(), settings=settings(tmp_path))
        for actor_id in range(manager._MAX_SCAN_JOBS + 5):
            await manager.start_scan(actor_id)
            await asyncio.sleep(0)
        assert len(manager._scan_jobs) <= manager._MAX_SCAN_JOBS

    asyncio.run(scenario())
