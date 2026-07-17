from datetime import datetime
from types import SimpleNamespace

import pytest
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.middleware.auth_middleware import require_admin
from app.routers import dataset_collection


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)

    def override_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    def override_admin(x_test_role: str | None = Header(default=None)):
        if x_test_role is None:
            raise HTTPException(status_code=401, detail="Not authenticated")
        if x_test_role != "admin":
            raise HTTPException(status_code=403, detail="Admin access required")
        return SimpleNamespace(id=1)

    app = FastAPI()
    app.include_router(dataset_collection.router, prefix="/api/v1")
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[require_admin] = override_admin
    with TestClient(app) as test_client:
        yield test_client
    engine.dispose()


ADMIN = {"X-Test-Role": "admin"}
BASE = "/api/v1/admin/dataset-collection"


@pytest.mark.parametrize("path", ["overview", "participants", "stimuli", "sessions"])
def test_collection_endpoints_require_authentication(client, path):
    assert client.get(f"{BASE}/{path}").status_code == 401


@pytest.mark.parametrize("path", ["overview", "participants", "stimuli", "sessions"])
def test_collection_endpoints_reject_standard_users(client, path):
    assert client.get(f"{BASE}/{path}", headers={"X-Test-Role": "user"}).status_code == 403


def test_admin_creates_and_lists_pseudonymous_participants_without_pii(client):
    response = client.post(
        f"{BASE}/participants",
        headers=ADMIN,
        json={"consent_confirmed_at": "2026-01-01T10:00:00"},
    )

    assert response.status_code == 201
    assert response.json()["participant_code"] == "P001"
    assert set(response.json()).isdisjoint({"name", "email", "phone"})
    listed = client.get(f"{BASE}/participants", headers=ADMIN)
    assert listed.status_code == 200
    assert listed.json()["items"][0]["participant_code"] == "P001"
    assert set(listed.json()["items"][0]).isdisjoint({"name", "email", "phone"})


def test_admin_creates_and_lists_45_to_60_second_stimuli(client):
    for index, duration in enumerate((45, 60)):
        response = client.post(
            f"{BASE}/stimuli",
            headers=ADMIN,
            json={
                "title": f"Stimulus {index}",
                "file_path": f"stimuli/{index}.mp4",
                "checksum": str(index) * 64,
                "duration_seconds": duration,
                "target_quadrant": "positive_low",
                "approval_state": "approved",
                "stimulus_set_version": "v1",
            },
        )
        assert response.status_code == 201

    listed = client.get(f"{BASE}/stimuli", headers=ADMIN)
    assert [item["duration_seconds"] for item in listed.json()["items"]] == [45, 60]


def test_duplicate_stimulus_checksum_returns_conflict(client):
    body = {
        "title": "Calm forest",
        "file_path": "stimuli/calm.mp4",
        "checksum": "a" * 64,
        "duration_seconds": 45,
        "target_quadrant": "positive_low",
        "approval_state": "draft",
        "stimulus_set_version": "v1",
    }
    assert client.post(f"{BASE}/stimuli", headers=ADMIN, json=body).status_code == 201
    assert client.post(f"{BASE}/stimuli", headers=ADMIN, json=body).status_code == 409


def test_overview_has_zero_defaults_for_all_collection_counts(client):
    response = client.get(f"{BASE}/overview", headers=ADMIN)

    assert response.status_code == 200
    assert response.json() == {
        "participants": 0,
        "sessions": 0,
        "trials": 0,
        "review_counts": {"pending": 0, "accepted": 0, "rejected": 0},
        "quadrant_counts": {
            "positive_low": 0,
            "positive_high": 0,
            "negative_low": 0,
            "negative_high": 0,
        },
    }


def test_admin_creates_preparation_session_for_active_participant(client):
    participant = client.post(
        f"{BASE}/participants",
        headers=ADMIN,
        json={"consent_confirmed_at": datetime(2026, 1, 1).isoformat()},
    ).json()

    response = client.post(
        f"{BASE}/sessions",
        headers=ADMIN,
        json={"participant_id": participant["id"], "device_id": "muse-1", "device_name": "Muse 2"},
    )

    assert response.status_code == 201
    assert response.json()["state"] == "preparation"
    assert response.json()["completed_trials"] == 0
    assert client.get(f"{BASE}/sessions", headers=ADMIN).json()["items"][0]["id"] == response.json()["id"]


def test_session_for_missing_participant_returns_not_found(client):
    response = client.post(
        f"{BASE}/sessions",
        headers=ADMIN,
        json={"participant_id": 999},
    )

    assert response.status_code == 404
