from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.config import Settings
from app.database import Base
from app.models.dataset_collection import (
    ArtifactEvent,
    BaselineKind,
    CollectionSession,
    CollectionSessionState,
    CollectionTrial,
    DatasetParticipant,
    EmotionStimulus,
    ParticipantState,
    Quadrant,
    StimulusApprovalState,
    TrialState,
)
from app.services.collection_state_machine import (
    CollectionPersistenceError,
    CollectionStateError,
    CollectionStateMachine,
    InvalidTransitionError,
)
from app.services.raw_eeg_writer import AtomicEEGWriter, EEGSample, RawFileResult
from app.services.trial_scheduler import create_trial_schedule


class Clock:
    def __init__(self):
        self.value = 1_000.0
        self.wall = datetime(2026, 7, 19, 10, 0, 0)

    def monotonic(self):
        return self.value

    def now(self):
        return self.wall + timedelta(seconds=self.value - 1_000.0)

    def advance(self, seconds):
        self.value += seconds


class FakeWriter:
    def __init__(self, events, *, fail_finalize=False):
        self.events = events
        self.fail_finalize = fail_finalize
        self.samples = []
        self.path = None
        self.fail_append = False
        self.fail_marker = None
        self.fail_abort = False

    def start(self, path):
        self.path = tuple(path)
        self.events.append(("start", self.path))

    def append(self, sample):
        if self.fail_append:
            raise OSError("stream write failed")
        self.samples.append(sample)

    def mark(self, marker):
        if marker == self.fail_marker:
            raise OSError("marker write failed")
        self.events.append(("marker", marker))

    def finalize(self):
        self.events.append(("finalize", self.path))
        if self.fail_finalize:
            raise OSError("disk failed")
        return RawFileResult("/".join(self.path) + ".csv", "a" * 64, 123, len(self.samples), None, None)

    def abort(self):
        self.events.append(("abort", self.path))
        if self.fail_abort:
            raise OSError("abort failed")


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


@pytest.fixture
def setup_runner(db):
    participant = DatasetParticipant(
        participant_code="P001",
        consent_confirmed_at=datetime(2026, 7, 19),
        state=ParticipantState.active,
    )
    db.add(participant)
    db.flush()
    session = CollectionSession(participant_id=participant.id)
    db.add(session)
    for quadrant in Quadrant:
        for index in range(3):
            db.add(EmotionStimulus(
                title=f"{quadrant.value}-{index}",
                file_path=f"{quadrant.value}-{index}.mp4",
                checksum=f"{quadrant.value}-{index}".ljust(64, "0"),
                duration_seconds=45,
                target_quadrant=quadrant,
                approval_state=StimulusApprovalState.approved,
                stimulus_set_version="v1",
            ))
    db.commit()
    create_trial_schedule(db, session, seed=7)
    clock = Clock()
    events = []
    writers = []

    def factory(marker_clock=None):
        writer = FakeWriter(events)
        writers.append(writer)
        return writer

    runner = CollectionStateMachine(
        db, session, writer_factory=factory, monotonic=clock.monotonic, now=clock.now
    )
    return runner, session, clock, events, writers


def good_sample(timestamp):
    return EEGSample(timestamp, 1, 2, 3, 4, 80, 80, 80, 80)


def finish_baseline(runner, clock, kind):
    runner.start_baseline(kind)
    runner.accept_sample(good_sample(clock.value), sensor_timestamps={name: clock.value for name in ("tp9", "af7", "af8", "tp10")})
    for _ in range(30):
        clock.advance(1)
        runner.accept_sample(good_sample(clock.value), sensor_timestamps={name: clock.value for name in ("tp9", "af7", "af8", "tp10")})
    clock.advance(30)
    return runner.finish_baseline()


def prepare_ready(runner, clock):
    runner.select_device("muse-1", "Muse 2")
    finish_baseline(runner, clock, BaselineKind.eyes_open)
    finish_baseline(runner, clock, BaselineKind.eyes_closed)


def test_happy_path_reaches_second_trial_rest(setup_runner):
    runner, session, clock, events, _ = setup_runner
    prepare_ready(runner, clock)
    first = runner.start_trial_rest()
    clock.advance(10)
    runner.start_stimulus(first.current_trial_id)
    clock.advance(45)
    runner.finish_stimulus(first.current_trial_id)
    runner.submit_rating(first.current_trial_id, valence=8, arousal=7, confidence=4)
    clock.advance(20)
    second = runner.start_trial_rest()

    assert session.state is CollectionSessionState.in_progress
    assert second.current_trial_order == 2
    assert second.trial_state is TrialState.rest
    assert session.completed_trials == 1
    assert [event[1] for event in events if event[0] == "marker"] == [
        "baseline_eyes_open_start", "baseline_eyes_open_end",
        "baseline_eyes_closed_start", "baseline_eyes_closed_end",
        "rest_start", "rest_end", "stimulus_start", "stimulus_end", "rating_start", "rating_end",
        "rest_start",
    ]


def test_invalid_transition_is_rejected_without_commit(setup_runner):
    runner, session, _, _, _ = setup_runner
    with pytest.raises(InvalidTransitionError):
        runner.start_trial_rest()
    assert session.state is CollectionSessionState.preparation


def test_clean_time_requires_all_four_good_and_fresh_sensors(setup_runner):
    runner, _, clock, _, _ = setup_runner
    runner.select_device("muse-1", "Muse 2")
    runner.start_baseline(BaselineKind.eyes_open)
    names = ("tp9", "af7", "af8", "tp10")
    runner.accept_sample(good_sample(clock.value), sensor_timestamps={n: clock.value for n in names})
    clock.advance(5)
    poor = EEGSample(clock.value, 1, 2, 3, 4, 80, 80, 59, 80)
    runner.accept_sample(poor, sensor_timestamps={n: clock.value for n in names})
    clock.advance(5)
    runner.accept_sample(good_sample(clock.value), sensor_timestamps={**{n: clock.value for n in names}, "tp10": clock.value - 3})
    clock.advance(5)
    runner.accept_sample(good_sample(clock.value), sensor_timestamps={n: clock.value for n in names})
    clock.advance(1)
    state = runner.accept_sample(good_sample(clock.value), sensor_timestamps={n: clock.value for n in names})
    assert state.accepted_clean_seconds == 1
    assert state.wall_clock_seconds == 16


def test_baseline_needs_sixty_wall_and_thirty_clean_seconds(setup_runner):
    runner, _, clock, _, _ = setup_runner
    runner.select_device("muse-1", "Muse 2")
    runner.start_baseline(BaselineKind.eyes_open)
    runner.accept_sample(good_sample(clock.value), sensor_timestamps={n: clock.value for n in ("tp9", "af7", "af8", "tp10")})
    clock.advance(29)
    runner.accept_sample(good_sample(clock.value), sensor_timestamps={n: clock.value for n in ("tp9", "af7", "af8", "tp10")})
    clock.advance(31)
    with pytest.raises(InvalidTransitionError, match="clean"):
        runner.finish_baseline()


def test_artifact_and_derived_ratings_are_persisted(db, setup_runner):
    runner, _, clock, _, _ = setup_runner
    prepare_ready(runner, clock)
    state = runner.start_trial_rest()
    clock.advance(10)
    runner.start_stimulus(state.current_trial_id)
    runner.mark_artifact(state.current_trial_id, "blink", start_seconds=2.5, duration_seconds=0.4, details={"source": "admin"})
    clock.advance(45)
    runner.finish_stimulus(state.current_trial_id)
    runner.submit_rating(state.current_trial_id, valence=8, arousal=3, confidence=4)

    trial = db.get(CollectionTrial, state.current_trial_id)
    artifact = db.scalar(select(ArtifactEvent).where(ArtifactEvent.trial_id == trial.id))
    assert (trial.valence_label, trial.arousal_label) == (True, False)
    assert (trial.valid_valence_label, trial.valid_arousal_label) == (True, True)
    assert artifact.event_type == "blink"
    assert '"source": "admin"' in artifact.details_json


def test_writer_finalizes_before_trial_can_complete(setup_runner):
    runner, _, clock, events, _ = setup_runner
    prepare_ready(runner, clock)
    state = runner.start_trial_rest()
    clock.advance(10)
    runner.start_stimulus(state.current_trial_id)
    clock.advance(45)
    runner.finish_stimulus(state.current_trial_id)
    runner.submit_rating(state.current_trial_id, valence=7, arousal=7, confidence=5)
    assert next(i for i, e in enumerate(events) if e == ("marker", "rating_end")) < next(
        i for i, e in enumerate(events) if e[0] == "finalize" and "trial" in e[1][2]
    )


def test_finalize_failure_marks_trial_failed_and_does_not_complete(setup_runner):
    runner, session, clock, _, writers = setup_runner
    prepare_ready(runner, clock)
    state = runner.start_trial_rest()
    writers[-1].fail_finalize = True
    clock.advance(10)
    runner.start_stimulus(state.current_trial_id)
    clock.advance(45)
    runner.finish_stimulus(state.current_trial_id)
    with pytest.raises(OSError, match="disk failed"):
        runner.submit_rating(state.current_trial_id, valence=7, arousal=7, confidence=5)
    trial = runner.db.get(CollectionTrial, state.current_trial_id)
    assert trial.state is TrialState.failed
    assert session.completed_trials == 0
    assert session.state is CollectionSessionState.failed


def test_db_failure_after_finalize_retains_file_and_marks_recovery(setup_runner, monkeypatch):
    runner, session, clock, events, _ = setup_runner
    prepare_ready(runner, clock)
    state = runner.start_trial_rest()
    clock.advance(10)
    runner.start_stimulus(state.current_trial_id)
    clock.advance(45)
    runner.finish_stimulus(state.current_trial_id)
    real_commit = runner.db.commit
    attempts = 0

    def fail_once():
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("database unavailable")
        real_commit()

    monkeypatch.setattr(runner.db, "commit", fail_once)
    with pytest.raises(CollectionPersistenceError, match="metadata commit failed"):
        runner.submit_rating(state.current_trial_id, valence=7, arousal=7, confidence=5)

    trial = runner.db.get(CollectionTrial, state.current_trial_id)
    assert any(event[0] == "finalize" and "trial" in event[1][2] for event in events)
    assert trial.state is TrialState.interrupted
    assert trial.failure_reason == "Trial file finalized but metadata commit failed"
    assert (trial.eeg_file_path, trial.eeg_checksum, trial.raw_size_bytes) == (
        f"P001/{session.id}/trial-{trial.id}.csv",
        "a" * 64,
        123,
    )
    assert runner.session.state is CollectionSessionState.interrupted
    assert runner.state().file_recovery_required is True

    recreated = CollectionStateMachine(
        runner.db,
        runner.session,
        writer_factory=lambda marker_clock: FakeWriter([]),
        monotonic=clock.monotonic,
        now=clock.now,
    )
    assert recreated.state().file_recovery_required is True
    assert recreated.resume().file_recovery_required is False


def test_baseline_metadata_commit_failure_survives_recreation(setup_runner, monkeypatch):
    runner, session, clock, _, _ = setup_runner
    runner.select_device("muse-1", "Muse 2")
    runner.start_baseline(BaselineKind.eyes_open)
    runner.accept_sample(good_sample(clock.value))
    for _ in range(30):
        clock.advance(1)
        runner.accept_sample(good_sample(clock.value))
    clock.advance(30)
    real_commit = runner.db.commit
    attempts = 0

    def fail_once():
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("database unavailable")
        real_commit()

    monkeypatch.setattr(runner.db, "commit", fail_once)
    with pytest.raises(CollectionPersistenceError, match="metadata commit failed"):
        runner.finish_baseline()

    recreated = CollectionStateMachine(
        runner.db,
        runner.session,
        writer_factory=lambda marker_clock: FakeWriter([]),
        monotonic=clock.monotonic,
        now=clock.now,
    )
    assert recreated.state().file_recovery_required is True
    assert recreated.session.eyes_open_baseline_path is not None
    resumed = recreated.resume()
    assert resumed.file_recovery_required is False
    assert resumed.state is CollectionSessionState.preparation


def test_interrupt_aborts_partial_and_persists_reason(setup_runner):
    runner, session, clock, events, _ = setup_runner
    prepare_ready(runner, clock)
    state = runner.start_trial_rest()
    interrupted = runner.interrupt("Muse disconnected")
    assert ("abort", ("P001", str(session.id), f"trial-{state.current_trial_id}")) in events
    assert interrupted.state is CollectionSessionState.interrupted
    assert interrupted.interruption_reason == "Muse disconnected"
    assert runner.db.get(CollectionTrial, state.current_trial_id).state is TrialState.interrupted


def test_restart_recovery_interrupts_in_flight_and_resume_keeps_order(db, setup_runner):
    runner, session, clock, _, _ = setup_runner
    prepare_ready(runner, clock)
    first = runner.start_trial_rest()
    original_order = [t.stimulus_id for t in db.scalars(select(CollectionTrial).where(CollectionTrial.session_id == session.id).order_by(CollectionTrial.randomized_order))]

    recovered = CollectionStateMachine.recover(db, session, writer_factory=lambda marker_clock: FakeWriter([]), monotonic=clock.monotonic, now=clock.now)
    assert recovered.state().state is CollectionSessionState.interrupted
    resumed = recovered.resume()
    after_order = [t.stimulus_id for t in db.scalars(select(CollectionTrial).where(CollectionTrial.session_id == session.id).order_by(CollectionTrial.randomized_order))]
    assert resumed.next_trial_order == first.current_trial_order
    assert after_order == original_order


def test_restart_uses_a_new_pseudonymous_attempt_path_when_old_partial_exists(db, setup_runner):
    runner, session, clock, events, _ = setup_runner
    prepare_ready(runner, clock)
    active = runner.start_trial_rest()
    old_path = next(event[1] for event in reversed(events) if event[0] == "start")
    occupied_partial_paths = {old_path}
    restarted_paths = []

    class CollisionCheckingWriter(FakeWriter):
        def start(self, path):
            path = tuple(path)
            if path in occupied_partial_paths:
                raise FileExistsError("old partial exists")
            restarted_paths.append(path)
            super().start(path)

    recovered = CollectionStateMachine.recover(
        db,
        session,
        writer_factory=lambda marker_clock: CollisionCheckingWriter([]),
        monotonic=clock.monotonic,
        now=clock.now,
    )
    recovered.resume()
    restarted = recovered.start_trial_rest()

    assert restarted.current_trial_order == active.current_trial_order
    assert restarted_paths[0] != old_path
    assert restarted_paths[0][:2] == ("P001", str(session.id))
    assert restarted_paths[0][2].startswith(f"trial-{active.current_trial_id}-recovery-")
    assert old_path in occupied_partial_paths


def test_restart_can_restart_same_baseline_without_touching_old_partial(db, setup_runner):
    runner, session, clock, events, _ = setup_runner
    runner.select_device("muse-1", "Muse 2")
    runner.start_baseline(BaselineKind.eyes_open)
    old_path = next(event[1] for event in reversed(events) if event[0] == "start")
    restarted_paths = []

    class CollisionCheckingWriter(FakeWriter):
        def start(self, path):
            path = tuple(path)
            if path == old_path:
                raise FileExistsError("old partial exists")
            restarted_paths.append(path)
            super().start(path)

    recovered = CollectionStateMachine.recover(
        db,
        session,
        writer_factory=lambda marker_clock: CollisionCheckingWriter([]),
        monotonic=clock.monotonic,
        now=clock.now,
    )
    resumed = recovered.resume()
    assert resumed.active_baseline is None
    restarted = recovered.start_baseline(BaselineKind.eyes_open)

    assert restarted.active_baseline is BaselineKind.eyes_open
    assert restarted_paths[0] != old_path
    assert restarted_paths[0][2].startswith("baseline-eyes_open-recovery-")


def test_break_after_six_and_session_completes_after_twelve(setup_runner):
    runner, session, clock, _, _ = setup_runner
    prepare_ready(runner, clock)
    for order in range(1, 13):
        state = runner.start_trial_rest()
        clock.advance(10)
        runner.start_stimulus(state.current_trial_id)
        clock.advance(45)
        runner.finish_stimulus(state.current_trial_id)
        done = runner.submit_rating(state.current_trial_id, valence=7, arousal=7, confidence=5)
        if order == 6:
            assert done.break_required is True
        if order < 12:
            clock.advance(20)
    assert done.state is CollectionSessionState.completed
    assert session.completed_trials == 12
    assert session.completed_at is not None


def test_start_rest_commit_failure_aborts_partial_and_persists_interruption(setup_runner, monkeypatch):
    runner, _, clock, events, _ = setup_runner
    prepare_ready(runner, clock)
    real_commit = runner.db.commit
    attempts = 0

    def fail_once():
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("commit failed")
        real_commit()

    monkeypatch.setattr(runner.db, "commit", fail_once)
    with pytest.raises(CollectionPersistenceError):
        runner.start_trial_rest()

    assert any(event[0] == "abort" and "trial" in event[1][2] for event in events)
    assert runner.session.state is CollectionSessionState.interrupted
    interrupted_trial_id = runner.session.current_trial_id
    assert runner.db.get(CollectionTrial, interrupted_trial_id).state is TrialState.interrupted
    runner.resume()
    retried = runner.start_trial_rest()
    assert retried.current_trial_order == 1
    assert any(event[0] == "start" and "-recovery-" in event[1][2] for event in events)


def test_start_baseline_commit_failure_aborts_partial_and_can_retry(setup_runner, monkeypatch):
    runner, _, _, events, _ = setup_runner
    runner.select_device("muse-1", "Muse 2")
    real_commit = runner.db.commit
    attempts = 0

    def fail_once():
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("commit failed")
        real_commit()

    monkeypatch.setattr(runner.db, "commit", fail_once)
    with pytest.raises(CollectionPersistenceError):
        runner.start_baseline(BaselineKind.eyes_open)
    assert any(event[0] == "abort" and "baseline-eyes_open" in event[1][2] for event in events)
    assert runner.session.state is CollectionSessionState.interrupted
    runner.resume()
    restarted = runner.start_baseline(BaselineKind.eyes_open)
    assert restarted.active_baseline is BaselineKind.eyes_open


def test_marker_write_failure_aborts_partial_and_interrupts(setup_runner):
    runner, _, clock, events, writers = setup_runner
    prepare_ready(runner, clock)
    state = runner.start_trial_rest()
    writers[-1].fail_marker = "stimulus_start"
    clock.advance(10)
    with pytest.raises(OSError, match="marker write failed"):
        runner.start_stimulus(state.current_trial_id)
    assert any(event[0] == "abort" for event in events)
    assert runner.db.get(CollectionTrial, state.current_trial_id).state is TrialState.interrupted
    assert runner.session.state is CollectionSessionState.interrupted


def test_marker_transition_commit_failure_aborts_partial_and_does_not_advance(setup_runner, monkeypatch):
    runner, _, clock, events, _ = setup_runner
    prepare_ready(runner, clock)
    state = runner.start_trial_rest()
    clock.advance(10)
    real_commit = runner.db.commit
    attempts = 0

    def fail_once():
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("commit failed")
        real_commit()

    monkeypatch.setattr(runner.db, "commit", fail_once)
    with pytest.raises(CollectionPersistenceError):
        runner.start_stimulus(state.current_trial_id)

    assert ("marker", "stimulus_start") in events
    assert any(event[0] == "abort" for event in events)
    assert runner.db.get(CollectionTrial, state.current_trial_id).state is TrialState.interrupted
    assert runner.session.state is CollectionSessionState.interrupted


def test_append_failure_aborts_and_interrupts_active_trial(setup_runner):
    runner, _, clock, events, writers = setup_runner
    prepare_ready(runner, clock)
    state = runner.start_trial_rest()
    writers[-1].fail_append = True

    with pytest.raises(OSError, match="stream write failed"):
        runner.accept_sample(good_sample(clock.value))

    assert any(event[0] == "abort" for event in events)
    assert runner.db.get(CollectionTrial, state.current_trial_id).state is TrialState.interrupted
    assert runner.session.state is CollectionSessionState.interrupted


@pytest.mark.parametrize(
    "terminal",
    [CollectionSessionState.completed, CollectionSessionState.failed, CollectionSessionState.withdrawn],
)
def test_interrupt_never_regresses_terminal_session(setup_runner, terminal):
    runner, session, _, _, _ = setup_runner
    session.state = terminal
    runner.db.commit()
    with pytest.raises(InvalidTransitionError):
        runner.interrupt("late disconnect")
    assert session.state is terminal


def test_interrupt_rejects_inactive_ready_session(setup_runner):
    runner, session, clock, _, _ = setup_runner
    prepare_ready(runner, clock)
    with pytest.raises(InvalidTransitionError):
        runner.interrupt("not actually active")
    assert session.state is CollectionSessionState.ready


def test_baseline_interrupt_commit_failure_still_persists_recovery(setup_runner, monkeypatch):
    runner, _, _, events, _ = setup_runner
    runner.select_device("muse-1", "Muse 2")
    runner.start_baseline(BaselineKind.eyes_open)
    real_commit = runner.db.commit
    attempts = 0

    def fail_once():
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("commit failed")
        real_commit()

    monkeypatch.setattr(runner.db, "commit", fail_once)
    with pytest.raises(CollectionPersistenceError):
        runner.interrupt("Muse disconnected")

    assert any(event[0] == "abort" for event in events)
    assert runner.session.state is CollectionSessionState.interrupted
    assert runner.session.active_baseline is None
    runner.resume()
    assert runner.start_baseline(BaselineKind.eyes_open).active_baseline is BaselineKind.eyes_open


def test_trial_interrupt_commit_failure_still_persists_recovery(setup_runner, monkeypatch):
    runner, _, clock, events, _ = setup_runner
    prepare_ready(runner, clock)
    active = runner.start_trial_rest()
    real_commit = runner.db.commit
    attempts = 0

    def fail_once():
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("commit failed")
        real_commit()

    monkeypatch.setattr(runner.db, "commit", fail_once)
    with pytest.raises(CollectionPersistenceError):
        runner.interrupt("Muse disconnected")

    assert any(event[0] == "abort" for event in events)
    trial = runner.db.get(CollectionTrial, active.current_trial_id)
    assert trial.state is TrialState.interrupted
    assert runner.session.state is CollectionSessionState.interrupted
    runner.resume()
    assert runner.start_trial_rest().current_trial_order == active.current_trial_order


def test_interrupt_abort_failure_clears_writer_and_persists_safe_state(setup_runner):
    runner, _, clock, _, writers = setup_runner
    prepare_ready(runner, clock)
    active = runner.start_trial_rest()
    writers[-1].fail_abort = True

    with pytest.raises(CollectionStateError, match="cleanly aborted"):
        runner.interrupt("Muse disconnected")

    assert runner.session.state is CollectionSessionState.interrupted
    assert "abort failed" in runner.session.interruption_reason
    assert runner.db.get(CollectionTrial, active.current_trial_id).state is TrialState.interrupted
    with pytest.raises(InvalidTransitionError):
        runner.interrupt("duplicate")


def test_recover_preserves_valid_between_trial_post_rating_rest(setup_runner):
    runner, session, clock, _, _ = setup_runner
    prepare_ready(runner, clock)
    first = runner.start_trial_rest()
    clock.advance(10)
    runner.start_stimulus(first.current_trial_id)
    clock.advance(45)
    runner.finish_stimulus(first.current_trial_id)
    runner.submit_rating(first.current_trial_id, valence=7, arousal=7, confidence=5)

    recovered = CollectionStateMachine.recover(
        runner.db,
        session,
        writer_factory=lambda marker_clock: FakeWriter([]),
        monotonic=clock.monotonic,
        now=clock.now,
    )
    state = recovered.state()
    assert state.state is CollectionSessionState.in_progress
    assert state.current_trial_id is None
    assert state.interruption_reason is None
    clock.advance(20)
    assert recovered.start_trial_rest().current_trial_order == 2


def test_rest_and_stimulus_enforce_early_and_late_bounds(setup_runner):
    runner, _, clock, _, _ = setup_runner
    prepare_ready(runner, clock)
    state = runner.start_trial_rest()
    clock.advance(9.9)
    with pytest.raises(InvalidTransitionError, match="10"):
        runner.start_stimulus(state.current_trial_id)
    clock.advance(5.2)
    with pytest.raises(InvalidTransitionError, match="15"):
        runner.start_stimulus(state.current_trial_id)
    assert runner.session.state is CollectionSessionState.interrupted

    runner.resume()
    state = runner.start_trial_rest()
    clock.advance(10)
    runner.start_stimulus(state.current_trial_id)
    clock.advance(44.9)
    with pytest.raises(InvalidTransitionError, match="45"):
        runner.finish_stimulus(state.current_trial_id)
    clock.advance(15.2)
    with pytest.raises(InvalidTransitionError, match="60"):
        runner.finish_stimulus(state.current_trial_id)
    assert runner.session.state is CollectionSessionState.interrupted


def test_post_rating_rest_blocks_early_start_and_records_late_protocol_deviation(setup_runner):
    runner, _, clock, _, _ = setup_runner
    prepare_ready(runner, clock)
    first = runner.start_trial_rest()
    clock.advance(10)
    runner.start_stimulus(first.current_trial_id)
    clock.advance(45)
    runner.finish_stimulus(first.current_trial_id)
    runner.submit_rating(first.current_trial_id, valence=7, arousal=7, confidence=5)
    clock.advance(19.9)
    with pytest.raises(InvalidTransitionError, match="20"):
        runner.start_trial_rest()
    clock.advance(10.2)
    second = runner.start_trial_rest()
    trial = runner.db.get(CollectionTrial, second.current_trial_id)
    assert "exceeded 30" in trial.failure_reason


def test_atomic_writer_uses_injected_backend_clock_for_markers_and_samples(tmp_path, db, setup_runner):
    _, session, clock, _, _ = setup_runner
    runner = CollectionStateMachine(
        db,
        session,
        writer_factory=lambda marker_clock: AtomicEEGWriter(tmp_path, clock=marker_clock),
        monotonic=clock.monotonic,
        now=clock.now,
    )
    runner.select_device("muse-1", "Muse 2")
    runner.start_baseline(BaselineKind.eyes_open)
    clock.advance(0.01)
    runner.accept_sample(
        good_sample(-999),
        sensor_timestamps={name: clock.value for name in ("tp9", "af7", "af8", "tp10")},
    )
    runner.interrupt("test cleanup")


def test_atomic_writer_orders_adjacent_phase_markers_and_sample_with_coarse_clock(tmp_path, db, setup_runner):
    _, session, clock, _, _ = setup_runner
    preparation_runner = CollectionStateMachine(
        db,
        session,
        writer_factory=lambda marker_clock: FakeWriter([]),
        monotonic=clock.monotonic,
        now=clock.now,
    )
    prepare_ready(preparation_runner, clock)
    runner = CollectionStateMachine(
        db,
        session,
        writer_factory=lambda marker_clock: AtomicEEGWriter(tmp_path, clock=marker_clock),
        monotonic=clock.monotonic,
        now=clock.now,
    )
    active = runner.start_trial_rest()
    clock.advance(10)

    # rest_end and stimulus_start are adjacent Backend-owned markers. The
    # coarse clock intentionally does not advance between them or the sample.
    runner.start_stimulus(active.current_trial_id)
    runner.accept_sample(
        good_sample(-999),
        sensor_timestamps={name: clock.value for name in ("tp9", "af7", "af8", "tp10")},
    )

    assert runner.state().trial_state is TrialState.stimulus
    runner.interrupt("test cleanup")


def test_runner_consumes_collection_rest_timing_settings(db, setup_runner):
    _, session, clock, _, _ = setup_runner
    base_runner = CollectionStateMachine(
        db,
        session,
        writer_factory=lambda marker_clock: FakeWriter([]),
        monotonic=clock.monotonic,
        now=clock.now,
    )
    prepare_ready(base_runner, clock)
    configured = CollectionStateMachine(
        db,
        session,
        writer_factory=lambda marker_clock: FakeWriter([]),
        monotonic=clock.monotonic,
        now=clock.now,
        settings=Settings(collection_rest_min_seconds=2, collection_rest_max_seconds=3),
    )
    state = configured.start_trial_rest()
    clock.advance(2)
    assert configured.start_stimulus(state.current_trial_id).trial_state is TrialState.stimulus
