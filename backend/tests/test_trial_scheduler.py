import os
import re
import threading
from datetime import datetime
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
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


_MYSQL_TEST_DATABASE_PATTERN = re.compile(r"eegpre_scheduler_test_[0-9a-f]{32}")


def _guard_mysql_test_database_name(database_name):
    assert _MYSQL_TEST_DATABASE_PATTERN.fullmatch(database_name)
    assert database_name != make_url(get_settings().database_url).database


@pytest.fixture
def mysql_scheduler_database_url():
    configured_url = make_url(
        os.getenv("EEGPRE_MYSQL_TEST_ADMIN_URL", get_settings().database_url)
    )
    if configured_url.get_backend_name() != "mysql":
        pytest.skip("MySQL scheduler integration requires a configured MySQL DATABASE_URL")

    database_name = f"eegpre_scheduler_test_{uuid4().hex}"
    _guard_mysql_test_database_name(database_name)
    server_engine = create_engine(configured_url.set(database=None), isolation_level="AUTOCOMMIT")
    try:
        with server_engine.connect() as connection:
            connection.exec_driver_sql(f"CREATE DATABASE `{database_name}` CHARACTER SET utf8mb4")
    except SQLAlchemyError as exc:
        server_engine.dispose()
        pytest.skip(f"MySQL scheduler integration unavailable: {type(exc).__name__}")

    try:
        yield configured_url.set(database=database_name)
    finally:
        _guard_mysql_test_database_name(database_name)
        with server_engine.connect() as connection:
            connection.exec_driver_sql(f"DROP DATABASE `{database_name}`")
        server_engine.dispose()


class _SimulatedRowLockSession:
    def __init__(self, db, simulation):
        self._db = db
        self._simulation = simulation
        self._holds_lock = False

    def scalars(self, statement, *args, **kwargs):
        sql = str(statement)
        if (
            "FROM collection_sessions" in sql
            and getattr(statement, "_for_update_arg", None) is not None
        ):
            with self._simulation["attempt_guard"]:
                self._simulation["attempts"] += 1
                attempt = self._simulation["attempts"]
                if attempt == 2:
                    self._simulation["second_attempted"].set()
            self._simulation["row_lock"].acquire()
            self._holds_lock = True
            if attempt == 1:
                assert self._simulation["second_attempted"].wait(timeout=5)
        elif "FROM collection_trials" in sql and not self._holds_lock:
            self._simulation["unlocked_read_barrier"].wait(timeout=5)
        return self._db.scalars(statement, *args, **kwargs)

    def commit(self):
        try:
            return self._db.commit()
        finally:
            self._release_lock()

    def rollback(self):
        try:
            return self._db.rollback()
        finally:
            self._release_lock()

    def close(self):
        self._release_lock()
        self._db.close()

    def _release_lock(self):
        if self._holds_lock:
            self._holds_lock = False
            self._simulation["row_lock"].release()

    def __getattr__(self, name):
        return getattr(self._db, name)


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
    collection_session = CollectionSession(
        participant_id=participant.id,
        device_id=f"muse-{participant_code}",
        device_name="Muse 2",
    )
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


def test_schedule_creation_requires_preparation_with_a_selected_device(db):
    missing_device = make_session(db, "P001")
    missing_device.device_id = None
    wrong_state = make_session(db, "P002")
    wrong_state.state = "ready"
    add_stimuli(db, approved_per_quadrant=3)
    db.commit()

    for collection_session in (missing_device, wrong_state):
        with pytest.raises(
            ScheduleUnavailableError,
            match="preparation.*selected device",
        ):
            create_trial_schedule(db, collection_session, seed=17)
        assert collection_session.total_trials == 0


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


def test_partial_existing_schedule_is_rejected_safely(db):
    session = make_session(db)
    add_stimuli(db)
    stimulus_id = db.scalar(select(EmotionStimulus.id).order_by(EmotionStimulus.id))
    db.add(
        CollectionTrial(
            session_id=session.id,
            stimulus_id=stimulus_id,
            randomized_order=1,
            state=TrialState.scheduled,
        )
    )
    session.total_trials = 1
    db.commit()

    with pytest.raises(ScheduleUnavailableError, match="Unable to create trial schedule"):
        create_trial_schedule(db, session, seed=1)

    assert len(db.scalars(select(CollectionTrial).where(CollectionTrial.session_id == session.id)).all()) == 1
    assert session.total_trials == 1


def test_scheduler_locks_session_row_before_checking_existing_trials(db, monkeypatch):
    session = make_session(db)
    add_stimuli(db)
    statements = []
    real_scalars = db.scalars

    def record_scalars(statement, *args, **kwargs):
        statements.append(statement)
        return real_scalars(statement, *args, **kwargs)

    monkeypatch.setattr(db, "scalars", record_scalars)

    create_trial_schedule(db, session, seed=1)

    assert "FROM collection_sessions" in str(statements[0])
    assert statements[0]._for_update_arg is not None


def test_unique_race_rolls_back_and_returns_valid_winner_schedule(db, monkeypatch):
    session = make_session(db)
    add_stimuli(db)
    stimulus_ids = list(db.scalars(select(EmotionStimulus.id).order_by(EmotionStimulus.id)))
    real_commit = db.commit
    inserted_winner = False

    def commit_winner_then_raise_unique_race():
        nonlocal inserted_winner
        if inserted_winner:
            real_commit()
            return
        inserted_winner = True
        db.rollback()
        db.add_all(
            [
                CollectionTrial(
                    session_id=session.id,
                    stimulus_id=stimulus_id,
                    randomized_order=order,
                    state=TrialState.scheduled,
                )
                for order, stimulus_id in enumerate(stimulus_ids, start=1)
            ]
        )
        session.total_trials = 12
        real_commit()
        raise IntegrityError("duplicate schedule", {}, Exception("unique violation"))

    monkeypatch.setattr(db, "commit", commit_winner_then_raise_unique_race)

    trials = create_trial_schedule(db, session, seed=99)

    assert len(trials) == 12
    assert [trial.randomized_order for trial in trials] == list(range(1, 13))
    assert len({trial.stimulus_id for trial in trials}) == 12
    assert db.get(CollectionSession, session.id).total_trials == 12


def test_two_workers_serialize_schedule_creation_and_return_one_schedule(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'scheduler-concurrency.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    setup_db = session_factory()
    collection_session = make_session(setup_db)
    session_id = collection_session.id
    add_stimuli(setup_db, approved_per_quadrant=5)
    setup_db.close()

    simulation = {
        "row_lock": threading.Lock(),
        "attempt_guard": threading.Lock(),
        "attempts": 0,
        "second_attempted": threading.Event(),
        "unlocked_read_barrier": threading.Barrier(2),
    }
    start = threading.Barrier(2)
    results = []
    errors = []

    def schedule(seed):
        worker_db = _SimulatedRowLockSession(session_factory(), simulation)
        try:
            worker_session = worker_db.get(CollectionSession, session_id)
            start.wait(timeout=5)
            trials = create_trial_schedule(worker_db, worker_session, seed=seed)
            results.append([(trial.id, trial.stimulus_id, trial.randomized_order) for trial in trials])
        except Exception as exc:  # pragma: no cover - asserted through errors
            errors.append(exc)
        finally:
            worker_db.close()

    workers = [threading.Thread(target=schedule, args=(seed,)) for seed in (11, 29)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(timeout=10)

    verification_db = session_factory()
    persisted = _load_persisted_schedule(verification_db, session_id)
    try:
        assert all(not worker.is_alive() for worker in workers)
        assert errors == []
        assert simulation["attempts"] == 2
        assert len(results) == 2
        assert results[0] == results[1]
        assert len(persisted) == 12
        assert verification_db.get(CollectionSession, session_id).total_trials == 12
    finally:
        verification_db.close()
        engine.dispose()


def test_mysql_workers_use_independent_connections_and_persist_one_schedule(
    mysql_scheduler_database_url,
):
    setup_engine = create_engine(mysql_scheduler_database_url)
    first_engine = create_engine(mysql_scheduler_database_url)
    second_engine = create_engine(mysql_scheduler_database_url)
    verification_engine = create_engine(mysql_scheduler_database_url)
    engines = (setup_engine, first_engine, second_engine, verification_engine)
    try:
        Base.metadata.create_all(setup_engine)
        with sessionmaker(bind=setup_engine)() as setup_db:
            collection_session = make_session(setup_db)
            session_id = collection_session.id
            add_stimuli(setup_db, approved_per_quadrant=5)

        start = threading.Barrier(2)
        results = []
        connection_ids = []
        errors = []

        def schedule(engine, seed):
            with sessionmaker(bind=engine)() as worker_db:
                try:
                    connection_ids.append(worker_db.scalar(text("SELECT CONNECTION_ID()")))
                    worker_session = worker_db.get(CollectionSession, session_id)
                    start.wait(timeout=10)
                    trials = create_trial_schedule(worker_db, worker_session, seed=seed)
                    results.append(
                        [(trial.id, trial.stimulus_id, trial.randomized_order) for trial in trials]
                    )
                except Exception as exc:  # pragma: no cover - asserted through errors
                    errors.append(exc)

        workers = [
            threading.Thread(target=schedule, args=(first_engine, 101)),
            threading.Thread(target=schedule, args=(second_engine, 202)),
        ]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(timeout=20)

        with sessionmaker(bind=verification_engine)() as verification_db:
            persisted = _load_persisted_schedule(verification_db, session_id)
            persisted_identity = [
                (trial.id, trial.stimulus_id, trial.randomized_order) for trial in persisted
            ]
            assert all(not worker.is_alive() for worker in workers)
            assert errors == []
            assert len(set(connection_ids)) == 2
            assert len(results) == 2
            assert results[0] == results[1] == persisted_identity
            assert len(persisted) == 12
            assert [trial.randomized_order for trial in persisted] == list(range(1, 13))
            assert len({trial.stimulus_id for trial in persisted}) == 12
            assert verification_db.get(CollectionSession, session_id).total_trials == 12
    finally:
        for engine in engines:
            engine.dispose()


def _load_persisted_schedule(db, session_id):
    return list(
        db.scalars(
            select(CollectionTrial)
            .where(CollectionTrial.session_id == session_id)
            .order_by(CollectionTrial.randomized_order)
        )
    )


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


def test_operational_failure_rolls_back_schedule_state_and_raises_safe_error(db, monkeypatch):
    session = make_session(db)
    add_stimuli(db, approved_per_quadrant=3)
    real_rollback = db.rollback
    rolled_back = False

    def fail_commit():
        raise OperationalError("secret connection SQL", {}, Exception("connection lost"))

    def track_rollback():
        nonlocal rolled_back
        rolled_back = True
        real_rollback()

    monkeypatch.setattr(db, "commit", fail_commit)
    monkeypatch.setattr(db, "rollback", track_rollback)

    with pytest.raises(ScheduleUnavailableError, match="Unable to create trial schedule") as exc_info:
        create_trial_schedule(db, session, seed=1)

    assert rolled_back is True
    assert "secret connection SQL" not in str(exc_info.value)
    assert session.total_trials == 0
    assert list(db.new) == []
    assert db.scalars(select(CollectionTrial).where(CollectionTrial.session_id == session.id)).all() == []
