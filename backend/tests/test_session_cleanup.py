from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch
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
from app.services.eeg_service import EEGStateMachine, Phase, SessionState


@pytest.fixture
def cleanup_client():
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
        db.add(user1)
        db.flush()

        session1 = EEGSession(user_id=user1.id)
        db.add(session1)
        db.commit()

        u1_id = user1.id
        s1_id = session1.id

    def override_db():
        with factory() as db:
            yield db

    app = FastAPI()
    app.include_router(eeg_session.router, prefix="/api/v1")
    app.dependency_overrides[get_db] = override_db

    tokens = {"user1": create_access_token(u1_id, "user")}

    with TestClient(app) as client:
        client.s1_id = s1_id
        client.u1_id = u1_id
        client.tokens = tokens
        yield client

    eeg_session._active_machines.clear()
    eeg_session._pending_muse_devices.clear()
    engine.dispose()


def test_final_client_disconnect_outside_active_capture_releases_bridge_and_runner(cleanup_client, monkeypatch):
    """When the last WS client leaves outside active capture, runner and bridge lease are released."""
    from app.routers import eeg_session

    s1_id = cleanup_client.s1_id
    u1_token = cleanup_client.tokens["user1"]

    stop_called = []
    release_called = []

    async def mock_runner_stop(session_id: int):
        stop_called.append(session_id)

    async def mock_bridge_release(owner):
        release_called.append(owner)

    monkeypatch.setattr("app.routers.eeg_session.user_eeg_stream_runner.stop", mock_runner_stop)
    monkeypatch.setattr("app.routers.eeg_session.managed_muse_bridge_manager.release", mock_bridge_release)

    # Machine in PREPARATION phase (not active capture)
    machine = EEGStateMachine(SessionState(session_id=str(s1_id), user_id=cleanup_client.u1_id))
    machine.state.phase = Phase.PREPARATION
    eeg_session._active_machines[str(s1_id)] = machine

    with cleanup_client.websocket_connect(f"/api/v1/sessions/ws/{s1_id}?token={u1_token}") as ws:
        data = ws.receive_json()
        assert data["session_id"] == str(s1_id)

    # After websocket closes, runner and bridge should be released
    assert s1_id in stop_called
    assert len(release_called) == 1
    assert release_called[0].session_id == s1_id


def test_final_client_disconnect_during_active_capture_preserves_bridge_and_runner(cleanup_client, monkeypatch):
    """When the last WS client leaves during active capture (RECORDING), capture runner and bridge remain alive."""
    from app.routers import eeg_session

    s1_id = cleanup_client.s1_id
    u1_token = cleanup_client.tokens["user1"]

    stop_called = []
    release_called = []

    async def mock_runner_stop(session_id: int):
        stop_called.append(session_id)

    async def mock_bridge_release(owner):
        release_called.append(owner)

    monkeypatch.setattr("app.routers.eeg_session.user_eeg_stream_runner.stop", mock_runner_stop)
    monkeypatch.setattr("app.routers.eeg_session.managed_muse_bridge_manager.release", mock_bridge_release)

    # Machine in RECORDING phase (active capture)
    machine = EEGStateMachine(SessionState(session_id=str(s1_id), user_id=cleanup_client.u1_id))
    machine.state.phase = Phase.RECORDING
    eeg_session._active_machines[str(s1_id)] = machine

    with cleanup_client.websocket_connect(f"/api/v1/sessions/ws/{s1_id}?token={u1_token}") as ws:
        data = ws.receive_json()
        assert data["session_id"] == str(s1_id)

    # Runner/bridge must NOT be released during active capture
    assert s1_id not in stop_called
    assert len(release_called) == 0
