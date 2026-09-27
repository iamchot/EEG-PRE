from datetime import datetime
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models.dataset_collection import CollectionSession, DatasetParticipant, EmotionStimulus
from app.models.user import Role, User
from app.routers import dataset_collection
from app.services.auth_service import create_access_token


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)

    with session_factory() as db:
        user_role = Role(name="user")
        admin_role = Role(name="admin")
        db.add_all([user_role, admin_role])
        db.flush()
        ordinary_user = User(
            username="user", email="user@example.com", password_hash="unused", role_id=user_role.id
        )
        admin_user = User(
            username="admin", email="admin@example.com", password_hash="unused", role_id=admin_role.id
        )
        db.add_all([ordinary_user, admin_user])
        db.commit()
        user_token = create_access_token(ordinary_user.id, "user")
        admin_token = create_access_token(admin_user.id, "admin")

    def override_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    app.include_router(dataset_collection.router, prefix="/api/v1")
    app.dependency_overrides[get_db] = override_db
    app.state.session_factory = session_factory
    app.state.admin_headers = {"Authorization": f"Bearer {admin_token}"}
    app.state.user_headers = {"Authorization": f"Bearer {user_token}"}
    with TestClient(app) as test_client:
        yield test_client
    engine.dispose()


BASE = "/api/v1/admin/dataset-collection"


def admin_headers(client):
    return client.app.state.admin_headers


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("get", "participants", None),
        ("post", "participants", {"consent_confirmed_at": "2026-01-01T10:00:00"}),
    ],
)
def test_collection_get_and_post_require_authentication(client, method, path, body):
    assert client.request(method, f"{BASE}/{path}", json=body).status_code == 401


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("get", "participants", None),
        ("post", "participants", {"consent_confirmed_at": "2026-01-01T10:00:00"}),
    ],
)
def test_collection_get_and_post_reject_standard_users(client, method, path, body):
    response = client.request(method, f"{BASE}/{path}", headers=client.app.state.user_headers, json=body)
    assert response.status_code == 403


def test_admin_creates_and_lists_pseudonymous_participants_without_pii(client):
    response = client.post(
        f"{BASE}/participants",
        headers=admin_headers(client),
        json={"consent_confirmed_at": "2026-01-01T10:00:00"},
    )

    assert response.status_code == 201
    assert response.json()["participant_code"] == "P001"
    assert set(response.json()).isdisjoint({"name", "email", "phone"})
    listed = client.get(f"{BASE}/participants", headers=admin_headers(client))
    assert listed.status_code == 200
    assert listed.json()["items"][0]["participant_code"] == "P001"
    assert set(listed.json()["items"][0]).isdisjoint({"name", "email", "phone"})


def test_admin_creates_and_lists_45_to_60_second_stimuli(client):
    for index, duration in enumerate((45, 60)):
        response = client.post(
            f"{BASE}/stimuli",
            headers=admin_headers(client),
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

    listed = client.get(f"{BASE}/stimuli", headers=admin_headers(client))
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
    assert client.post(f"{BASE}/stimuli", headers=admin_headers(client), json=body).status_code == 201
    assert client.post(f"{BASE}/stimuli", headers=admin_headers(client), json=body).status_code == 409


def test_overview_has_zero_defaults_for_all_collection_counts(client):
    response = client.get(f"{BASE}/overview", headers=admin_headers(client))

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
        "completed_trials": 0,
        "scheduled_trials": 0,
        "total_eeg_bytes": 0,
        "sessions_by_state": {},
        "ratings_distribution": [],
        "quadrant_stats": {
            "positive_low": {"target_count": 0, "avg_valence": None, "avg_arousal": None},
            "positive_high": {"target_count": 0, "avg_valence": None, "avg_arousal": None},
            "negative_low": {"target_count": 0, "avg_valence": None, "avg_arousal": None},
            "negative_high": {"target_count": 0, "avg_valence": None, "avg_arousal": None},
        },
    }


def test_session_trials_detail_returns_not_found_for_missing_session(client):
    response = client.get(f"{BASE}/sessions/999/trials", headers=admin_headers(client))
    assert response.status_code == 404


def test_admin_creates_preparation_session_for_active_participant(client):
    participant = client.post(
        f"{BASE}/participants",
        headers=admin_headers(client),
        json={"consent_confirmed_at": datetime(2026, 1, 1).isoformat()},
    ).json()

    response = client.post(
        f"{BASE}/sessions",
        headers=admin_headers(client),
        json={"participant_id": participant["id"], "device_id": "muse-1", "device_name": "Muse 2"},
    )

    assert response.status_code == 201
    assert response.json()["state"] == "preparation"
    assert response.json()["completed_trials"] == 0
    assert client.get(f"{BASE}/sessions", headers=admin_headers(client)).json()["items"][0]["id"] == response.json()["id"]


def test_session_for_missing_participant_returns_not_found(client):
    response = client.post(
        f"{BASE}/sessions",
        headers=admin_headers(client),
        json={"participant_id": 999},
    )

    assert response.status_code == 404


@pytest.mark.parametrize("resource", ["participants", "stimuli", "sessions"])
def test_collection_lists_default_to_first_50_in_ascending_id_order(client, resource):
    _seed_list_records(client, 105)

    response = client.get(f"{BASE}/{resource}", headers=admin_headers(client))

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["items"]] == list(range(1, 51))


@pytest.mark.parametrize("resource", ["participants", "stimuli", "sessions"])
def test_collection_lists_support_explicit_bounded_pagination(client, resource):
    _seed_list_records(client, 105)

    response = client.get(f"{BASE}/{resource}?skip=50&limit=100", headers=admin_headers(client))

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["items"]] == list(range(51, 106))
    assert client.get(f"{BASE}/{resource}?limit=101", headers=admin_headers(client)).status_code == 422
    assert client.get(f"{BASE}/{resource}?skip=-1", headers=admin_headers(client)).status_code == 422


def _seed_list_records(client, count):
    with client.app.state.session_factory() as db:
        db.add_all(
            DatasetParticipant(
                participant_code=f"P{index:03d}",
                consent_confirmed_at=datetime(2026, 1, 1),
                state="active",
            )
            for index in range(1, count + 1)
        )
        db.add_all(
            EmotionStimulus(
                title=f"Stimulus {index}",
                file_path=f"stimuli/{index}.mp4",
                checksum=f"{index:064x}",
                duration_seconds=45,
                target_quadrant="positive_low",
                approval_state="draft",
                stimulus_set_version="v1",
            )
            for index in range(1, count + 1)
        )
        db.add_all(CollectionSession(participant_id=index) for index in range(1, count + 1))
        db.commit()


def test_withdraw_participant(client):
    create_resp = client.post(
        f"{BASE}/participants",
        headers=admin_headers(client),
        json={"consent_confirmed_at": "2026-09-27T10:00:00"},
    )
    assert create_resp.status_code == 201
    p_id = create_resp.json()["id"]

    withdraw_resp = client.post(
        f"{BASE}/participants/{p_id}/withdraw",
        headers=admin_headers(client),
    )
    assert withdraw_resp.status_code == 200
    data = withdraw_resp.json()
    assert data["state"] == "withdrawn"
    assert data["withdrawn_at"] is not None

    # Idempotent
    second_resp = client.post(
        f"{BASE}/participants/{p_id}/withdraw",
        headers=admin_headers(client),
    )
    assert second_resp.status_code == 200
    assert second_resp.json()["state"] == "withdrawn"

    # 404 for missing
    missing_resp = client.post(
        f"{BASE}/participants/99999/withdraw",
        headers=admin_headers(client),
    )
    assert missing_resp.status_code == 404


def test_update_stimulus_approval(client):
    create_resp = client.post(
        f"{BASE}/stimuli",
        headers=admin_headers(client),
        json={
            "title": "Test Video",
            "file_path": "test/vid.mp4",
            "checksum": "a" * 64,
            "duration_seconds": 50.0,
            "target_quadrant": "positive_low",
            "approval_state": "draft",
            "stimulus_set_version": "v1.0",
        },
    )
    assert create_resp.status_code == 201
    s_id = create_resp.json()["id"]

    patch_resp = client.patch(
        f"{BASE}/stimuli/{s_id}/approval",
        headers=admin_headers(client),
        json={"approval_state": "approved"},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["approval_state"] == "approved"

    patch_resp2 = client.patch(
        f"{BASE}/stimuli/{s_id}/approval",
        headers=admin_headers(client),
        json={"approval_state": "retired"},
    )
    assert patch_resp2.status_code == 200
    assert patch_resp2.json()["approval_state"] == "retired"

    patch_missing = client.patch(
        f"{BASE}/stimuli/99999/approval",
        headers=admin_headers(client),
        json={"approval_state": "approved"},
    )
    assert patch_missing.status_code == 404


def test_stimuli_inspect_and_available_files(client):
    avail_resp = client.get(
        f"{BASE}/stimuli/available-files",
        headers=admin_headers(client),
    )
    assert avail_resp.status_code == 200
    files = avail_resp.json()["files"]
    assert isinstance(files, list)

    # Test inspect file that exists
    inspect_resp = client.post(
        f"{BASE}/stimuli/inspect-file",
        headers=admin_headers(client),
        json={"file_path": "relax/relax1.mp4"},
    )
    assert inspect_resp.status_code == 200
    data = inspect_resp.json()
    assert data["checksum"] == "7bac4d899130dc77fa4f8a1d2f8f182e9fe5166b6254b981f9d43b52afaed0b6"
    assert data["duration_seconds"] == 59.86
    assert data["suggested_quadrant"] == "positive_low"
    assert data["is_valid_duration"] is True

    # Test inspect non-existent file
    inspect_missing = client.post(
        f"{BASE}/stimuli/inspect-file",
        headers=admin_headers(client),
        json={"file_path": "non_existent/video.mp4"},
    )
    assert inspect_missing.status_code == 404


def test_stimuli_upload(client):
    import io

    content = b"fake video content for testing upload endpoint"
    files = {"file": ("test_upload_relax.mp4", io.BytesIO(content), "video/mp4")}
    data = {"subfolder": "relax"}
    resp = client.post(
        f"{BASE}/stimuli/upload",
        headers=admin_headers(client),
        files=files,
        data=data,
    )
    assert resp.status_code == 200
    res_data = resp.json()
    assert "file_path" in res_data
    assert res_data["file_path"].startswith("relax/")
    assert len(res_data["checksum"]) == 64
    assert res_data["file_size_bytes"] == len(content)


def test_upload_and_create_stimulus(client):
    from pathlib import Path

    sample = Path("collection_stimuli/relax/relax1.mp4")
    if sample.exists():
        with open(sample, "rb") as f:
            content = f.read()
        files = {"file": ("new_uploaded_relax.mp4", content, "video/mp4")}
        data = {
            "title": "New Uploaded Relax",
            "target_quadrant": "positive_low",
            "approval_state": "draft",
            "stimulus_set_version": "v1",
        }
        resp = client.post(
            f"{BASE}/stimuli/upload-and-create",
            headers=admin_headers(client),
            files=files,
            data=data,
        )
        assert resp.status_code == 201
        res = resp.json()
        assert res["title"] == "New Uploaded Relax"
        assert res["duration_seconds"] == 59.86
        assert res["target_quadrant"] == "positive_low"



