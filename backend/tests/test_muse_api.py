from __future__ import annotations

import asyncio
from datetime import datetime
from types import SimpleNamespace

import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models.dataset_collection import CollectionSession, CollectionSessionState, DatasetParticipant
from app.models.eeg import EEGSession
from app.models.user import Role, User
from app.schemas.muse import MuseBridgeState, MuseConnectionStatus, MuseOwner, MuseScanStatus
from app.services.auth_service import create_access_token
from app.services.eeg_service import EEGStateMachine, Phase, SessionState
from app.services.muse_stream import MuseSample
from app.services.raw_eeg_writer import EEGSample
from app.services.signal_processor import SensorQuality


@pytest.fixture
def client(monkeypatch):
    from app.routers import dataset_collection, eeg_session, muse

    eeg_session._active_machines.clear()
    eeg_session._pending_muse_devices.clear()
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as db:
        user_role, admin_role = Role(name="user"), Role(name="admin")
        db.add_all((user_role, admin_role))
        db.flush()
        owner = User(username="owner", email="owner@example.com", password_hash="x", role_id=user_role.id)
        other = User(username="other", email="other@example.com", password_hash="x", role_id=user_role.id)
        admin = User(username="admin", email="admin@example.com", password_hash="x", role_id=admin_role.id)
        db.add_all((owner, other, admin))
        db.flush()
        ordinary_session = EEGSession(user_id=owner.id)
        other_session = EEGSession(user_id=other.id)
        participant = DatasetParticipant(
            participant_code="P001", consent_confirmed_at=datetime(2026, 7, 27), state="active"
        )
        db.add_all((ordinary_session, other_session, participant))
        db.flush()
        collection = CollectionSession(participant_id=participant.id, device_id="AA:BB", device_name="Muse")
        terminal_collection = CollectionSession(
            participant_id=participant.id,
            device_id="CC:DD",
            device_name="Muse",
            state=CollectionSessionState.completed,
        )
        db.add_all((collection, terminal_collection))
        db.commit()
        ids = SimpleNamespace(
            ordinary=ordinary_session.id,
            other=other_session.id,
            collection=collection.id,
            terminal=terminal_collection.id,
        )
        tokens = SimpleNamespace(
            owner=create_access_token(owner.id, "user"),
            other=create_access_token(other.id, "user"),
            admin=create_access_token(admin.id, "admin"),
        )

    def override_db():
        with factory() as db:
            yield db

    app = FastAPI()
    app.include_router(muse.router, prefix="/api/v1")
    app.include_router(eeg_session.router, prefix="/api/v1")
    app.include_router(dataset_collection.router, prefix="/api/v1")
    app.dependency_overrides[get_db] = override_db
    app.state.ids, app.state.tokens = ids, tokens
    with TestClient(app) as test_client:
        yield test_client
    eeg_session._active_machines.clear()
    eeg_session._pending_muse_devices.clear()
    engine.dispose()


def _headers(client, actor):
    return {"Authorization": f"Bearer {getattr(client.app.state.tokens, actor)}"}


def test_scan_is_owned_and_reports_scanning_before_completion(client, monkeypatch):
    from app.routers import muse

    class Bridge:
        actor_id = None

        async def start_scan(self, actor_id):
            assert actor_id > 0
            self.actor_id = actor_id
            return MuseScanStatus(scan_id="scan-1", state=MuseBridgeState.scanning)

        async def get_scan(self, actor_id, scan_id):
            if scan_id in {"unknown", "expired"} or actor_id != self.actor_id or scan_id != "scan-1":
                raise LookupError("Muse scan is unavailable")
            return MuseScanStatus(scan_id=scan_id, state=MuseBridgeState.found)

    bridge = Bridge()
    monkeypatch.setattr(muse, "managed_muse_bridge_manager", bridge)
    response = client.post("/api/v1/muse/scans", headers=_headers(client, "owner"))
    assert response.status_code == 202
    assert response.json() == {"scan_id": "scan-1", "state": "scanning", "devices": [], "detail": None}
    assert client.get("/api/v1/muse/scans/scan-1", headers=_headers(client, "owner")).json()["state"] == "found"
    assert client.get("/api/v1/muse/scans/unknown", headers=_headers(client, "owner")).status_code == 404
    assert client.get("/api/v1/muse/scans/expired", headers=_headers(client, "owner")).status_code == 404
    assert client.get("/api/v1/muse/scans/scan-1", headers=_headers(client, "other")).status_code == 404


def test_user_muse_route_owns_ordinary_session_and_waits_for_verified_bridge(client, monkeypatch):
    from app.routers import eeg_session, muse

    started = []

    class Runner:
        async def start(self, session_id, machine, bridge_status):
            started.append((session_id, machine.state.phase, bridge_status.state))

        async def stop(self, session_id):
            started.append((session_id, "stopped"))

    class Bridge:
        async def connect(self, owner, device):
            return MuseConnectionStatus(owner=owner, state=MuseBridgeState.waiting_for_lsl)

        async def status(self, owner):
            return MuseConnectionStatus(owner=owner, state=MuseBridgeState.waiting_for_lsl)

        async def release(self, owner):
            return MuseConnectionStatus(owner=owner, state=MuseBridgeState.idle)

    monkeypatch.setattr(muse, "managed_muse_bridge_manager", Bridge())
    monkeypatch.setattr(eeg_session, "managed_muse_bridge_manager", Bridge())
    monkeypatch.setattr(eeg_session, "user_eeg_stream_runner", Runner())
    session_id = client.app.state.ids.ordinary
    other_id = client.app.state.ids.other
    response = client.post(
        f"/api/v1/sessions/{session_id}/muse",
        headers=_headers(client, "owner"),
        json={"address": "AA:BB", "name": "Muse"},
    )
    assert response.status_code == 200
    assert response.json()["state"] == "waiting_for_lsl"
    assert started == []
    assert client.get(f"/api/v1/sessions/{other_id}/muse", headers=_headers(client, "owner")).status_code == 404
    assert client.post(f"/api/v1/sessions/{session_id}/muse", headers=_headers(client, "admin"), json={"address": "AA", "name": "Muse"}).status_code == 403


def test_user_muse_poll_promotes_waiting_bridge_once_with_selected_device(client, monkeypatch):
    from app.routers import eeg_session

    starts = []

    class Runner:
        async def start(self, session_id, machine, bridge_status):
            starts.append((session_id, machine.state.device_id, machine.state.device_name, bridge_status.state))

    class Bridge:
        async def connect(self, owner, device):
            return MuseConnectionStatus(owner=owner, state=MuseBridgeState.waiting_for_lsl)

        async def status(self, owner):
            return MuseConnectionStatus(owner=owner, state=MuseBridgeState.connected)

    monkeypatch.setattr(eeg_session, "managed_muse_bridge_manager", Bridge())
    monkeypatch.setattr(eeg_session, "user_eeg_stream_runner", Runner())
    session_id = client.app.state.ids.ordinary

    assert client.post(
        f"/api/v1/sessions/{session_id}/muse",
        headers=_headers(client, "owner"),
        json={"address": "AA:BB", "name": "Selected Muse"},
    ).json()["state"] == "waiting_for_lsl"
    assert client.get(f"/api/v1/sessions/{session_id}/muse", headers=_headers(client, "owner")).json()["state"] == "connected"
    assert client.get(f"/api/v1/sessions/{session_id}/muse", headers=_headers(client, "owner")).json()["state"] == "connected"
    assert starts == [(session_id, "AA:BB", "Selected Muse", MuseBridgeState.connected)]


@pytest.mark.parametrize("bridge_state", [MuseBridgeState.starting_bridge, MuseBridgeState.connecting_bluetooth])
def test_user_muse_intermediate_bridge_states_never_activate_runner(client, monkeypatch, bridge_state):
    from app.routers import eeg_session

    starts = []

    class Runner:
        async def start(self, *_args):
            starts.append(True)

    class Bridge:
        async def connect(self, owner, device):
            return MuseConnectionStatus(owner=owner, state=bridge_state)

    monkeypatch.setattr(eeg_session, "managed_muse_bridge_manager", Bridge())
    monkeypatch.setattr(eeg_session, "user_eeg_stream_runner", Runner())
    session_id = client.app.state.ids.ordinary
    response = client.post(
        f"/api/v1/sessions/{session_id}/muse",
        headers=_headers(client, "owner"),
        json={"address": "AA:BB", "name": "Muse"},
    )
    assert response.json()["state"] == bridge_state.value
    assert starts == []


def test_user_muse_connect_is_idempotent_and_disconnects(client, monkeypatch):
    from app.routers import eeg_session, muse

    calls = []
    events = []

    class Runner:
        async def start(self, session_id, machine, bridge_status):
            calls.append(("start", session_id, machine.state.phase))

        async def stop(self, session_id):
            calls.append(("stop", session_id))
            events.append(("stop", session_id))

    class Bridge:
        async def connect(self, owner, device):
            return MuseConnectionStatus(owner=owner, state=MuseBridgeState.connected)

        async def status(self, owner):
            return MuseConnectionStatus(owner=owner, state=MuseBridgeState.connected)

        async def release(self, owner):
            calls.append(("release", owner.session_id))
            events.append(("release", owner.session_id))
            return MuseConnectionStatus(owner=owner, state=MuseBridgeState.idle)

    monkeypatch.setattr(muse, "managed_muse_bridge_manager", Bridge())
    monkeypatch.setattr(eeg_session, "managed_muse_bridge_manager", Bridge())
    monkeypatch.setattr(eeg_session, "user_eeg_stream_runner", Runner())

    async def broadcast(session_id, payload):
        events.append(("broadcast", session_id, payload))

    monkeypatch.setattr(eeg_session.eeg_manager, "broadcast", broadcast)
    session_id = client.app.state.ids.ordinary
    for _ in range(2):
        assert client.post(f"/api/v1/sessions/{session_id}/muse", headers=_headers(client, "owner"), json={"address": "AA", "name": "Muse"}).status_code == 200
    assert calls == [("start", session_id, Phase.PREPARATION)]
    assert client.delete(f"/api/v1/sessions/{session_id}/muse", headers=_headers(client, "owner")).status_code == 200
    assert calls[-2:] == [("stop", session_id), ("release", session_id)]
    assert eeg_session._active_machines[str(session_id)].state.phase is Phase.DISCONNECTED
    assert events[-3][0:2] == ("stop", session_id)
    assert events[-2][0:2] == ("broadcast", str(session_id))
    assert events[-2][2]["session_id"] == str(session_id)
    assert events[-2][2]["phase"] == "DISCONNECTED"
    assert events[-2][2]["device_state"] == "disconnected"
    assert events[-1] == ("release", session_id)


def test_completion_stops_runner_and_releases_user_bridge(client, monkeypatch):
    from app.routers import eeg_session

    calls = []

    class Runner:
        async def stop(self, session_id):
            calls.append(("stop", session_id))

    class Bridge:
        async def release(self, owner):
            calls.append(("release", owner.session_id))
            return MuseConnectionStatus(owner=owner, state=MuseBridgeState.idle)

    session_id = client.app.state.ids.ordinary
    machine = EEGStateMachine(SessionState(session_id=str(session_id), user_id=1))
    machine.transition_to(Phase.EMOTION_CONFIRMATION)
    monkeypatch.setitem(eeg_session._active_machines, str(session_id), machine)
    monkeypatch.setattr(eeg_session, "user_eeg_stream_runner", Runner())
    monkeypatch.setattr(eeg_session, "managed_muse_bridge_manager", Bridge())

    response = client.post(f"/api/v1/sessions/{session_id}/confirm-emotion", headers=_headers(client, "owner"))
    assert response.status_code == 200
    assert calls == [("stop", session_id), ("release", session_id)]


def test_cancellation_stops_runner_and_releases_user_bridge(client, monkeypatch):
    from app.routers import eeg_session

    calls = []

    class Runner:
        async def stop(self, session_id):
            calls.append(("stop", session_id))

    class Bridge:
        async def release(self, owner):
            calls.append(("release", owner.session_id))
            return MuseConnectionStatus(owner=owner, state=MuseBridgeState.idle)

    session_id = client.app.state.ids.ordinary
    monkeypatch.setitem(eeg_session._active_machines, str(session_id), EEGStateMachine(SessionState(session_id=str(session_id), user_id=1)))
    monkeypatch.setattr(eeg_session, "user_eeg_stream_runner", Runner())
    monkeypatch.setattr(eeg_session, "managed_muse_bridge_manager", Bridge())

    response = client.post(f"/api/v1/sessions/{session_id}/cancel", headers=_headers(client, "owner"))
    assert response.status_code == 200
    assert calls == [("stop", session_id), ("release", session_id)]


def test_other_user_cannot_complete_an_ordinary_session(client, monkeypatch):
    from app.routers import eeg_session

    session_id = client.app.state.ids.ordinary
    machine = EEGStateMachine(SessionState(session_id=str(session_id), user_id=1))
    machine.transition_to(Phase.EMOTION_CONFIRMATION)
    monkeypatch.setitem(eeg_session._active_machines, str(session_id), machine)

    response = client.post(f"/api/v1/sessions/{session_id}/confirm-emotion", headers=_headers(client, "other"))
    assert response.status_code == 404


def test_admin_collection_muse_is_admin_only_and_never_starts_terminal_bridge(client, monkeypatch):
    from app.routers import dataset_collection, muse

    connect_calls = []

    class Bridge:
        async def connect(self, owner, device):
            connect_calls.append((owner, device.address))
            return MuseConnectionStatus(owner=owner, state=MuseBridgeState.connected)

        async def status(self, owner):
            return MuseConnectionStatus(owner=owner, state=MuseBridgeState.idle)

        async def release(self, owner):
            return MuseConnectionStatus(owner=owner, state=MuseBridgeState.idle)

    monkeypatch.setattr(muse, "managed_muse_bridge_manager", Bridge())
    monkeypatch.setattr(dataset_collection, "managed_muse_bridge_manager", Bridge())
    session_id = client.app.state.ids.collection
    device = {"address": "AA:BB", "name": "Selected Muse"}
    assert client.post(f"/api/v1/admin/dataset-collection/sessions/{session_id}/muse", headers=_headers(client, "owner"), json=device).status_code == 403
    assert client.post(f"/api/v1/admin/dataset-collection/sessions/{session_id}/muse", headers=_headers(client, "admin"), json=device).status_code == 200
    assert [address for _, address in connect_calls] == ["AA:BB"]
    terminal = client.app.state.ids.terminal
    response = client.post(f"/api/v1/admin/dataset-collection/sessions/{terminal}/muse", headers=_headers(client, "admin"), json=device)
    assert response.status_code == 409
    assert len(connect_calls) == 1


def test_admin_connects_discovered_muse_for_fresh_session_without_pre_persisting_it(client, monkeypatch):
    from app.routers import dataset_collection

    connected = []

    class Bridge:
        async def connect(self, owner, device):
            connected.append((owner.kind, owner.session_id, device.address, device.name))
            return MuseConnectionStatus(owner=owner, state=MuseBridgeState.connected)

    monkeypatch.setattr(dataset_collection, "managed_muse_bridge_manager", Bridge())
    participant = client.post(
        "/api/v1/admin/dataset-collection/participants",
        headers=_headers(client, "admin"),
        json={"consent_confirmed_at": "2026-07-29T00:00:00Z"},
    ).json()
    created = client.post(
        "/api/v1/admin/dataset-collection/sessions",
        headers=_headers(client, "admin"),
        json={"participant_id": participant["id"]},
    )
    assert created.status_code == 201
    session = created.json()
    assert session["device_id"] is None

    response = client.post(
        f"/api/v1/admin/dataset-collection/sessions/{session['id']}/muse",
        headers=_headers(client, "admin"),
        json={"address": "11:22:33:44", "name": "Fresh Muse"},
    )

    assert response.status_code == 200
    assert connected == [("collection", session["id"], "11:22:33:44", "Fresh Muse")]
    assert client.get("/api/v1/admin/dataset-collection/sessions", headers=_headers(client, "admin")).json()["items"][-1]["device_id"] is None


def test_admin_muse_delete_stops_collection_source_and_returns_truthful_state(client, monkeypatch):
    from app.routers import dataset_collection

    calls = []

    class Bridge:
        async def status(self, owner):
            calls.append(("status", owner.session_id))
            return MuseConnectionStatus(owner=owner, state=MuseBridgeState.idle)

    async def stop_source(session_id):
        calls.append(("stop_source", session_id))

    monkeypatch.setattr(dataset_collection, "managed_muse_bridge_manager", Bridge())
    monkeypatch.setattr(dataset_collection.collection_manager, "stop_source", stop_source)
    session_id = client.app.state.ids.collection
    response = client.delete(
        f"/api/v1/admin/dataset-collection/sessions/{session_id}/muse",
        headers=_headers(client, "admin"),
    )
    assert response.json()["state"] == "idle"
    assert calls == [("stop_source", session_id), ("status", session_id)]


def test_failed_user_and_admin_connections_expose_only_safe_failure_detail(client, monkeypatch):
    from app.routers import dataset_collection, eeg_session

    class Bridge:
        async def connect(self, owner, device):
            return MuseConnectionStatus(owner=owner, state=MuseBridgeState.failed, detail="bridge_failed")

    bridge = Bridge()
    monkeypatch.setattr(eeg_session, "managed_muse_bridge_manager", bridge)
    monkeypatch.setattr(dataset_collection, "managed_muse_bridge_manager", bridge)
    ordinary = client.app.state.ids.ordinary
    collection = client.app.state.ids.collection
    user_response = client.post(
        f"/api/v1/sessions/{ordinary}/muse",
        headers=_headers(client, "owner"),
        json={"address": "private-address", "name": "Muse"},
    )
    admin_response = client.post(
        f"/api/v1/admin/dataset-collection/sessions/{collection}/muse",
        headers=_headers(client, "admin"),
        json={"address": "private-address", "name": "Muse"},
    )
    assert user_response.json()["detail"] == "bridge_failed"
    assert admin_response.json()["detail"] == "bridge_failed"
    assert "private-address" not in user_response.text


def test_user_runner_maps_muse_samples_and_marks_disconnect(monkeypatch):
    from app.services import eeg_stream_runner

    broadcasts = []
    disconnected = asyncio.Event()
    machine = EEGStateMachine(SessionState(session_id="7", user_id=1))
    machine.confirm_device("Muse", "AA")
    machine.mark_connected()
    ingested = []
    machine.ingest_samples = lambda values, timestamps, **kwargs: ingested.append((values, timestamps))

    sample = MuseSample(
        sample=EEGSample(
            timestamp=123.5,
            tp9=1.0,
            af7=2.0,
            af8=3.0,
            tp10=4.0,
            tp9_quality=100.0,
            af7_quality=100.0,
            af8_quality=100.0,
            tp10_quality=100.0,
        ),
        sensor_timestamps={"tp9": 123.5, "af7": 123.5, "af8": 123.5, "tp10": 123.5},
        sensors={key: SensorQuality(state="good", quality_score=100.0, timestamp=123.5) for key in ("tp9", "af7", "af8", "tp10")},
        sampling_rate_hz=256.0,
        sampling_rate_ok=True,
    )

    class Source:
        async def connect(self, device_id):
            assert device_id == "AA"

        async def disconnect(self):
            disconnected.set()

        async def samples(self):
            yield sample

    async def broadcast(session_id, payload):
        broadcasts.append((session_id, payload))

    monkeypatch.setattr(eeg_stream_runner.eeg_manager, "broadcast", broadcast)

    async def scenario():
        runner = eeg_stream_runner.UserEEGStreamRunner(source_factory=Source)
        await runner.start(7, machine, SimpleNamespace(state=MuseBridgeState.connected))
        await asyncio.sleep(0)
        assert ingested[0][0].tolist() == [[1.0, 2.0, 3.0, 4.0]]
        assert ingested[0][1].tolist() == [123.5]
        assert machine.state.phase is Phase.DISCONNECTED
        assert broadcasts[-1][0] == "7"
        assert disconnected.is_set()

    asyncio.run(scenario())


def test_user_runner_stop_and_shutdown_cancel_active_pumps():
    from app.services.eeg_stream_runner import UserEEGStreamRunner

    connected = asyncio.Event()
    sources = []

    class Source:
        def __init__(self):
            self.disconnected = 0
            sources.append(self)

        async def connect(self, _device_id):
            connected.set()

        async def disconnect(self):
            self.disconnected += 1

        async def samples(self):
            await asyncio.Event().wait()
            yield None

    async def scenario():
        runner = UserEEGStreamRunner(source_factory=Source)
        first = EEGStateMachine(SessionState(session_id="7", user_id=1, device_id="AA"))
        await runner.start(7, first, SimpleNamespace(state=MuseBridgeState.connected))
        await asyncio.wait_for(connected.wait(), timeout=0.5)
        await runner.stop(7)
        assert 7 not in runner._tasks
        assert sources[0].disconnected >= 1

        second = EEGStateMachine(SessionState(session_id="8", user_id=1, device_id="BB"))
        await runner.start(8, second, SimpleNamespace(state=MuseBridgeState.connected))
        await runner.shutdown()
        assert runner._tasks == {}
        assert sources[1].disconnected >= 1

    asyncio.run(scenario())


def test_lifespan_attempts_both_cleanups_when_application_raises(monkeypatch):
    from app import main

    cleanups = []

    async def stop_user_runner():
        cleanups.append("user")

    async def stop_bridge_manager():
        cleanups.append("bridge")

    monkeypatch.setattr(main.Base.metadata, "create_all", lambda **_kwargs: None)
    monkeypatch.setattr(main, "_seed_roles", lambda: None)
    monkeypatch.setattr(main.os, "makedirs", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(main.user_eeg_stream_runner, "shutdown", stop_user_runner)
    monkeypatch.setattr(main.managed_muse_bridge_manager, "shutdown", stop_bridge_manager)

    async def scenario():
        with pytest.raises(RuntimeError, match="application failed"):
            async with main.lifespan(FastAPI()):
                raise RuntimeError("application failed")

    asyncio.run(scenario())
    assert cleanups == ["user", "bridge"]


def test_lifespan_attempts_bridge_cleanup_after_runner_cleanup_failure(monkeypatch):
    from app import main

    cleanups = []

    async def failing_runner_cleanup():
        cleanups.append("user")
        raise RuntimeError("runner cleanup failed")

    async def bridge_cleanup():
        cleanups.append("bridge")

    monkeypatch.setattr(main.Base.metadata, "create_all", lambda **_kwargs: None)
    monkeypatch.setattr(main, "_seed_roles", lambda: None)
    monkeypatch.setattr(main.os, "makedirs", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(main.user_eeg_stream_runner, "shutdown", failing_runner_cleanup)
    monkeypatch.setattr(main.managed_muse_bridge_manager, "shutdown", bridge_cleanup)

    async def scenario():
        async with main.lifespan(FastAPI()):
            pass

    asyncio.run(scenario())
    assert cleanups == ["user", "bridge"]


def test_lifespan_runs_bridge_cleanup_after_runner_cancellation_then_reraises(monkeypatch):
    from app import main

    cleanups = []

    async def cancelled_runner_cleanup():
        cleanups.append("user")
        raise asyncio.CancelledError()

    async def bridge_cleanup():
        cleanups.append("bridge")

    monkeypatch.setattr(main.Base.metadata, "create_all", lambda **_kwargs: None)
    monkeypatch.setattr(main, "_seed_roles", lambda: None)
    monkeypatch.setattr(main.os, "makedirs", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(main.user_eeg_stream_runner, "shutdown", cancelled_runner_cleanup)
    monkeypatch.setattr(main.managed_muse_bridge_manager, "shutdown", bridge_cleanup)

    async def scenario():
        with pytest.raises(asyncio.CancelledError):
            async with main.lifespan(FastAPI()):
                pass

    asyncio.run(scenario())
    assert cleanups == ["user", "bridge"]
