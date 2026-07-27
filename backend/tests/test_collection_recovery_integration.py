from __future__ import annotations

import csv
import hashlib
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.config import Settings
from app.database import Base
from app.models.dataset_collection import (
    BaselineKind,
    CollectionSession,
    CollectionTrial,
    DatasetParticipant,
    EmotionStimulus,
    ParticipantState,
    Quadrant,
    StimulusApprovalState,
    TrialState,
)
from app.services.collection_state_machine import CollectionStateMachine
from app.services.raw_eeg_writer import AtomicEEGWriter, EEGSample
from app.services.trial_scheduler import create_trial_schedule


class DeterministicClock:
    def __init__(self) -> None:
        self.value = 1_000.0
        self.wall = datetime(2026, 7, 19, 10, 0, 0)

    def monotonic(self) -> float:
        return self.value

    def now(self) -> datetime:
        return self.wall + timedelta(seconds=self.value - 1_000.0)

    def advance(self, seconds: float) -> None:
        self.value += seconds


SENSORS = ("tp9", "af7", "af8", "tp10")


def _sample(clock: DeterministicClock) -> EEGSample:
    return EEGSample(clock.value, 1.0, 2.0, 3.0, 4.0, 80.0, 80.0, 80.0, 80.0)


def _accept_sample(runner: CollectionStateMachine, clock: DeterministicClock) -> None:
    runner.accept_sample(
        _sample(clock),
        sensor_timestamps={sensor: clock.value for sensor in SENSORS},
    )


def _finish_baseline(
    runner: CollectionStateMachine,
    clock: DeterministicClock,
    kind: BaselineKind,
) -> None:
    runner.start_baseline(kind)
    clock.advance(0.001)
    _accept_sample(runner, clock)
    for _ in range(31):
        clock.advance(1.0)
        _accept_sample(runner, clock)
    clock.advance(28.999)
    runner.finish_baseline()


def _schedule(db, collection_session: CollectionSession) -> list[tuple[int, int, int]]:
    return [
        (trial.id, trial.stimulus_id, trial.randomized_order)
        for trial in db.scalars(
            select(CollectionTrial)
            .where(CollectionTrial.session_id == collection_session.id)
            .order_by(CollectionTrial.randomized_order)
        )
    ]


def test_real_writer_recovery_preserves_raw_trial_and_schedule(tmp_path):
    database_path = tmp_path / "collection.sqlite3"
    raw_root = tmp_path / "raw"
    database_url = f"sqlite:///{database_path.as_posix()}"
    settings = Settings(
        database_url=database_url,
        collection_raw_dir=str(raw_root),
        collection_baseline_wall_seconds=60,
        collection_baseline_min_clean_seconds=30,
        collection_rest_min_seconds=10,
        collection_rest_max_seconds=15,
    )
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    clock = DeterministicClock()

    with factory() as db:
        participant = DatasetParticipant(
            participant_code="P9001",
            consent_confirmed_at=clock.now(),
            state=ParticipantState.active,
        )
        db.add(participant)
        db.flush()
        collection_session = CollectionSession(participant_id=participant.id)
        db.add(collection_session)
        for quadrant in Quadrant:
            for index in range(3):
                token = f"{quadrant.value}-{index}"
                db.add(
                    EmotionStimulus(
                        title=token,
                        file_path=f"{token}.mp4",
                        checksum=hashlib.sha256(token.encode("utf-8")).hexdigest(),
                        duration_seconds=45,
                        target_quadrant=quadrant,
                        approval_state=StimulusApprovalState.approved,
                        stimulus_set_version="integration-v1",
                    )
                )
        db.commit()
        runner = CollectionStateMachine(
            db,
            collection_session,
            writer_factory=lambda marker_clock: AtomicEEGWriter(raw_root, clock=marker_clock),
            monotonic=clock.monotonic,
            now=clock.now,
            settings=settings,
        )
        runner.select_device("fake-muse", "Fake Muse")
        create_trial_schedule(db, collection_session, seed=9001)
        initial_schedule = _schedule(db, collection_session)
        session_id = collection_session.id

        _finish_baseline(runner, clock, BaselineKind.eyes_open)
        _finish_baseline(runner, clock, BaselineKind.eyes_closed)
        assert collection_session.eyes_open_wall_clock_seconds == pytest.approx(60.0)
        assert collection_session.eyes_closed_wall_clock_seconds == pytest.approx(60.0)
        assert collection_session.eyes_open_accepted_clean_seconds >= 30.0
        assert collection_session.eyes_closed_accepted_clean_seconds >= 30.0

        first_state = runner.start_trial_rest()
        first_trial_id = first_state.current_trial_id
        clock.advance(0.01)
        _accept_sample(runner, clock)
        clock.advance(9.99)
        runner.start_stimulus(first_trial_id)
        clock.advance(0.01)
        _accept_sample(runner, clock)
        clock.advance(44.99)
        runner.finish_stimulus(first_trial_id)
        clock.advance(0.01)
        _accept_sample(runner, clock)
        runner.submit_rating(first_trial_id, valence=8, arousal=7, confidence=5)

        first_trial = db.get(CollectionTrial, first_trial_id)
        final_path = raw_root / Path(first_trial.eeg_file_path)
        raw_bytes = final_path.read_bytes()
        with final_path.open(encoding="utf-8", newline="") as raw_file:
            markers = [row["marker"] for row in csv.DictReader(raw_file) if row["marker"]]
        assert first_trial.state is TrialState.completed
        assert first_trial.eeg_checksum == hashlib.sha256(raw_bytes).hexdigest()
        assert first_trial.raw_size_bytes == len(raw_bytes)
        assert markers == [
            "rest_start",
            "rest_end",
            "stimulus_start",
            "stimulus_end",
            "rating_start",
            "rating_end",
        ]

        clock.advance(20.0)
        second_state = runner.start_trial_rest()
        second_trial_id = second_state.current_trial_id
        assert second_state.current_trial_order == 2
        clock.advance(0.01)
        _accept_sample(runner, clock)
        runner.interrupt("integration restart")
        assert db.get(CollectionTrial, second_trial_id).state is TrialState.interrupted

    engine.dispose()

    recreated_engine = create_engine(database_url)
    recreated_factory = sessionmaker(bind=recreated_engine, expire_on_commit=False)
    with recreated_factory() as db:
        collection_session = db.get(CollectionSession, session_id)
        recovered = CollectionStateMachine.recover(
            db,
            collection_session,
            writer_factory=lambda marker_clock: AtomicEEGWriter(raw_root, clock=marker_clock),
            monotonic=clock.monotonic,
            now=clock.now,
            settings=settings,
        )
        recovered.resume()
        resumed = recovered.start_trial_rest()
        assert resumed.current_trial_id == second_trial_id
        assert resumed.current_trial_order == 2
        assert _schedule(db, collection_session) == initial_schedule
        recovered.interrupt("integration cleanup")

    recreated_engine.dispose()
