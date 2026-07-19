from datetime import datetime

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.dataset_collection import (
    CollectionSession,
    CollectionTrial,
    DatasetParticipant,
    EmotionStimulus,
    ParticipantState,
    Quadrant,
    StimulusApprovalState,
    TrialState,
)
from app.services.trial_scheduler import ScheduleUnavailableError, create_trial_schedule


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


def make_session(db, participant_code="P001"):
    participant = DatasetParticipant(
        participant_code=participant_code,
        consent_confirmed_at=datetime(2026, 1, 1),
        state=ParticipantState.active,
    )
    db.add(participant)
    db.flush()
    collection_session = CollectionSession(participant_id=participant.id)
    db.add(collection_session)
    db.commit()
    return collection_session


def add_stimuli(db, *, approved_per_quadrant=3, include_unapproved=False):
    for quadrant in Quadrant:
        for index in range(approved_per_quadrant):
            db.add(
                EmotionStimulus(
                    title=f"{quadrant.value}-{index}",
                    file_path=f"stimuli/{quadrant.value}-{index}.mp4",
                    checksum=f"{quadrant.value}-{index}".ljust(64, "0"),
                    duration_seconds=45,
                    target_quadrant=quadrant,
                    approval_state=StimulusApprovalState.approved,
                    stimulus_set_version="v1",
                )
            )
        if include_unapproved:
            for state in (StimulusApprovalState.draft, StimulusApprovalState.retired):
                db.add(
                    EmotionStimulus(
                        title=f"{quadrant.value}-{state.value}",
                        file_path=f"stimuli/{quadrant.value}-{state.value}.mp4",
                        checksum=f"{quadrant.value}-{state.value}".ljust(64, "0"),
                        duration_seconds=45,
                        target_quadrant=quadrant,
                        approval_state=state,
                        stimulus_set_version="v1",
                    )
                )
    db.commit()


def scheduled_stimuli(db, trials):
    ids = [trial.stimulus_id for trial in trials]
    return list(db.scalars(select(EmotionStimulus).where(EmotionStimulus.id.in_(ids))))


def test_schedule_persists_three_approved_stimuli_per_quadrant_and_orders_one_to_twelve(db):
    session = make_session(db)
    add_stimuli(db, approved_per_quadrant=4)

    trials = create_trial_schedule(db, session, seed=17)

    assert len(trials) == 12
    assert sorted(trial.randomized_order for trial in trials) == list(range(1, 13))
    assert len({trial.randomized_order for trial in trials}) == 12
    assert len({trial.stimulus_id for trial in trials}) == 12
    assert {trial.state for trial in trials} == {TrialState.scheduled}
    counts = {quadrant: 0 for quadrant in Quadrant}
    for stimulus in scheduled_stimuli(db, trials):
        counts[stimulus.target_quadrant] += 1
        assert stimulus.approval_state is StimulusApprovalState.approved
    assert counts == {quadrant: 3 for quadrant in Quadrant}
    assert session.total_trials == 12


def test_explicit_seed_produces_deterministic_order(db):
    first = make_session(db, "P001")
    second = make_session(db, "P002")
    add_stimuli(db, approved_per_quadrant=5)

    first_order = [trial.stimulus_id for trial in create_trial_schedule(db, first, seed=314)]
    second_order = [trial.stimulus_id for trial in create_trial_schedule(db, second, seed=314)]

    assert first_order == second_order


def test_each_persisted_session_retains_its_first_schedule(db):
    first = make_session(db, "P001")
    second = make_session(db, "P002")
    add_stimuli(db, approved_per_quadrant=5)
    first_initial = create_trial_schedule(db, first, seed=1)
    second_initial = create_trial_schedule(db, second, seed=2)
    first_ids = [(trial.id, trial.stimulus_id, trial.randomized_order) for trial in first_initial]
    second_ids = [(trial.id, trial.stimulus_id, trial.randomized_order) for trial in second_initial]

    first_resumed = create_trial_schedule(db, first, seed=999)
    second_resumed = create_trial_schedule(db, second, seed=999)

    assert [(trial.id, trial.stimulus_id, trial.randomized_order) for trial in first_resumed] == first_ids
    assert [(trial.id, trial.stimulus_id, trial.randomized_order) for trial in second_resumed] == second_ids


def test_schedule_rejects_short_quadrant_without_persisting_partial_rows(db):
    session = make_session(db)
    add_stimuli(db, approved_per_quadrant=3)
    missing = db.scalar(
        select(EmotionStimulus).where(EmotionStimulus.target_quadrant == Quadrant.negative_high)
    )
    db.delete(missing)
    db.commit()

    with pytest.raises(ScheduleUnavailableError, match="negative_high"):
        create_trial_schedule(db, session, seed=1)

    assert db.scalars(select(CollectionTrial).where(CollectionTrial.session_id == session.id)).all() == []
    assert session.total_trials == 0


def test_draft_and_retired_stimuli_do_not_satisfy_inventory_or_enter_schedule(db):
    session = make_session(db)
    add_stimuli(db, approved_per_quadrant=2, include_unapproved=True)

    with pytest.raises(ScheduleUnavailableError, match="approved stimuli required"):
        create_trial_schedule(db, session, seed=1)

    assert db.scalars(select(CollectionTrial)).all() == []


def test_bulk_insert_failure_rolls_back_and_raises_safe_error(db, monkeypatch):
    session = make_session(db)
    add_stimuli(db, approved_per_quadrant=3)
    real_rollback = db.rollback
    rolled_back = False

    def fail_commit():
        raise IntegrityError("secret bulk SQL", {}, Exception("database detail"))

    def track_rollback():
        nonlocal rolled_back
        rolled_back = True
        real_rollback()

    monkeypatch.setattr(db, "commit", fail_commit)
    monkeypatch.setattr(db, "rollback", track_rollback)

    with pytest.raises(ScheduleUnavailableError, match="Unable to create trial schedule") as exc_info:
        create_trial_schedule(db, session, seed=1)

    assert rolled_back is True
    assert "secret bulk SQL" not in str(exc_info.value)
    assert db.scalars(select(CollectionTrial).where(CollectionTrial.session_id == session.id)).all() == []
