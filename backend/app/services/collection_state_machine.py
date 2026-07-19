from __future__ import annotations

import json
import secrets
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models.dataset_collection import (
    ArtifactEvent,
    BaselineKind,
    CollectionSession,
    CollectionSessionState,
    CollectionTrial,
    DatasetParticipant,
    TrialState,
)
from app.services.dataset_labels import derive_labels
from app.services.raw_eeg_writer import EEGSample, RawFileResult


SENSOR_NAMES = ("tp9", "af7", "af8", "tp10")
GOOD_QUALITY_MINIMUM = 60.0
STALE_AFTER_SECONDS = 2.0
STIMULUS_MIN_SECONDS = 45.0
STIMULUS_MAX_SECONDS = 60.0
POST_RATING_REST_MIN_SECONDS = 20.0
POST_RATING_REST_MAX_SECONDS = 30.0


class EEGWriter(Protocol):
    def start(self, path_parts: list[str]) -> None: ...
    def append(self, sample: EEGSample) -> None: ...
    def mark(self, marker: str) -> None: ...
    def finalize(self) -> RawFileResult: ...
    def abort(self) -> None: ...


class CollectionStateError(RuntimeError):
    """Base class for safe collection runner errors."""


class InvalidTransitionError(CollectionStateError):
    """Raised when a command is not valid for the persisted state."""


class CollectionPersistenceError(CollectionStateError):
    """Raised when a boundary could not be durably committed."""


@dataclass(frozen=True, slots=True)
class CollectionRunnerState:
    session_id: int
    state: CollectionSessionState
    active_baseline: BaselineKind | None
    current_trial_id: int | None
    current_trial_order: int | None
    trial_state: TrialState | None
    completed_trials: int
    total_trials: int
    next_trial_order: int | None
    break_required: bool
    interruption_reason: str | None
    accepted_clean_seconds: float
    wall_clock_seconds: float
    file_recovery_required: bool = False


class CollectionStateMachine:
    """Persist collection boundaries while keeping high-rate counters in memory."""

    def __init__(
        self,
        db: Session,
        collection_session: CollectionSession,
        *,
        writer_factory: Callable[[Callable[[], float]], EEGWriter],
        monotonic: Callable[[], float] = time.monotonic,
        now: Callable[[], datetime] = datetime.utcnow,
        settings: Settings | None = None,
    ):
        self.db = db
        self.session = collection_session
        self._writer_factory = writer_factory
        self._monotonic = monotonic
        self._now = now
        settings = settings or get_settings()
        self._baseline_wall_seconds = float(settings.collection_baseline_wall_seconds)
        self._baseline_clean_seconds = float(settings.collection_baseline_min_clean_seconds)
        self._rest_min_seconds = float(settings.collection_rest_min_seconds)
        self._rest_max_seconds = float(settings.collection_rest_max_seconds)
        self._writer: EEGWriter | None = None
        self._capture_started_at: float | None = None
        self._last_sample_at: float | None = None
        self._last_sample_clean = False
        self._accepted_clean_seconds = 0.0
        self._file_recovery_required = False
        self._capture_attempt_token = (
            secrets.token_hex(6)
            if collection_session.state is CollectionSessionState.interrupted
            else None
        )

    @classmethod
    def recover(
        cls,
        db: Session,
        collection_session: CollectionSession,
        **kwargs,
    ) -> CollectionStateMachine:
        runner = cls(db, collection_session, **kwargs)
        in_flight = collection_session.active_baseline is not None
        trial = runner._current_trial()
        if trial is not None and trial.state in {TrialState.rest, TrialState.stimulus, TrialState.rating}:
            trial.state = TrialState.interrupted
            trial.failure_reason = "Backend restarted during active Trial"
            in_flight = True
        if in_flight:
            collection_session.state = CollectionSessionState.interrupted
            collection_session.interruption_reason = "Backend restarted during active collection"
            collection_session.recovery_at = runner._now()
            collection_session.active_baseline = None
            runner._capture_attempt_token = secrets.token_hex(6)
            runner._commit_boundary()
        return runner

    def state(self) -> CollectionRunnerState:
        trial = self._current_trial()
        elapsed = self._elapsed()
        next_order = self._next_trial_order()
        return CollectionRunnerState(
            session_id=self.session.id,
            state=self.session.state,
            active_baseline=self.session.active_baseline,
            current_trial_id=trial.id if trial else None,
            current_trial_order=trial.randomized_order if trial else None,
            trial_state=trial.state if trial else None,
            completed_trials=self.session.completed_trials or 0,
            total_trials=self.session.total_trials or 0,
            next_trial_order=next_order,
            break_required=(self.session.completed_trials or 0) == 6,
            interruption_reason=self.session.interruption_reason,
            accepted_clean_seconds=self._accepted_clean_seconds,
            wall_clock_seconds=elapsed,
            file_recovery_required=self._persisted_file_recovery_required(),
        )

    def select_device(self, device_id: str, device_name: str) -> CollectionRunnerState:
        self._require(self.session.state is CollectionSessionState.preparation, "device selection requires preparation")
        self._require(bool(device_id.strip()), "device ID is required")
        self.session.device_id = device_id
        self.session.device_name = device_name
        self._commit_boundary()
        return self.state()

    def start_baseline(self, kind: BaselineKind) -> CollectionRunnerState:
        kind = BaselineKind(kind)
        allowed = self.session.state in {CollectionSessionState.preparation, CollectionSessionState.baseline}
        self._require(allowed and self.session.device_id is not None, "baseline requires a selected device")
        if kind is BaselineKind.eyes_open:
            self._require(not self.session.eyes_open_baseline_path, "eyes-open baseline is already complete")
        else:
            self._require(bool(self.session.eyes_open_baseline_path), "eyes-open baseline must finish first")
            self._require(not self.session.eyes_closed_baseline_path, "eyes-closed baseline is already complete")
        self._require(self._writer is None, "a capture is already active")

        writer = self._new_writer(f"baseline-{kind.value}")
        self._writer = writer
        self._capture_started_at = self._monotonic()
        self._last_sample_at = None
        self._last_sample_clean = False
        self._accepted_clean_seconds = 0.0
        self.session.active_baseline = kind
        self.session.state = CollectionSessionState.baseline
        self.session.started_at = self.session.started_at or self._now()
        self.session.interruption_reason = None
        self._write_marker(f"baseline_{kind.value}_start")
        self._commit_boundary()
        return self.state()

    def accept_sample(
        self,
        sample: EEGSample,
        *,
        sensor_timestamps: Mapping[str, float] | None = None,
    ) -> CollectionRunnerState:
        self._require(self._writer is not None, "sample ingestion requires an active capture")
        now = self._monotonic()
        sample = replace(sample, timestamp=now)
        try:
            self._writer.append(sample)
        except Exception:
            self._fail_active_boundary("Raw EEG append failed", self.session.current_trial_id)
            raise
        clean = self._sample_is_clean(sample, sensor_timestamps, now)
        if self._last_sample_at is not None and clean and self._last_sample_clean:
            interval = max(0.0, now - self._last_sample_at)
            if interval <= STALE_AFTER_SECONDS:
                self._accepted_clean_seconds += interval
        self._last_sample_at = now
        self._last_sample_clean = clean
        return self.state()

    def finish_baseline(self) -> CollectionRunnerState:
        self._require(self.session.state is CollectionSessionState.baseline, "no baseline is active")
        self._require(self._writer is not None and self.session.active_baseline is not None, "no baseline capture is active")
        wall_seconds = self._elapsed()
        self._require(
            wall_seconds >= self._baseline_wall_seconds,
            f"baseline requires {self._baseline_wall_seconds:g} wall seconds",
        )
        self._require(
            self._accepted_clean_seconds >= self._baseline_clean_seconds,
            f"baseline requires {self._baseline_clean_seconds:g} clean seconds",
        )
        kind = self.session.active_baseline
        writer = self._writer
        self._write_marker(f"baseline_{kind.value}_end")
        try:
            result = writer.finalize()
        except Exception:
            try:
                writer.abort()
            except Exception:
                pass
            self._mark_capture_failed("Baseline Raw EEG finalization failed")
            raise
        self._clear_capture()

        if kind is BaselineKind.eyes_open:
            self.session.eyes_open_baseline_path = result.relative_path
            self.session.eyes_open_baseline_checksum = result.sha256
            self.session.eyes_open_accepted_clean_seconds = self._accepted_clean_seconds
            self.session.eyes_open_wall_clock_seconds = wall_seconds
            self.session.state = CollectionSessionState.baseline
        else:
            self.session.eyes_closed_baseline_path = result.relative_path
            self.session.eyes_closed_baseline_checksum = result.sha256
            self.session.eyes_closed_accepted_clean_seconds = self._accepted_clean_seconds
            self.session.eyes_closed_wall_clock_seconds = wall_seconds
            self.session.state = CollectionSessionState.ready
        self.session.active_baseline = None
        self._commit_after_finalize(
            "Baseline file finalized but metadata commit failed",
            result=result,
            recovery_baseline=kind,
            accepted_clean_seconds=self._accepted_clean_seconds,
            wall_clock_seconds=wall_seconds,
        )
        return self.state()

    def start_trial_rest(self) -> CollectionRunnerState:
        self._require(self.session.state in {CollectionSessionState.ready, CollectionSessionState.in_progress}, "Trial rest requires a ready session")
        self._require(self.session.current_trial_id is None, "another Trial is active")
        post_rest_warning = self._post_rating_rest_warning()
        trial = self._next_trial()
        self._require(trial is not None, "no scheduled Trial remains")
        writer = self._new_writer(f"trial-{trial.id}")
        self._writer = writer
        self._capture_started_at = self._monotonic()
        self._last_sample_at = None
        self._last_sample_clean = False
        self._accepted_clean_seconds = 0.0
        trial.state = TrialState.rest
        trial.rest_started_at = self._now()
        trial.started_at = trial.started_at or self._now()
        trial.failure_reason = None
        if post_rest_warning is not None:
            trial.failure_reason = post_rest_warning
        self.session.current_trial_id = trial.id
        self.session.state = CollectionSessionState.in_progress
        self.session.interruption_reason = None
        self._write_marker("rest_start", trial.id)
        self._commit_boundary()
        return self.state()

    def start_stimulus(self, trial_id: int) -> CollectionRunnerState:
        trial = self._require_trial(trial_id, TrialState.rest)
        elapsed = self._elapsed()
        self._require(elapsed >= self._rest_min_seconds, f"rest requires at least {self._rest_min_seconds:g} seconds")
        if elapsed > self._rest_max_seconds:
            self.interrupt(f"Pre-stimulus rest exceeded {self._rest_max_seconds:g} seconds")
            raise InvalidTransitionError(
                f"rest must not exceed {self._rest_max_seconds:g} seconds; Trial was interrupted"
            )
        assert self._writer is not None
        self._write_marker("rest_end", trial.id)
        self._write_marker("stimulus_start", trial.id)
        trial.state = TrialState.stimulus
        trial.stimulus_started_at = self._now()
        self._capture_started_at = self._monotonic()
        self._commit_boundary()
        return self.state()

    def mark_artifact(
        self,
        trial_id: int,
        event_type: str,
        *,
        start_seconds: float,
        duration_seconds: float,
        details: Mapping[str, object] | None = None,
    ) -> CollectionRunnerState:
        trial = self._require_trial(trial_id, TrialState.stimulus)
        self._require(bool(event_type.strip()) and start_seconds >= 0 and duration_seconds >= 0, "invalid artifact event")
        self.db.add(ArtifactEvent(
            trial_id=trial.id,
            event_type=event_type,
            start_seconds=start_seconds,
            duration_seconds=duration_seconds,
            details_json=json.dumps(details, sort_keys=True) if details is not None else None,
        ))
        self._commit_boundary()
        return self.state()

    def finish_stimulus(self, trial_id: int) -> CollectionRunnerState:
        trial = self._require_trial(trial_id, TrialState.stimulus)
        elapsed = self._elapsed()
        self._require(elapsed >= STIMULUS_MIN_SECONDS, "stimulus requires at least 45 seconds")
        if elapsed > STIMULUS_MAX_SECONDS:
            self.interrupt("Stimulus exceeded 60 seconds")
            raise InvalidTransitionError("stimulus must not exceed 60 seconds; Trial was interrupted")
        assert self._writer is not None
        self._write_marker("stimulus_end", trial.id)
        self._write_marker("rating_start", trial.id)
        trial.state = TrialState.rating
        trial.rating_started_at = self._now()
        trial.wall_clock_seconds = self._elapsed()
        trial.accepted_clean_seconds = self._accepted_clean_seconds
        self._commit_boundary()
        return self.state()

    def submit_rating(self, trial_id: int, *, valence: int, arousal: int, confidence: int) -> CollectionRunnerState:
        trial = self._require_trial(trial_id, TrialState.rating)
        assert self._writer is not None
        labels = derive_labels(valence, arousal, confidence)
        self._write_marker("rating_end", trial.id)
        try:
            result = self._writer.finalize()
        except Exception:
            try:
                self._writer.abort()
            except Exception:
                pass
            self._mark_capture_failed("Trial Raw EEG finalization failed", trial=trial)
            raise
        self._clear_capture()

        trial.valence_rating = valence
        trial.arousal_rating = arousal
        trial.confidence = confidence
        trial.valence_label = None if labels.valence_label is None else labels.valence_label == "positive"
        trial.arousal_label = None if labels.arousal_label is None else labels.arousal_label == "high"
        trial.valid_valence_label = labels.valid_valence_label
        trial.valid_arousal_label = labels.valid_arousal_label
        trial.eeg_file_path = result.relative_path
        trial.eeg_checksum = result.sha256
        trial.raw_size_bytes = result.byte_size
        trial.state = TrialState.completed
        trial.completed_at = self._now()
        self.session.completed_trials = (self.session.completed_trials or 0) + 1
        self.session.current_trial_id = None
        if self.session.completed_trials == self.session.total_trials == 12:
            self.session.state = CollectionSessionState.completed
            self.session.completed_at = self._now()
        else:
            self.session.state = CollectionSessionState.in_progress
        self._commit_after_finalize(
            "Trial file finalized but metadata commit failed",
            recovery_trial_id=trial.id,
            result=result,
        )
        return self.state()

    def interrupt(self, reason: str) -> CollectionRunnerState:
        self._require(bool(reason.strip()), "interruption reason is required")
        self._require(
            self._writer is not None
            and self.session.state in {CollectionSessionState.baseline, CollectionSessionState.in_progress},
            "only an active baseline or Trial can be interrupted",
        )
        trial = self._current_trial()
        trial_id = trial.id if trial is not None else None
        session_id = self.session.id
        abort_error: Exception | None = None
        assert self._writer is not None
        try:
            self._writer.abort()
        except Exception as exc:
            abort_error = exc
        self._clear_capture()
        safe_reason = reason
        if abort_error is not None:
            safe_reason = f"{reason}; Raw EEG abort failed"
        if trial is not None and trial.state in {TrialState.rest, TrialState.stimulus, TrialState.rating}:
            trial.state = TrialState.interrupted
            trial.failure_reason = safe_reason
        self.session.state = CollectionSessionState.interrupted
        self.session.interruption_reason = safe_reason
        self.session.recovery_at = self._now()
        self.session.active_baseline = None
        self._capture_attempt_token = secrets.token_hex(6)
        try:
            self.db.commit()
        except Exception as exc:
            self._fail_active_boundary(safe_reason, trial_id, session_id=session_id)
            raise CollectionPersistenceError("Collection interruption could not be persisted") from exc
        if abort_error is not None:
            raise CollectionStateError("Raw EEG capture could not be cleanly aborted") from abort_error
        return self.state()

    def resume(self) -> CollectionRunnerState:
        self._require(self.session.state is CollectionSessionState.interrupted, "only an interrupted session can resume")
        trial = self._current_trial()
        if trial is not None and trial.state is TrialState.interrupted:
            trial.state = TrialState.scheduled
            self.session.current_trial_id = None
        self.session.interruption_reason = None
        self.session.recovery_at = self._now()
        if self.session.eyes_open_baseline_path and self.session.eyes_closed_baseline_path:
            self.session.state = CollectionSessionState.ready
        elif self.session.device_id:
            self.session.state = CollectionSessionState.preparation
        else:
            self.session.state = CollectionSessionState.preparation
        self._commit_boundary()
        return self.state()

    def _new_writer(self, capture_id: str) -> EEGWriter:
        participant = self.db.get(DatasetParticipant, self.session.participant_id)
        if participant is None:
            raise CollectionStateError("collection participant is unavailable")
        writer = self._writer_factory(self._monotonic)
        if self._capture_attempt_token is not None:
            capture_id = f"{capture_id}-recovery-{self._capture_attempt_token}"
        writer.start([participant.participant_code, str(self.session.id), capture_id])
        return writer

    def _sample_is_clean(self, sample: EEGSample, timestamps: Mapping[str, float] | None, now: float) -> bool:
        qualities = dict(zip(SENSOR_NAMES, (sample.tp9_quality, sample.af7_quality, sample.af8_quality, sample.tp10_quality)))
        if set(qualities) != set(SENSOR_NAMES) or any(value < GOOD_QUALITY_MINIMUM for value in qualities.values()):
            return False
        timestamps = timestamps or {name: sample.timestamp for name in SENSOR_NAMES}
        if set(timestamps) != set(SENSOR_NAMES):
            return False
        return all(0 <= now - timestamps[name] <= STALE_AFTER_SECONDS for name in SENSOR_NAMES)

    def _require_trial(self, trial_id: int, expected: TrialState) -> CollectionTrial:
        trial = self._current_trial()
        self._require(trial is not None and trial.id == trial_id and trial.session_id == self.session.id, "Trial is not active for this session")
        self._require(trial.state is expected, f"Trial must be {expected.value}")
        self._require(self._writer is not None, "Trial capture is unavailable")
        return trial

    def _current_trial(self) -> CollectionTrial | None:
        return self.db.get(CollectionTrial, self.session.current_trial_id) if self.session.current_trial_id else None

    def _next_trial(self) -> CollectionTrial | None:
        return self.db.scalar(
            select(CollectionTrial).where(
                CollectionTrial.session_id == self.session.id,
                CollectionTrial.state == TrialState.scheduled,
            ).order_by(CollectionTrial.randomized_order)
        )

    def _next_trial_order(self) -> int | None:
        trial = self._next_trial()
        return trial.randomized_order if trial else None

    def _post_rating_rest_warning(self) -> str | None:
        previous = self.db.scalar(
            select(CollectionTrial)
            .where(
                CollectionTrial.session_id == self.session.id,
                CollectionTrial.state == TrialState.completed,
            )
            .order_by(CollectionTrial.randomized_order.desc())
        )
        if previous is None or previous.completed_at is None:
            return None
        elapsed = (self._now() - previous.completed_at).total_seconds()
        self._require(elapsed >= POST_RATING_REST_MIN_SECONDS, "post-rating rest requires at least 20 seconds")
        if elapsed > POST_RATING_REST_MAX_SECONDS:
            return "Post-rating rest exceeded 30 seconds"
        return None

    def _persisted_file_recovery_required(self) -> bool:
        trial = self._current_trial()
        trial_recovery = bool(
            trial is not None
            and trial.state is TrialState.interrupted
            and trial.eeg_file_path
            and trial.eeg_checksum
            and trial.raw_size_bytes is not None
        )
        baseline_recovery = bool(
            self.session.state is CollectionSessionState.interrupted
            and self.session.interruption_reason
            and "file finalized but metadata commit failed" in self.session.interruption_reason
            and (self.session.eyes_open_baseline_path or self.session.eyes_closed_baseline_path)
        )
        return trial_recovery or baseline_recovery

    def _elapsed(self) -> float:
        return 0.0 if self._capture_started_at is None else max(0.0, self._monotonic() - self._capture_started_at)

    def _write_marker(self, marker: str, trial_id: int | None = None) -> None:
        assert self._writer is not None
        try:
            self._writer.mark(marker)
        except Exception:
            self._fail_active_boundary("Raw EEG marker write failed", trial_id)
            raise

    def _clear_capture(self) -> None:
        self._writer = None
        self._capture_started_at = None
        self._last_sample_at = None
        self._last_sample_clean = False

    def _mark_capture_failed(self, reason: str, *, trial: CollectionTrial | None = None) -> None:
        session_id = self.session.id
        trial_id = trial.id if trial is not None else None
        self.db.rollback()
        self._clear_capture()
        if trial_id is not None:
            trial = self.db.get(CollectionTrial, trial_id)
            if trial is not None:
                trial.state = TrialState.failed
                trial.failure_reason = reason
        self.session = self.db.get(CollectionSession, session_id)
        self.session.state = CollectionSessionState.failed
        self.session.interruption_reason = reason
        self.session.recovery_at = self._now()
        self.db.commit()

    def _fail_active_boundary(
        self,
        reason: str,
        trial_id: int | None = None,
        *,
        session_id: int | None = None,
    ) -> None:
        session_id = session_id or self.session.id
        writer = self._writer
        if writer is not None:
            try:
                writer.abort()
            except Exception:
                pass
        self._clear_capture()
        self.db.rollback()
        self.session = self.db.get(CollectionSession, session_id)
        if trial_id is not None:
            trial = self.db.get(CollectionTrial, trial_id)
            if trial is not None:
                trial.state = TrialState.interrupted
                trial.failure_reason = reason
                self.session.current_trial_id = trial.id
        self.session.state = CollectionSessionState.interrupted
        self.session.active_baseline = None
        self.session.interruption_reason = reason
        self.session.recovery_at = self._now()
        self._capture_attempt_token = secrets.token_hex(6)
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()

    def _commit_boundary(self) -> None:
        session_id = self.session.id
        current_trial_id = self.session.current_trial_id
        capture_active = self._writer is not None
        try:
            self.db.commit()
        except Exception as exc:
            if capture_active:
                self._fail_active_boundary(
                    "Collection boundary commit failed",
                    current_trial_id,
                    session_id=session_id,
                )
            else:
                self.db.rollback()
            raise CollectionPersistenceError("Collection state could not be persisted") from exc

    def _commit_after_finalize(
        self,
        reason: str,
        *,
        result: RawFileResult,
        recovery_trial_id: int | None = None,
        recovery_baseline: BaselineKind | None = None,
        accepted_clean_seconds: float = 0.0,
        wall_clock_seconds: float = 0.0,
    ) -> None:
        session_id = self.session.id
        current_trial_id = recovery_trial_id or self.session.current_trial_id
        try:
            self.db.commit()
        except Exception as exc:
            self.db.rollback()
            self.session = self.db.get(CollectionSession, session_id)
            if current_trial_id is not None:
                trial = self.db.get(CollectionTrial, current_trial_id)
                if trial is not None and trial.state is not TrialState.completed:
                    trial.state = TrialState.interrupted
                    trial.failure_reason = reason
                    trial.eeg_file_path = result.relative_path
                    trial.eeg_checksum = result.sha256
                    trial.raw_size_bytes = result.byte_size
                    self.session.current_trial_id = trial.id
            if recovery_baseline is BaselineKind.eyes_open:
                self.session.eyes_open_baseline_path = result.relative_path
                self.session.eyes_open_baseline_checksum = result.sha256
                self.session.eyes_open_accepted_clean_seconds = accepted_clean_seconds
                self.session.eyes_open_wall_clock_seconds = wall_clock_seconds
            elif recovery_baseline is BaselineKind.eyes_closed:
                self.session.eyes_closed_baseline_path = result.relative_path
                self.session.eyes_closed_baseline_checksum = result.sha256
                self.session.eyes_closed_accepted_clean_seconds = accepted_clean_seconds
                self.session.eyes_closed_wall_clock_seconds = wall_clock_seconds
            self.session.state = CollectionSessionState.interrupted
            self.session.interruption_reason = reason
            self.session.recovery_at = self._now()
            self._file_recovery_required = True
            self._capture_attempt_token = secrets.token_hex(6)
            try:
                self.db.commit()
            except Exception:
                self.db.rollback()
            raise CollectionPersistenceError(reason) from exc

    @staticmethod
    def _require(condition: bool, message: str) -> None:
        if not condition:
            raise InvalidTransitionError(message)
