from __future__ import annotations

import asyncio
import hashlib
import importlib
import threading
import time
from datetime import datetime
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.websockets import WebSocketDisconnect

from app.config import Settings
from app.database import Base, get_db
from app.models.dataset_collection import (
    CollectionSession,
    CollectionSessionState,
    CollectionTrial,
    DatasetParticipant,
    EmotionStimulus,
    Quadrant,
    StimulusApprovalState,
    TrialState,
)
from app.models.user import Role, User
from app.routers import dataset_collection
from app.services.auth_service import create_access_token
from app.services.collection_state_machine import CollectionRunnerState
from app.services.muse_stream import LSLMuseStreamSource, MuseDevice, MuseStreamError
from app.services.raw_eeg_writer import EEGSample
from app.services.signal_processor import SensorQuality
from app.ws.collection_manager import CollectionConnectionManager


BASE = "/api/v1/admin/dataset-collection"


@pytest.fixture
def client(tmp_path, monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    media_root = tmp_path / "media"
    media_root.mkdir()

    with factory() as db:
        user_role, admin_role = Role(name="user"), Role(name="admin")
        db.add_all([user_role, admin_role])
        db.flush()
        user = User(username="user2", email="user2@example.com", password_hash="x", role_id=user_role.id)
        admin = User(username="admin2", email="admin2@example.com", password_hash="x", role_id=admin_role.id)
        db.add_all([user, admin])
        db.flush()
        participant = DatasetParticipant(
            participant_code="P001", consent_confirmed_at=datetime(2026, 7, 19), state="active"
        )
        db.add(participant)
        db.flush()
        collection_session = CollectionSession(participant_id=participant.id)
        db.add(collection_session)
        db.flush()
        stimulus = EmotionStimulus(
            title="Safe clip",
            file_path="safe.mp4",
            checksum="0" * 64,
            duration_seconds=45,
            target_quadrant=Quadrant.positive_low,
            approval_state=StimulusApprovalState.approved,
            stimulus_set_version="v1",
        )
        db.add(stimulus)
        db.commit()
        ids = (collection_session.id, stimulus.id)
        tokens = (create_access_token(admin.id, "admin"), create_access_token(user.id, "user"))

    def override_db():
        with factory() as db:
            yield db

    app = FastAPI()
    app.include_router(dataset_collection.router, prefix="/api/v1")
    app.dependency_overrides[get_db] = override_db
    app.state.collection_settings = Settings(
        database_url="sqlite://", collection_raw_dir=str(tmp_path / "raw"), collection_stimulus_dir=str(media_root)
    )
    monkeypatch.setattr(dataset_collection, "get_settings", lambda: app.state.collection_settings)
    app.state.factory = factory
    app.state.ids = ids
    app.state.admin_token, app.state.user_token = tokens
    with TestClient(app) as test_client:
        yield test_client
    engine.dispose()


def auth(client, role="admin"):
    token = client.app.state.admin_token if role == "admin" else client.app.state.user_token
    return {"Authorization": f"Bearer {token}"}


def test_lsl_adapter_maps_exact_muse_channels_and_rejects_stale_samples():
    clock = [9.0]
    source = LSLMuseStreamSource(clock=lambda: clock[0], stale_after_seconds=2.0)
    source._channel_names = ("AF8", "TP10", "TP9", "AF7")
    for index in range(16):
        clock[0] = 9.0 + index / 256
        mapped = source.map_sample(
            [35.0 * ((index % 4) - 1.5), 30.0 * ((index % 4) - 1.5), 32.0 * ((index % 4) - 1.5), 34.0 * ((index % 4) - 1.5)],
            timestamp=clock[0],
        )
    assert (mapped.sample.tp9, mapped.sample.af7, mapped.sample.af8, mapped.sample.tp10) == (48, 51, 52.5, 45)
    assert set(mapped.sensor_timestamps) == {"tp9", "af7", "af8", "tp10"}
    assert set(mapped.sensor_timestamps.values()) == {mapped.sample.timestamp}
    assert mapped.sample.tp9_quality != 100.0
    assert mapped.sampling_rate_ok is True
    assert all(sensor.state == "good" for sensor in mapped.sensors.values())

    clock[0] += 3
    stale = source.map_sample([3.0, 4.0, 1.0, 2.0], timestamp=clock[0] - 3)
    assert stale.capture_eligible is False
    assert all(sensor.state == "stale" for sensor in stale.sensors.values())


def test_lsl_adapter_enforces_configured_256_hz_tolerance_deterministically():
    clock = [100.0]
    source = LSLMuseStreamSource(
        clock=lambda: clock[0], expected_sampling_rate_hz=256, sampling_tolerance_hz=8,
    )
    source._channel_names = ("TP9", "AF7", "AF8", "TP10")

    for index in range(16):
        clock[0] = 100.0 + index / 240
        mapped = source.map_sample([20 + index % 4, 25 + index % 4, 30 + index % 4, 35 + index % 4], clock[0])

    assert mapped.sampling_rate_hz == pytest.approx(240.0)
    assert mapped.sampling_rate_ok is False
    assert mapped.capture_eligible is True
    assert all(sensor.state == "poor" for sensor in mapped.sensors.values())


def test_lsl_adapter_emits_one_stale_quality_observation_when_samples_stop():
    clock = [50.0]
    source = LSLMuseStreamSource(clock=lambda: clock[0], stale_after_seconds=2)
    source._channel_names = ("TP9", "AF7", "AF8", "TP10")
    source.map_sample([1, 2, 3, 4], 50.0)
    clock[0] = 52.1

    stale = source.stale_observation()

    assert stale is not None and stale.capture_eligible is False
    assert all(sensor.state == "stale" for sensor in stale.sensors.values())
    assert source.stale_observation() is None


def test_lsl_adapter_ignores_aux_but_keeps_exact_four_channel_mapping():
    source = LSLMuseStreamSource(clock=lambda: 10.0)
    source._channel_names = ("TP9", "AF7", "AF8", "TP10", "AUX")
    mapped = source.map_sample([1.0, 2.0, 3.0, 4.0, 999.0], timestamp=10.0)
    assert (mapped.sample.tp9, mapped.sample.af7, mapped.sample.af8, mapped.sample.tp10) == (1, 2, 3, 4)


def test_lsl_adapter_discovery_failure_is_bounded_and_safe(monkeypatch):
    source = LSLMuseStreamSource(discovery_timeout=0.01)
    monkeypatch.setattr(source, "_resolve_streams", lambda: [])
    assert asyncio.run(source.discover()) == []
    with pytest.raises(MuseStreamError, match="not found"):
        asyncio.run(source.connect("missing"))


def test_runner_state_and_commands_are_admin_only_and_validate_trial_session(client, monkeypatch):
    session_id, stimulus_id = client.app.state.ids
    assert client.get(f"{BASE}/sessions/{session_id}/runner-state").status_code == 401
    assert client.get(f"{BASE}/sessions/{session_id}/runner-state", headers=auth(client, "user")).status_code == 403

    class FakeRunner:
        def __init__(self, db):
            self.db = db

        def state(self):
            return type("State", (), dict(
                session_id=session_id, state="ready", active_baseline=None, current_trial_id=None,
                current_trial_order=None, trial_state=None, completed_trials=0, total_trials=12,
                next_trial_order=1, break_required=False, interruption_reason=None,
                accepted_clean_seconds=0.0, wall_clock_seconds=0.0, file_recovery_required=False,
            ))()

        def start_stimulus(self, trial_id):
            raise AssertionError("wrong-session Trial must not reach state machine")

    monkeypatch.setattr(
        dataset_collection.collection_manager,
        "run",
        lambda db, session, operation: operation(FakeRunner(db)),
    )
    response = client.get(f"{BASE}/sessions/{session_id}/runner-state", headers=auth(client))
    assert response.status_code == 200
    assert response.json()["state"] == "ready"
    assert "file_path" not in response.text

    with client.app.state.factory() as db:
        other = CollectionSession(participant_id=1)
        db.add(other)
        db.flush()
        trial = CollectionTrial(
            session_id=other.id, stimulus_id=stimulus_id, randomized_order=1, state=TrialState.scheduled
        )
        db.add(trial)
        db.commit()
        wrong_trial_id = trial.id
    assert client.post(
        f"{BASE}/sessions/{session_id}/trials/{wrong_trial_id}/stimulus/start", headers=auth(client)
    ).status_code == 404
    assert client.get(f"{BASE}/sessions/9999/runner-state", headers=auth(client)).status_code == 404


def test_runner_state_identifies_current_stimulus_without_exposing_its_path(client, monkeypatch):
    session_id, stimulus_id = client.app.state.ids
    with client.app.state.factory() as db:
        trial = CollectionTrial(
            session_id=session_id, stimulus_id=stimulus_id, randomized_order=1, state=TrialState.rest
        )
        db.add(trial)
        db.commit()
        trial_id = trial.id

    class FakeRunner:
        db = None

        def state(self):
            return type("State", (), dict(
                session_id=session_id, state="in_progress", active_baseline=None,
                current_trial_id=trial_id, current_trial_order=1, trial_state="rest",
                completed_trials=0, total_trials=12, next_trial_order=None, break_required=False,
                interruption_reason=None, accepted_clean_seconds=0.0, wall_clock_seconds=1.0,
                file_recovery_required=False,
            ))()

    monkeypatch.setattr(
        dataset_collection.collection_manager,
        "run",
        lambda db, session, operation: operation(FakeRunner()),
    )
    response = client.get(f"{BASE}/sessions/{session_id}/runner-state", headers=auth(client))
    assert response.status_code == 200
    assert response.json()["current_stimulus_id"] == stimulus_id
    assert response.json()["current_stimulus_title"] == "Safe clip"
    assert "safe.mp4" not in response.text


def test_ready_runner_state_identifies_next_trial_without_revealing_quadrant(client, monkeypatch):
    session_id, stimulus_id = client.app.state.ids
    with client.app.state.factory() as db:
        trial = CollectionTrial(
            session_id=session_id, stimulus_id=stimulus_id, randomized_order=1, state=TrialState.scheduled
        )
        db.add(trial)
        db.commit()
        trial_id = trial.id

    class FakeRunner:
        def __init__(self, db):
            self.db = db

        def state(self):
            return type("State", (), dict(
                session_id=session_id, state="ready", active_baseline=None,
                current_trial_id=None, current_trial_order=None, trial_state=None,
                completed_trials=0, total_trials=12, next_trial_order=1, break_required=False,
                interruption_reason=None, accepted_clean_seconds=0.0, wall_clock_seconds=0.0,
                file_recovery_required=False,
            ))()

    monkeypatch.setattr(
        dataset_collection.collection_manager,
        "run",
        lambda db, session, operation: operation(FakeRunner(db)),
    )
    response = client.get(f"{BASE}/sessions/{session_id}/runner-state", headers=auth(client))
    assert response.status_code == 200
    assert response.json()["next_trial_id"] == trial_id
    assert response.json()["next_stimulus_id"] == stimulus_id
    assert response.json()["next_stimulus_title"] == "Safe clip"
    assert "quadrant" not in response.text


def test_rest_start_rejects_a_non_next_trial_before_transition(client, monkeypatch):
    session_id, stimulus_id = client.app.state.ids
    with client.app.state.factory() as db:
        first = CollectionTrial(
            session_id=session_id, stimulus_id=stimulus_id, randomized_order=1, state=TrialState.scheduled
        )
        second = CollectionTrial(
            session_id=session_id, stimulus_id=stimulus_id, randomized_order=2, state=TrialState.scheduled
        )
        db.add_all([first, second])
        db.commit()
        second_id = second.id

    called = False

    class FakeRunner:
        def __init__(self, db):
            self.db = db

        def state(self):
            return type("State", (), {"next_trial_order": 1})()

        def start_trial_rest(self):
            nonlocal called
            called = True

    monkeypatch.setattr(
        dataset_collection.collection_manager,
        "run_capture",
        lambda db, session, operation: operation(FakeRunner(db)),
    )
    response = client.post(
        f"{BASE}/sessions/{session_id}/trials/{second_id}/rest/start", headers=auth(client)
    )
    assert response.status_code == 409
    assert called is False


def test_collection_websocket_auth_closes_before_accept(client, monkeypatch):
    session_id, _ = client.app.state.ids
    with pytest.raises(WebSocketDisconnect) as missing:
        with client.websocket_connect(f"{BASE}/ws/{session_id}"):
            pass
    assert missing.value.code == 4401
    with pytest.raises(WebSocketDisconnect) as standard:
        with client.websocket_connect(f"{BASE}/ws/{session_id}?token={client.app.state.user_token}"):
            pass
    assert standard.value.code == 4403

    async def connect(_session_id, websocket, _db):
        await websocket.send_json({"sequence": 1, "state": "preparation"})

    async def disconnect(*_args, **_kwargs):
        return None

    monkeypatch.setattr(dataset_collection.collection_manager, "connect", connect)
    monkeypatch.setattr(dataset_collection.collection_manager, "disconnect", disconnect)
    with client.websocket_connect(f"{BASE}/ws/{session_id}?token={client.app.state.admin_token}") as ws:
        assert ws.receive_json() == {"sequence": 1, "state": "preparation"}
        ws.close()

    with pytest.raises(WebSocketDisconnect) as missing_session:
        with client.websocket_connect(f"{BASE}/ws/9999?token={client.app.state.admin_token}"):
            pass
    assert missing_session.value.code == 4404


def test_stimulus_media_fails_closed_and_serves_verified_video(client):
    _, stimulus_id = client.app.state.ids
    root = Path(client.app.state.collection_settings.collection_stimulus_dir)
    clip = root / "safe.mp4"
    clip.write_bytes(b"video-bytes")
    with client.app.state.factory() as db:
        stimulus = db.get(EmotionStimulus, stimulus_id)
        stimulus.checksum = hashlib.sha256(clip.read_bytes()).hexdigest()
        db.commit()

    assert client.get(f"{BASE}/stimuli/{stimulus_id}/media", headers=auth(client, "user")).status_code == 403
    response = client.get(f"{BASE}/stimuli/{stimulus_id}/media", headers=auth(client))
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("video/mp4")
    assert response.content == b"video-bytes"
    assert str(clip) not in response.text

    clip.write_bytes(b"tampered")
    assert client.get(f"{BASE}/stimuli/{stimulus_id}/media", headers=auth(client)).status_code == 409
    with client.app.state.factory() as db:
        stimulus = db.get(EmotionStimulus, stimulus_id)
        stimulus.file_path = "../escape.mp4"
        db.commit()
    assert client.get(f"{BASE}/stimuli/{stimulus_id}/media", headers=auth(client)).status_code == 404


def test_ordinary_eeg_websocket_source_is_unchanged():
    source = Path("app/routers/eeg_session.py").read_text(encoding="utf-8")
    assert "async def eeg_websocket(session_id: str, websocket: WebSocket):" in source
    assert "collection_manager" not in source


def test_collection_manager_owns_a_session_that_survives_request_cleanup(client, monkeypatch):
    session_id, _ = client.app.state.ids
    manager = CollectionConnectionManager()
    monkeypatch.setattr("app.ws.collection_manager.get_settings", lambda: client.app.state.collection_settings)
    with client.app.state.factory() as request_db:
        collection_session = request_db.get(CollectionSession, session_id)
        manager.run(request_db, collection_session, lambda runner: runner.select_device("muse-owned", "Muse 2"))
    with client.app.state.factory() as verification_db:
        persisted = verification_db.get(CollectionSession, session_id)
        assert persisted.device_id == "muse-owned"


def test_last_websocket_disconnect_interrupts_active_collection():
    manager = CollectionConnectionManager()
    interrupted = []

    class FakeRunner:
        def state(self):
            return type("State", (), {"state": CollectionSessionState.baseline})()

        def interrupt(self, reason):
            interrupted.append(reason)

    websocket = object()
    manager._runners[7] = FakeRunner()
    manager._clients[7].add(websocket)
    asyncio.run(manager.disconnect(7, websocket))
    assert interrupted == ["Muse disconnected"]


def test_stream_samples_wait_until_a_capture_phase_is_active():
    manager = CollectionConnectionManager()
    accepted = []
    observed = []

    class FakeSource:
        async def connect(self, device_id):
            assert device_id == "muse-1"

        async def samples(self):
            sensors = {name: SensorQuality("good", 80, 1.0) for name in ("tp9", "af7", "af8", "tp10")}
            yield type("Incoming", (), {
                "sample": EEGSample(1, 1, 2, 3, 4, 80, 80, 80, 80),
                "sensor_timestamps": {name: 1.0 for name in ("tp9", "af7", "af8", "tp10")},
                "sensors": sensors,
                "sampling_rate_hz": 256.0,
                "sampling_rate_ok": True,
                "capture_eligible": True,
            })()

    class FakeRunner:
        session = type("Session", (), {"device_id": "muse-1"})()

        def state(self):
            return CollectionRunnerState(
                session_id=3,
                state=CollectionSessionState.preparation,
                active_baseline=None,
                current_trial_id=None,
                current_trial_order=None,
                trial_state=None,
                completed_trials=0,
                total_trials=12,
                next_trial_order=1,
                break_required=False,
                interruption_reason=None,
                accepted_clean_seconds=0,
                wall_clock_seconds=0,
            )

        def accept_sample(self, *args, **kwargs):
            accepted.append((args, kwargs))

        def observe_quality(self, sensors, **kwargs):
            observed.append((sensors, kwargs))

    asyncio.run(manager._pump(3, FakeSource(), FakeRunner()))
    assert accepted == []
    assert observed[0][1] == {"sampling_rate_hz": 256.0, "sampling_rate_ok": True}


def test_muse_stream_ending_interrupts_an_active_capture():
    manager = CollectionConnectionManager()
    interrupted = []

    class EndingSource:
        async def connect(self, device_id):
            return None

        async def samples(self):
            if False:
                yield None

    class FakeRunner:
        session = type("Session", (), {"device_id": "muse-1"})()

        def state(self):
            return CollectionRunnerState(
                session_id=4,
                state=CollectionSessionState.baseline,
                active_baseline="eyes_open",
                current_trial_id=None,
                current_trial_order=None,
                trial_state=None,
                completed_trials=0,
                total_trials=12,
                next_trial_order=1,
                break_required=False,
                interruption_reason=None,
                accepted_clean_seconds=0,
                wall_clock_seconds=1,
            )

        def interrupt(self, reason):
            interrupted.append(reason)

    asyncio.run(manager._pump(4, EndingSource(), FakeRunner()))
    assert interrupted == ["Muse disconnected"]


def test_runner_access_is_serialized_per_session_without_overlap():
    manager = CollectionConnectionManager()
    manager._runners[11] = object()
    active = 0
    maximum = 0
    barrier = threading.Barrier(3)

    def operation(_runner):
        nonlocal active, maximum
        active += 1
        maximum = max(maximum, active)
        time.sleep(0.03)
        active -= 1

    def worker():
        barrier.wait()
        manager.run_active(11, operation)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    barrier.wait()
    for thread in threads:
        thread.join()
    assert maximum == 1


def test_device_selected_after_websocket_starts_source_task():
    async def scenario():
        started = asyncio.Event()

        class WaitingSource:
            async def connect(self, device_id):
                started.set()

            async def samples(self):
                await asyncio.Event().wait()
                yield None

            async def disconnect(self):
                return None

        class FakeRunner:
            session = type("Session", (), {"device_id": "muse-late"})()

        manager = CollectionConnectionManager(source_factory=WaitingSource)
        manager._runners[12] = FakeRunner()
        manager._clients[12].add(object())
        await manager.ensure_source(12)
        await asyncio.wait_for(started.wait(), timeout=0.2)
        assert 12 in manager._tasks
        assert 12 in manager._connected_sources
        await manager.stop_source(12)

    asyncio.run(scenario())


def test_natural_stream_end_cleans_up_and_can_restart():
    async def scenario():
        sources = []

        class EndingSource:
            def __init__(self):
                self.disconnected = 0
                sources.append(self)

            async def connect(self, device_id):
                return None

            async def samples(self):
                if False:
                    yield None

            async def disconnect(self):
                self.disconnected += 1

        class FakeRunner:
            session = type("Session", (), {"device_id": "muse-restart"})()

            def state(self):
                return CollectionRunnerState(
                    session_id=13, state=CollectionSessionState.preparation, active_baseline=None,
                    current_trial_id=None, current_trial_order=None, trial_state=None,
                    completed_trials=0, total_trials=12, next_trial_order=1, break_required=False,
                    interruption_reason=None, accepted_clean_seconds=0, wall_clock_seconds=0,
                )

        class WebSocket:
            async def send_json(self, payload):
                return None

        manager = CollectionConnectionManager(source_factory=EndingSource)
        manager._runners[13] = FakeRunner()
        manager._clients[13].add(WebSocket())
        await manager.ensure_source(13)
        await asyncio.sleep(0.02)
        assert 13 not in manager._tasks
        assert 13 not in manager._sources
        assert sources[0].disconnected == 1
        await manager.ensure_source(13)
        await asyncio.sleep(0.02)
        assert len(sources) == 2

    asyncio.run(scenario())


def test_late_lsl_open_is_closed_after_connection_timeout(monkeypatch):
    async def scenario():
        source = LSLMuseStreamSource(discovery_timeout=0.01)
        released = threading.Event()
        closed = threading.Event()
        inlet = object()

        async def discover():
            return [MuseDevice("muse", "Muse")]

        def delayed_open(_device_id):
            released.wait(timeout=1)
            return inlet, ("TP9", "AF7", "AF8", "TP10")

        monkeypatch.setattr(source, "discover", discover)
        monkeypatch.setattr(source, "_open_inlet", delayed_open)
        monkeypatch.setattr(source, "_close_inlet", lambda value: closed.set() if value is inlet else None)
        with pytest.raises(MuseStreamError, match="timed out"):
            await source.connect("muse")
        released.set()
        await asyncio.sleep(0.05)
        assert closed.is_set()

    asyncio.run(scenario())


def test_unexpected_stream_exception_is_not_broadcast_to_clients():
    async def scenario():
        messages = []

        class WebSocket:
            async def send_json(self, payload):
                messages.append(payload)

        class SecretFailureSource:
            async def connect(self, device_id):
                raise RuntimeError("database-password=secret")

        class FakeRunner:
            session = type("Session", (), {"device_id": "muse"})()

            def state(self):
                return CollectionRunnerState(
                    session_id=14, state=CollectionSessionState.preparation, active_baseline=None,
                    current_trial_id=None, current_trial_order=None, trial_state=None,
                    completed_trials=0, total_trials=12, next_trial_order=1, break_required=False,
                    interruption_reason=None, accepted_clean_seconds=0, wall_clock_seconds=0,
                )

        manager = CollectionConnectionManager()
        manager._clients[14].add(WebSocket())
        await manager._pump(14, SecretFailureSource(), FakeRunner())
        assert messages[-1]["stream_error"] == "Muse stream failed"
        assert "secret" not in str(messages)

    asyncio.run(scenario())


def test_http_device_command_broadcasts_returned_state(client, monkeypatch):
    session_id, _ = client.app.state.ids
    published = []

    class FakeRunner:
        def select_device(self, device_id, device_name):
            return self.state()

        def state(self):
            return CollectionRunnerState(
                session_id=session_id, state=CollectionSessionState.preparation, active_baseline=None,
                current_trial_id=None, current_trial_order=None, trial_state=None,
                completed_trials=0, total_trials=0, next_trial_order=None, break_required=False,
                interruption_reason=None, accepted_clean_seconds=0, wall_clock_seconds=0,
            )

    monkeypatch.setattr(
        dataset_collection.collection_manager,
        "run",
        lambda db, collection_session, command: command(FakeRunner()),
        raising=False,
    )

    async def publish(session_id, payload):
        published.append((session_id, payload))

    monkeypatch.setattr(dataset_collection.collection_manager, "publish", publish)
    monkeypatch.setattr(dataset_collection.collection_manager, "ensure_source", lambda _id: asyncio.sleep(0), raising=False)
    response = client.post(
        f"{BASE}/sessions/{session_id}/device",
        headers=auth(client),
        json={"device_id": "late", "device_name": "Muse 2"},
    )
    assert response.status_code == 200
    assert published and published[-1][0] == session_id
    assert published[-1][1].state is CollectionSessionState.preparation


def test_http_rating_command_broadcasts_completed_state(client, monkeypatch):
    session_id, stimulus_id = client.app.state.ids
    with client.app.state.factory() as db:
        trial = CollectionTrial(
            session_id=session_id,
            stimulus_id=stimulus_id,
            randomized_order=1,
            state=TrialState.rating,
        )
        db.add(trial)
        db.commit()
        trial_id = trial.id
    published = []

    class FakeRunner:
        def __init__(self, db):
            self.db = db

        def submit_rating(self, trial_id, **rating):
            assert rating == {"valence": 8, "arousal": 7, "confidence": 5}
            return CollectionRunnerState(
                session_id=session_id, state=CollectionSessionState.completed, active_baseline=None,
                current_trial_id=None, current_trial_order=None, trial_state=None,
                completed_trials=12, total_trials=12, next_trial_order=None, break_required=False,
                interruption_reason=None, accepted_clean_seconds=0, wall_clock_seconds=0,
            )

    monkeypatch.setattr(
        dataset_collection.collection_manager,
        "run_capture",
        lambda db, collection_session, command: command(FakeRunner(db)),
    )

    async def publish(session_id, payload):
        published.append((session_id, payload))

    monkeypatch.setattr(dataset_collection.collection_manager, "publish", publish)
    response = client.post(
        f"{BASE}/sessions/{session_id}/trials/{trial_id}/rating",
        headers=auth(client),
        json={"valence": 8, "arousal": 7, "confidence": 5},
    )
    assert response.status_code == 200
    assert published[-1][1].state is CollectionSessionState.completed


def test_lsl_unexpected_errors_are_translated_without_secret_details(monkeypatch):
    discovery = LSLMuseStreamSource(discovery_timeout=0.01)
    monkeypatch.setattr(discovery, "_resolve_streams", lambda: (_ for _ in ()).throw(RuntimeError("secret")))
    with pytest.raises(MuseStreamError, match="discovery failed") as discovered:
        asyncio.run(discovery.discover())
    assert "secret" not in str(discovered.value)

    async def open_failure():
        source = LSLMuseStreamSource(discovery_timeout=0.05)

        async def found():
            return [MuseDevice("muse", "Muse")]

        monkeypatch.setattr(source, "discover", found)
        monkeypatch.setattr(source, "_open_inlet", lambda _id: (_ for _ in ()).throw(RuntimeError("secret")))
        with pytest.raises(MuseStreamError, match="connection failed") as connected:
            await source.connect("muse")
        assert "secret" not in str(connected.value)

    asyncio.run(open_failure())


def test_http_only_runner_is_released_and_owned_db_session_is_closed(client, monkeypatch):
    session_id, _ = client.app.state.ids
    manager = CollectionConnectionManager()
    monkeypatch.setattr("app.ws.collection_manager.get_settings", lambda: client.app.state.collection_settings)
    with client.app.state.factory() as request_db:
        collection_session = request_db.get(CollectionSession, session_id)
        manager.run(request_db, collection_session, lambda runner: runner.state())
    owned = manager._runner_sessions[session_id]
    real_close = owned.close
    closed = []

    def close():
        closed.append(True)
        real_close()

    monkeypatch.setattr(owned, "close", close)
    assert manager.release_if_idle(session_id) is True
    assert closed == [True]
    assert session_id not in manager._runners
    assert session_id not in manager._runner_sessions


def test_idle_release_retains_websocket_flow_and_active_writer_context():
    manager = CollectionConnectionManager()

    class Runner:
        def __init__(self, state):
            self._state = state

        def state(self):
            return self._state

    preparation = CollectionRunnerState(
        session_id=21, state=CollectionSessionState.preparation, active_baseline=None,
        current_trial_id=None, current_trial_order=None, trial_state=None, completed_trials=0,
        total_trials=12, next_trial_order=1, break_required=False, interruption_reason=None,
        accepted_clean_seconds=0, wall_clock_seconds=0,
    )
    baseline = CollectionRunnerState(
        session_id=22, state=CollectionSessionState.baseline, active_baseline="eyes_open",
        current_trial_id=None, current_trial_order=None, trial_state=None, completed_trials=0,
        total_trials=12, next_trial_order=1, break_required=False, interruption_reason=None,
        accepted_clean_seconds=1, wall_clock_seconds=1,
    )
    manager._runners[21] = Runner(preparation)
    manager._clients[21].add(object())
    manager._runners[22] = Runner(baseline)
    manager._clients[22].add(object())
    manager._sources[22] = object()
    manager._connected_sources.add(22)

    assert manager.release_if_idle(21) is False
    assert manager.release_if_idle(22) is False
    assert 21 in manager._runners
    assert 22 in manager._runners


def test_repeated_http_only_state_queries_leave_no_manager_sessions(client, monkeypatch):
    session_id, _ = client.app.state.ids
    manager = CollectionConnectionManager()
    monkeypatch.setattr(dataset_collection, "collection_manager", manager)
    monkeypatch.setattr("app.ws.collection_manager.get_settings", lambda: client.app.state.collection_settings)

    for _ in range(3):
        response = client.get(f"{BASE}/sessions/{session_id}/runner-state", headers=auth(client))
        assert response.status_code == 200
        assert manager._runners == {}
        assert manager._runner_sessions == {}


def test_capture_command_requires_live_websocket_and_source(client, monkeypatch):
    session_id, _ = client.app.state.ids
    manager = CollectionConnectionManager()
    monkeypatch.setattr(dataset_collection, "collection_manager", manager)
    monkeypatch.setattr("app.ws.collection_manager.get_settings", lambda: client.app.state.collection_settings)

    selected = client.post(
        f"{BASE}/sessions/{session_id}/device",
        headers=auth(client),
        json={"device_id": "muse-offline", "device_name": "Muse 2"},
    )
    assert selected.status_code == 200
    response = client.post(
        f"{BASE}/sessions/{session_id}/baseline/eyes_open/start",
        headers=auth(client),
    )
    assert response.status_code == 409
    assert "live Muse connection" in response.json()["detail"]
    assert manager._runners == {}
    assert manager._runner_sessions == {}


def test_failed_http_only_schedule_releases_owned_runner_session(client, monkeypatch):
    session_id, _ = client.app.state.ids
    manager = CollectionConnectionManager()
    monkeypatch.setattr(dataset_collection, "collection_manager", manager)
    monkeypatch.setattr("app.ws.collection_manager.get_settings", lambda: client.app.state.collection_settings)

    response = client.post(f"{BASE}/sessions/{session_id}/schedule", headers=auth(client))
    assert response.status_code == 409
    assert manager._runners == {}
    assert manager._runner_sessions == {}


def test_runner_recovery_failure_closes_owned_session_without_registration(client, monkeypatch):
    session_id, _ = client.app.state.ids
    manager = CollectionConnectionManager()
    module = importlib.import_module("app.ws.collection_manager")
    closed = []

    class OwnedSession:
        def get(self, model, object_id):
            return object()

        def close(self):
            closed.append(True)

    owned = OwnedSession()
    monkeypatch.setattr(module, "Session", lambda **kwargs: owned)
    monkeypatch.setattr(
        module.CollectionStateMachine,
        "recover",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("recover failed")),
    )
    with client.app.state.factory() as request_db:
        collection_session = request_db.get(CollectionSession, session_id)
        with pytest.raises(RuntimeError, match="recover failed"):
            manager.run(request_db, collection_session, lambda runner: runner.state())

    assert closed == [True]
    assert manager._runners == {}
    assert manager._runner_sessions == {}


def test_idle_release_closes_session_even_if_runner_state_would_fail():
    manager = CollectionConnectionManager()
    closed = []

    class BrokenRunner:
        def state(self):
            raise RuntimeError("state inspection failed")

    class OwnedSession:
        def close(self):
            closed.append(True)

    manager._runners[31] = BrokenRunner()
    manager._runner_sessions[31] = OwnedSession()
    assert manager.release_if_idle(31) is True
    assert closed == [True]
    assert manager._runners == {}
    assert manager._runner_sessions == {}


def test_http_only_lifecycle_does_not_grow_sequence_or_lock_registries(client, monkeypatch):
    session_id, _ = client.app.state.ids
    manager = CollectionConnectionManager()
    monkeypatch.setattr(dataset_collection, "collection_manager", manager)
    monkeypatch.setattr("app.ws.collection_manager.get_settings", lambda: client.app.state.collection_settings)

    for index in range(10):
        response = client.post(
            f"{BASE}/sessions/{session_id}/device",
            headers=auth(client),
            json={"device_id": f"muse-{index}", "device_name": "Muse 2"},
        )
        assert response.status_code == 200
        assert manager._runners == {}
        assert manager._runner_sessions == {}
        assert manager._sequences == {}

    assert len(manager._locks) == 0
