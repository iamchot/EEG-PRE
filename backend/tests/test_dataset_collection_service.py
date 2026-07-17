from datetime import datetime

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.dataset_collection import DatasetParticipant, ParticipantState
from app.schemas.dataset_collection import CollectionSessionResponse, StimulusCreate
from app.services.dataset_collection_service import (
    DatasetConflictError,
    ParticipantUnavailableError,
    create_collection_session,
    create_participant,
    create_stimulus,
)


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def stimulus_body(checksum="a" * 64):
    return StimulusCreate(
        title="Calm forest",
        file_path="stimuli/calm.mp4",
        checksum=checksum,
        duration_seconds=45,
        target_quadrant="positive_low",
        approval_state="draft",
        stimulus_set_version="v1",
    )


def test_participant_codes_increment_and_store_no_identifying_fields(db):
    first = create_participant(db, datetime(2026, 1, 1))
    second = create_participant(db, datetime(2026, 1, 2))

    assert (first.participant_code, second.participant_code) == ("P001", "P002")
    assert set(first.__table__.columns.keys()).isdisjoint({"name", "email", "phone"})


def test_duplicate_stimulus_checksum_raises_domain_conflict(db):
    create_stimulus(db, stimulus_body())

    with pytest.raises(DatasetConflictError):
        create_stimulus(db, stimulus_body())

    other = create_stimulus(db, stimulus_body("b" * 64))
    assert other.id is not None


def test_participant_creation_rolls_back_collision_then_retries(db, monkeypatch):
    real_commit = db.commit
    attempts = 0

    def collide_once():
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise IntegrityError("participant insert", {}, Exception("collision"))
        real_commit()

    monkeypatch.setattr(db, "commit", collide_once)

    participant = create_participant(db, datetime(2026, 1, 1))

    assert attempts == 2
    assert participant.participant_code == "P001"


@pytest.mark.parametrize("duration", [44.9, 60.1])
def test_stimulus_duration_must_be_between_45_and_60_seconds(duration):
    with pytest.raises(ValidationError):
        stimulus_body().model_copy(update={"duration_seconds": duration}).model_validate(
            {**stimulus_body().model_dump(), "duration_seconds": duration}
        )


def test_collection_session_rejects_withdrawn_participant(db):
    participant = DatasetParticipant(
        participant_code="P001",
        consent_confirmed_at=datetime(2026, 1, 1),
        state=ParticipantState.withdrawn,
    )
    db.add(participant)
    db.commit()

    with pytest.raises(ParticipantUnavailableError):
        create_collection_session(db, participant.id, None, None)


def test_collection_session_starts_in_preparation_with_zero_progress(db):
    participant = create_participant(db, datetime(2026, 1, 1))

    session = create_collection_session(db, participant.id, "muse-1", "Muse 2")

    assert session.state.value == "preparation"
    assert session.completed_trials == 0
    assert session.total_trials == 0


def test_collection_session_preserves_omitted_device_id(db):
    participant = create_participant(db, datetime(2026, 1, 1))

    session = create_collection_session(db, participant.id, None, None)

    assert session.device_id is None
    assert CollectionSessionResponse.model_validate(session).device_id is None


def test_collection_session_commit_failure_rolls_back_and_hides_sql(db, monkeypatch):
    participant = create_participant(db, datetime(2026, 1, 1))
    rolled_back = False

    def fail_commit():
        raise IntegrityError("secret SQL", {}, Exception("failure"))

    def track_rollback():
        nonlocal rolled_back
        rolled_back = True

    monkeypatch.setattr(db, "commit", fail_commit)
    monkeypatch.setattr(db, "rollback", track_rollback)

    with pytest.raises(DatasetConflictError, match="collection session") as exc_info:
        create_collection_session(db, participant.id, None, None)

    assert rolled_back is True
    assert "secret SQL" not in str(exc_info.value)
