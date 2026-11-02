from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models.eeg import EEGSession
from app.models.user import Role, User
from app.services.auth_service import create_access_token


@pytest.fixture
def security_client():
    from app.routers import eeg_session

    eeg_session._active_machines.clear()
    eeg_session._pending_muse_devices.clear()

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)

    with factory() as db:
        user_role = Role(name="user")
        db.add(user_role)
        db.flush()

        user1 = User(username="user1", email="user1@example.com", password_hash="x", role_id=user_role.id)
        user2 = User(username="user2", email="user2@example.com", password_hash="x", role_id=user_role.id)
        db.add_all((user1, user2))
        db.flush()

        session1 = EEGSession(user_id=user1.id)
        session2 = EEGSession(user_id=user2.id)
        db.add_all((session1, session2))
        db.commit()

        u1_id, u2_id = user1.id, user2.id
        s1_id, s2_id = session1.id, session2.id

    def override_db():
        with factory() as db:
            yield db

    app = FastAPI()
    app.include_router(eeg_session.router, prefix="/api/v1")
    app.dependency_overrides[get_db] = override_db

    # Active state machine for s1_id
    from app.services.eeg_service import EEGStateMachine, SessionState
    eeg_session._active_machines[str(s1_id)] = EEGStateMachine(SessionState(session_id=str(s1_id), user_id=u1_id))

    tokens = {
        "user1": create_access_token(u1_id, "user"),
        "user2": create_access_token(u2_id, "user"),
    }

    with TestClient(app) as client:
        client.s1_id = s1_id
        client.s2_id = s2_id
        client.tokens = tokens
        yield client

    eeg_session._active_machines.clear()
    eeg_session._pending_muse_devices.clear()
    engine.dispose()


def test_ws_unauthenticated_connection_rejected(security_client):
    """Anonymous WS connection (no token) should be closed with code 4401."""
    s1_id = security_client.s1_id
    with pytest.raises(Exception):
        with security_client.websocket_connect(f"/api/v1/sessions/ws/{s1_id}") as ws:
            pass


def test_ws_invalid_token_rejected(security_client):
    """WS connection with invalid token should be closed with code 4401."""
    s1_id = security_client.s1_id
    with pytest.raises(Exception):
        with security_client.websocket_connect(f"/api/v1/sessions/ws/{s1_id}?token=invalid.jwt.token") as ws:
            pass


def test_ws_other_user_token_rejected(security_client):
    """WS connection using User2's token on User1's session should be closed with code 4403."""
    s1_id = security_client.s1_id
    u2_token = security_client.tokens["user2"]
    with pytest.raises(Exception):
        with security_client.websocket_connect(f"/api/v1/sessions/ws/{s1_id}?token={u2_token}") as ws:
            pass


def test_ws_nonexistent_session_rejected(security_client):
    """WS connection to non-existent session ID should be closed with code 4404."""
    u1_token = security_client.tokens["user1"]
    with pytest.raises(Exception):
        with security_client.websocket_connect(f"/api/v1/sessions/ws/999999?token={u1_token}") as ws:
            pass


def test_ws_authorized_owner_succeeds(security_client):
    """WS connection using User1's token on User1's session should succeed and receive state."""
    s1_id = security_client.s1_id
    u1_token = security_client.tokens["user1"]
    with security_client.websocket_connect(f"/api/v1/sessions/ws/{s1_id}?token={u1_token}") as ws:
        data = ws.receive_json()
        assert "session_id" in data
        assert data["session_id"] == str(s1_id)


def test_confirm_device_http_other_user_forbidden(security_client):
    """User2 calling confirm-device on User1's session should be rejected with 404/403."""
    s1_id = security_client.s1_id
    u2_token = security_client.tokens["user2"]
    res = security_client.post(
        f"/api/v1/sessions/{s1_id}/confirm-device?device_name=Muse&device_id=AA:BB",
        headers={"Authorization": f"Bearer {u2_token}"},
    )
    assert res.status_code in (403, 404)


def test_start_baseline_http_other_user_forbidden(security_client):
    """User2 calling start-baseline on User1's session should be rejected with 404/403."""
    s1_id = security_client.s1_id
    u2_token = security_client.tokens["user2"]
    res = security_client.post(
        f"/api/v1/sessions/{s1_id}/start-baseline",
        headers={"Authorization": f"Bearer {u2_token}"},
    )
    assert res.status_code in (403, 404)


def test_start_recording_http_other_user_forbidden(security_client):
    """User2 calling start-recording on User1's session should be rejected with 404/403."""
    s1_id = security_client.s1_id
    u2_token = security_client.tokens["user2"]
    res = security_client.post(
        f"/api/v1/sessions/{s1_id}/start-recording",
        headers={"Authorization": f"Bearer {u2_token}"},
    )
    assert res.status_code in (403, 404)


def test_two_stage_baseline_lifecycle():
    """Verify eyes_open -> eyes_closed -> READY lifecycle and to_ws_dict snapshot."""
    import numpy as np
    from app.services.eeg_service import EEGStateMachine, SessionState, Phase
    from app.services.signal_processor import SensorQuality

    state = SessionState(session_id="test_sess", user_id=1)
    machine = EEGStateMachine(state)
    machine.BASELINE_WALL_TARGET = 1.0
    machine.BASELINE_CLEAN_TARGET = 0.5

    machine.start_baseline(subphase="eyes_open")
    assert state.phase == Phase.BASELINE
    assert state.baseline_subphase == "eyes_open"

    good_sensors = {
        ch: SensorQuality(state="good", quality_score=90.0, timestamp=1.0, sequence=1)
        for ch in ("tp9", "af7", "af8", "tp10")
    }

    # Simulate samples for eyes_open
    for i in range(15):
        sample = np.array([[10.0, 15.0, 12.0, 11.0]], dtype=float)
        ts = np.array([float(i)])
        machine.ingest_samples(sample, ts, sensor_qualities=good_sensors)
        if machine._last_baseline_time:
            machine._last_baseline_time -= 0.1

    assert state.baseline_subphase == "eyes_closed"

    # Simulate samples for eyes_closed
    for i in range(15):
        sample = np.array([[10.0, 15.0, 12.0, 11.0]], dtype=float)
        ts = np.array([float(i)])
        machine.ingest_samples(sample, ts, sensor_qualities=good_sensors)
        if machine._last_baseline_time:
            machine._last_baseline_time -= 0.1

    assert state.phase == Phase.READY
    ws_dict = machine.to_ws_dict()
    assert ws_dict["eyes_open_complete"] is True
    assert ws_dict["eyes_closed_complete"] is True
    assert ws_dict["ready"] is True


def test_baseline_clean_seconds_accumulate_with_poor_sensors():
    """Baseline clean-seconds must accumulate on artifact-free samples even when all
    sensor debounce states are poor -- previously, all_sensors_good gated the counter
    and caused the 30-second window to appear frozen on the Web Bluetooth path.
    """
    import numpy as np
    from app.services.eeg_service import EEGStateMachine, SessionState, Phase
    from app.services.signal_processor import SensorQuality

    state = SessionState(session_id="test_poor_sensors", user_id=1)
    machine = EEGStateMachine(state)
    machine.BASELINE_WALL_TARGET = 1.0
    machine.BASELINE_CLEAN_TARGET = 0.5
    machine.start_baseline(subphase="eyes_open")

    poor_sensors = {
        ch: SensorQuality(state="poor", quality_score=40.0, timestamp=1.0, sequence=1)
        for ch in ("tp9", "af7", "af8", "tp10")
    }

    for i in range(15):
        sample = np.array([[10.0, 15.0, 12.0, 11.0]], dtype=float)
        machine.ingest_samples(sample, np.array([float(i)]), sensor_qualities=poor_sensors)
        if machine._last_baseline_time:
            machine._last_baseline_time -= 0.1

    assert state.baseline_eyes_open_clean_seconds > 0.0, (
        "Baseline clean-seconds must accumulate on artifact-free samples "
        "regardless of sensor debounce state"
    )
