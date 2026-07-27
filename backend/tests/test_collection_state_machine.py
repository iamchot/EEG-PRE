import asyncio
from datetime import datetime, timedelta
import json
import sys
import threading

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
from app.services.muse_stream import LSLMuseStreamSource, MuseQualityObservation
from app.services.raw_eeg_writer import AtomicEEGWriter, EEGSample, RawFileResult
from app.services.signal_processor import SensorQuality
from app.services.trial_scheduler import create_trial_schedule
from app.ws.collection_manager import CollectionConnectionManager


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
    clock.advance(0.001)
    runner.accept_sample(good_sample(clock.value), sensor_timestamps={name: clock.value for name in ("tp9", "af7", "af8", "tp10")})
    for _ in range(30):
        clock.advance(1)
        runner.accept_sample(good_sample(clock.value), sensor_timestamps={name: clock.value for name in ("tp9", "af7", "af8", "tp10")})
    clock.advance(29.999)
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


def test_stimulus_counters_reset_after_rest_and_persist_derived_coverage_qc(setup_runner, db):
    runner, _, clock, _, _ = setup_runner
    prepare_ready(runner, clock)
    state = runner.start_trial_rest()
    names = ("tp9", "af7", "af8", "tp10")
    runner.accept_sample(good_sample(clock.value), sensor_timestamps={n: clock.value for n in names}, sampling_rate_ok=True)
    clock.advance(10)
    runner.accept_sample(good_sample(clock.value), sensor_timestamps={n: clock.value for n in names}, sampling_rate_ok=True)
    assert runner.state().accepted_clean_seconds == 0

    runner.start_stimulus(state.current_trial_id)
    assert runner.state().accepted_clean_seconds == 0
    clock.advance(0.001)
    for _ in range(46):
        runner.accept_sample(good_sample(clock.value), sensor_timestamps={n: clock.value for n in names}, sampling_rate_ok=True)
        clock.advance(1)
    runner.finish_stimulus(state.current_trial_id)

    trial = db.get(CollectionTrial, state.current_trial_id)
    qc = json.loads(trial.qc_summary_json)
    assert trial.wall_clock_seconds == pytest.approx(46.001)
    assert trial.accepted_clean_seconds == pytest.approx(45)
    assert qc["quality_source"] == "derived_eeg_window"
    assert qc["valid_signal"] is True
    assert qc["af7_good_coverage"] >= 0.8
    assert qc["af8_good_coverage"] >= 0.8


def test_out_of_tolerance_sampling_never_accrues_clean_time(setup_runner):
    runner, _, clock, _, _ = setup_runner
    runner.select_device("muse-1", "Muse 2")
    runner.start_baseline(BaselineKind.eyes_open)
    names = ("tp9", "af7", "af8", "tp10")
    runner.accept_sample(good_sample(clock.value), sensor_timestamps={n: clock.value for n in names}, sampling_rate_ok=False)
    clock.advance(1)
    state = runner.accept_sample(good_sample(clock.value), sensor_timestamps={n: clock.value for n in names}, sampling_rate_ok=False)
    assert state.accepted_clean_seconds == 0


def test_live_readiness_uses_backend_observation_age_without_replacing_source_timestamps(setup_runner):
    runner, _, clock, _, _ = setup_runner
    source_timestamp = 50_000.0
    sensors = {
        name: SensorQuality(state="good", quality_score=80, timestamp=source_timestamp)
        for name in ("tp9", "af7", "af8", "tp10")
    }
    state = runner.observe_quality(sensors, sampling_rate_hz=256, sampling_rate_ok=True)
    assert state.live_sensor_ready is True
    assert {sensor.timestamp for sensor in state.sensors.values()} == {source_timestamp}
    clock.advance(2.1)
    assert runner.state().live_sensor_ready is False


def test_readiness_recomputes_rate_and_sensor_state_from_typed_observation(setup_runner):
    runner, _, _, _, _ = setup_runner
    asserted_good = {
        name: SensorQuality(state="good", quality_score=80, timestamp=50_000)
        for name in ("tp9", "af7", "af8", "tp10")
    }
    spoofed_rate = MuseQualityObservation(asserted_good, 1.0, 1, 50_000, 0.0, True)
    assert runner.observe_quality(spoofed_rate).live_sensor_ready is False

    low_score = {
        name: SensorQuality(state="good", quality_score=80, timestamp=50_001)
        for name in ("tp9", "af7", "af8", "tp10")
    }
    low_score["af7"] = SensorQuality(state="good", quality_score=10, timestamp=50_001)
    spoofed_state = MuseQualityObservation(low_score, 256.0, 2, 50_001, 0.0, True)
    state = runner.observe_quality(spoofed_state)
    assert state.live_sensor_ready is False
    assert state.sensors["af7"].state == "poor"


def test_adapter_invalid_cadence_observation_cannot_be_normalized_back_to_ready(setup_runner):
    runner, _, _, _, _ = setup_runner
    source_clock = [100.0]
    source = LSLMuseStreamSource(clock=lambda: source_clock[0])
    source._channel_names = ("TP9", "AF7", "AF8", "TP10")
    for index in range(16):
        source_clock[0] = 100.0 + index / 256
        mapped = source.map_sample(
            [35.0 * ((index % 4) - 1.5)] * 4,
            source_clock[0],
        )
    assert mapped.sampling_rate_ok is True

    duplicate = source.map_sample([35.0, -35.0, 35.0, -35.0], source_clock[0])
    assert duplicate.sampling_rate_hz == pytest.approx(256.0)
    assert duplicate.sampling_rate_ok is False

    state = runner.observe_quality(duplicate.quality_observation)

    assert state.sampling_rate_ok is False
    assert state.live_sensor_ready is False
    assert all(sensor.state == "poor" for sensor in state.sensors.values())


def test_binding_new_source_clears_previous_readiness_until_new_observation(setup_runner):
    runner, _, _, _, _ = setup_runner
    sensors = {
        name: SensorQuality(state="good", quality_score=80, timestamp=50_000)
        for name in ("tp9", "af7", "af8", "tp10")
    }
    assert runner.observe_quality(
        sensors,
        sampling_rate_hz=256,
        sampling_rate_ok=True,
    ).live_sensor_ready is True

    runner.bind_source(lambda: 60_000.0, lambda: 0)
    state = runner.state()

    assert state.live_sensor_ready is False
    assert state.sampling_rate_hz is None
    assert state.sampling_rate_ok is False
    assert all(sensor.state == "unknown" for sensor in state.sensors.values())


def test_bound_source_rejects_stale_source_domain_observation(setup_runner):
    runner, _, _, _, _ = setup_runner
    runner.bind_source(lambda: 60_000.0, lambda: 1)
    sensors = {
        name: SensorQuality(state="good", quality_score=80, timestamp=59_990.0)
        for name in ("tp9", "af7", "af8", "tp10")
    }
    stale = MuseQualityObservation(
        sensors,
        256.0,
        1,
        59_990.0,
        59_990.0,
        True,
    )

    state = runner.observe_quality(stale)

    assert state.live_sensor_ready is False
    assert state.sampling_rate_ok is False
    assert all(sensor.state == "stale" for sensor in state.sensors.values())


def test_source_sequence_watermark_uses_bound_lsl_clock_and_fails_unorderable_post_boundary(setup_runner):
    runner, session, clock, _, writers = setup_runner
    source_clock = [50_000.0]
    latest_sequence = [1]
    runner.bind_source(lambda: source_clock[0], lambda: latest_sequence[0])
    runner.select_device("muse-1", "Muse 2")
    runner.start_baseline(BaselineKind.eyes_open)
    names = ("tp9", "af7", "af8", "tp10")

    # Sequence 1 was pulled before the committed marker and is skipped even
    # though the Python monotonic clock uses a deliberately unrelated epoch.
    runner.accept_sample(
        good_sample(49_999.9), sensor_timestamps={n: 49_999.9 for n in names},
        sampling_rate_ok=False, source_sequence=1,
    )
    assert writers[-1].samples == []

    latest_sequence[0] = 2
    runner.accept_sample(
        good_sample(50_000.1), sensor_timestamps={n: 50_000.1 for n in names},
        sampling_rate_ok=False, source_sequence=2,
    )
    assert writers[-1].samples[-1].timestamp == 50_000.1
    assert runner.state().accepted_clean_seconds == 0

    # A later source event cannot be ordered with an exact duplicate timestamp.
    latest_sequence[0] = 3
    with pytest.raises(CollectionStateError, match="sample could not be written"):
        runner.accept_sample(
            good_sample(50_000.1), sensor_timestamps={n: 50_000.1 for n in names},
            sampling_rate_ok=False, source_sequence=3,
        )
    assert session.state is CollectionSessionState.interrupted


def test_adapter_sequences_duplicate_backward_and_nonfinite_source_events():
    source = LSLMuseStreamSource(clock=lambda: 10.0)
    source._channel_names = ("TP9", "AF7", "AF8", "TP10")
    first = source.map_sample([1, 2, 3, 4], 10.0)
    duplicate = source.map_sample([2, 3, 4, 5], 10.0)
    backward = source.map_sample([3, 4, 5, 6], 9.9)
    nonfinite = source.map_sample([4, 5, 6, 7], float("nan"))

    assert [item.source_sequence for item in (first, duplicate, backward, nonfinite)] == [1, 2, 3, 4]
    assert duplicate.capture_eligible is True
    assert backward.capture_eligible is True
    assert nonfinite.capture_eligible is True


def test_physical_pull_sequence_is_watermarked_before_boundary_with_real_writer(
    tmp_path, db, setup_runner, monkeypatch
):
    _, session, clock, _, _ = setup_runner
    source_clock = [50_000.0]
    source = LSLMuseStreamSource(clock=lambda: source_clock[0])
    source._channel_names = ("TP9", "AF7", "AF8", "TP10")
    source._connected = True

    class OneSampleInlet:
        def pull_sample(self, timeout):
            return [1.0, 2.0, 3.0, 4.0], 50_000.1

    source._inlet = OneSampleInlet()
    writers = []
    runner = CollectionStateMachine(
        db,
        session,
        writer_factory=lambda marker_clock: (
            writers.append(AtomicEEGWriter(tmp_path, clock=marker_clock)) or writers[-1]
        ),
        monotonic=clock.monotonic,
        now=clock.now,
    )
    runner.bind_source(source.source_clock, source.latest_source_sequence)
    runner.select_device("muse-1", "Muse 2")
    original_map = source.map_sample

    def cross_boundary_after_pull(*args, **kwargs):
        runner.start_baseline(BaselineKind.eyes_open)
        return original_map(*args, **kwargs)

    monkeypatch.setattr(source, "map_sample", cross_boundary_after_pull)

    async def pull_once():
        samples = source.samples()
        try:
            return await anext(samples)
        finally:
            await samples.aclose()

    incoming = asyncio.run(pull_once())
    CollectionConnectionManager._accept_sample_unlocked(runner, incoming)

    assert incoming.source_sequence == 1
    assert writers[0]._row_count == 1  # start marker only; pre-boundary pull was skipped
    runner.interrupt("test cleanup")


def test_marker_watermark_waits_for_inlet_return_sequence_stamp(setup_runner):
    runner, _, _, _, _ = setup_runner
    source = LSLMuseStreamSource(clock=lambda: 50_000.0)
    runner.bind_source(source.source_clock, source.latest_source_sequence)
    runner._writer = FakeWriter([])
    inlet_returned = threading.Event()
    release_stamp = threading.Event()
    marker_done = threading.Event()
    pull_result = []

    class PausedPullResult:
        def __iter__(self):
            yield [1.0, 2.0, 3.0, 4.0]
            yield 50_000.1
            inlet_returned.set()
            assert release_stamp.wait(timeout=2)

    class PausedInlet:
        def pull_sample(self, timeout):
            return PausedPullResult()

    source._inlet = PausedInlet()
    pull_thread = threading.Thread(
        target=lambda: pull_result.append(source._pull_sample()),
        daemon=True,
    )
    marker_thread = threading.Thread(
        target=lambda: (runner._write_marker("race_boundary"), marker_done.set()),
        daemon=True,
    )

    pull_thread.start()
    assert inlet_returned.wait(timeout=1)
    marker_thread.start()
    marker_waited_for_stamp = not marker_done.wait(timeout=0.1)
    release_stamp.set()
    pull_thread.join(timeout=1)
    marker_thread.join(timeout=1)

    assert marker_waited_for_stamp is True
    assert marker_done.is_set()
    assert pull_result == [([1.0, 2.0, 3.0, 4.0], 50_000.1, 1)]
    assert runner._capture_sequence_watermark == 1


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
    clock.advance(0.001)
    runner.accept_sample(good_sample(clock.value))
    for _ in range(30):
        clock.advance(1)
        runner.accept_sample(good_sample(clock.value))
    clock.advance(29.999)
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
    with pytest.raises(CollectionStateError, match="marker could not be written"):
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
    clock.advance(0.001)

    with pytest.raises(CollectionStateError, match="sample could not be written"):
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


def test_state_machine_preserves_valid_source_timestamp_in_raw_sample(db, setup_runner):
    _, session, clock, _, _ = setup_runner
    writers = []
    runner = CollectionStateMachine(
        db,
        session,
        writer_factory=lambda marker_clock: writers.append(FakeWriter([])) or writers[-1],
        monotonic=clock.monotonic,
        now=clock.now,
    )
    runner.select_device("muse-1", "Muse 2")
    runner.start_baseline(BaselineKind.eyes_open)
    clock.advance(0.01)
    runner.accept_sample(
        good_sample(clock.value),
        sensor_timestamps={name: clock.value for name in ("tp9", "af7", "af8", "tp10")},
    )
    assert writers[-1].samples[-1].timestamp == clock.value


def test_sample_pulled_before_phase_marker_is_skipped_without_interrupting_capture(setup_runner):
    runner, session, clock, _, writers = setup_runner
    runner.select_device("muse-1", "Muse 2")
    runner.start_baseline(BaselineKind.eyes_open)
    before_marker = clock.value - 0.01

    state = runner.accept_sample(
        good_sample(before_marker),
        sensor_timestamps={name: before_marker for name in ("tp9", "af7", "af8", "tp10")},
    )

    assert writers[-1].samples == []
    assert state.state is CollectionSessionState.baseline
    assert session.interruption_reason is None
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

    # Backend markers remain ordered, then the next valid source sample follows.
    runner.start_stimulus(active.current_trial_id)
    clock.advance(0.01)
    runner.accept_sample(
        good_sample(clock.value),
        sensor_timestamps={name: clock.value for name in ("tp9", "af7", "af8", "tp10")},
    )

    assert runner.state().trial_state is TrialState.stimulus
    runner.interrupt("test cleanup")


def test_capture_clock_overflow_during_baseline_sample_fails_closed(tmp_path, db, setup_runner):
    _, session, clock, _, _ = setup_runner
    fixed_max_clock = lambda: sys.float_info.max
    runner = CollectionStateMachine(
        db,
        session,
        writer_factory=lambda marker_clock: AtomicEEGWriter(tmp_path, clock=marker_clock),
        monotonic=fixed_max_clock,
        now=clock.now,
    )
    runner.select_device("muse-1", "Muse 2")
    runner.start_baseline(BaselineKind.eyes_open)

    with pytest.raises(CollectionStateError, match="sample could not be written"):
        runner.accept_sample(good_sample(sys.float_info.max))

    assert runner.session.state is CollectionSessionState.interrupted
    assert runner.session.active_baseline is None
    assert list(tmp_path.rglob("*.partial")) == []


def test_capture_clock_overflow_during_trial_sample_fails_closed(tmp_path, db, setup_runner):
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
        monotonic=lambda: sys.float_info.max,
        now=clock.now,
    )
    active = runner.start_trial_rest()

    with pytest.raises(CollectionStateError, match="sample could not be written"):
        runner.accept_sample(good_sample(sys.float_info.max))

    assert runner.session.state is CollectionSessionState.interrupted
    assert runner.db.get(CollectionTrial, active.current_trial_id).state is TrialState.interrupted
    assert list(tmp_path.rglob("*.partial")) == []


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
