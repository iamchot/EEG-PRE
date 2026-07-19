from __future__ import annotations

import asyncio
import hashlib
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
from app.services.muse_stream import LSLMuseStreamSource, MuseStreamError
from app.services.raw_eeg_writer import EEGSample
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
    source = LSLMuseStreamSource(clock=lambda: 10.0, stale_after_seconds=2.0)
    source._channel_names = ("AF8", "TP10", "TP9", "AF7")
    mapped = source.map_sample([3.0, 4.0, 1.0, 2.0], timestamp=9.0)
    assert (mapped.sample.tp9, mapped.sample.af7, mapped.sample.af8, mapped.sample.tp10) == (1, 2, 3, 4)
    assert set(mapped.sensor_timestamps) == {"tp9", "af7", "af8", "tp10"}
    with pytest.raises(MuseStreamError, match="stale"):
        source.map_sample([3.0, 4.0, 1.0, 2.0], timestamp=7.9)


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
        def state(self):
            return type("State", (), dict(
                session_id=session_id, state="ready", active_baseline=None, current_trial_id=None,
                current_trial_order=None, trial_state=None, completed_trials=0, total_trials=12,
                next_trial_order=1, break_required=False, interruption_reason=None,
                accepted_clean_seconds=0.0, wall_clock_seconds=0.0, file_recovery_required=False,
            ))()

        def start_stimulus(self, trial_id):
            raise AssertionError("wrong-session Trial must not reach state machine")

    monkeypatch.setattr(dataset_collection.collection_manager, "get_runner", lambda db, session: FakeRunner())
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

    monkeypatch.setattr(dataset_collection.collection_manager, "get_runner", lambda db, session: FakeRunner())
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
        def state(self):
            return type("State", (), dict(
                session_id=session_id, state="ready", active_baseline=None,
                current_trial_id=None, current_trial_order=None, trial_state=None,
                completed_trials=0, total_trials=12, next_trial_order=1, break_required=False,
                interruption_reason=None, accepted_clean_seconds=0.0, wall_clock_seconds=0.0,
                file_recovery_required=False,
            ))()

    monkeypatch.setattr(dataset_collection.collection_manager, "get_runner", lambda db, session: FakeRunner())
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
        def state(self):
            return type("State", (), {"next_trial_order": 1})()

        def start_trial_rest(self):
            nonlocal called
            called = True

    monkeypatch.setattr(dataset_collection.collection_manager, "get_runner", lambda db, session: FakeRunner())
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
        runner = manager.get_runner(request_db, request_db.get(CollectionSession, session_id))

    runner.select_device("muse-owned", "Muse 2")
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

    class FakeSource:
        async def connect(self, device_id):
            assert device_id == "muse-1"

        async def samples(self):
            yield type("Incoming", (), {
                "sample": EEGSample(1, 1, 2, 3, 4, 100, 100, 100, 100),
                "sensor_timestamps": {name: 1.0 for name in ("tp9", "af7", "af8", "tp10")},
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

    asyncio.run(manager._pump(3, FakeSource(), FakeRunner()))
    assert accepted == []


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
