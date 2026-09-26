"""
EEG Session State Machine — implements PRD Section 8.

States:
  DISCOVERING → DEVICE_CONFIRMATION → CONNECTING → PREPARATION → FITTING
  → BASELINE → READY → RECORDING → EMOTION_CONFIRMATION → COMPLETED

Error states: PAUSED_SIGNAL_QUALITY | DISCONNECTED | TIMEOUT | CANCELLED | FAILED

Rules:
  1. Baseline signal drop or artifact → Reset 20s
  2. Recording signal drop → PAUSED_SIGNAL_QUALITY, reject epoch, stop timer
  3. Back to 'good' all 4 sensors for 2s → Resume recording
  4. Wall-clock > 120s and accepted < 30s → TIMEOUT
  5. Accepted = 30s → compute features/emotion → EMOTION_CONFIRMATION
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import numpy as np

from app.config import get_settings
from app.services.signal_processor import (
    BaselineFeatures,
    EmotionClassification,
    RecordingFeatures,
    SensorQuality,
    SAMPLING_RATE,
    classify_emotion,
    compute_baseline,
    compute_recording_features,
    estimate_sensor_state,
    is_artifact,
    EPOCH_SAMPLES,
)

settings = get_settings()


class Phase(str, Enum):
    DISCOVERING = "DISCOVERING"
    DEVICE_CONFIRMATION = "DEVICE_CONFIRMATION"
    CONNECTING = "CONNECTING"
    PREPARATION = "PREPARATION"
    FITTING = "FITTING"
    BASELINE = "BASELINE"
    READY = "READY"
    RECORDING = "RECORDING"
    PAUSED_SIGNAL_QUALITY = "PAUSED_SIGNAL_QUALITY"
    EMOTION_CONFIRMATION = "EMOTION_CONFIRMATION"
    COMPLETED = "COMPLETED"
    TIMEOUT = "TIMEOUT"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"
    DISCONNECTED = "DISCONNECTED"


@dataclass
class SessionState:
    """Mutable state for one EEG session."""

    session_id: str
    user_id: int
    phase: Phase = Phase.DISCOVERING
    sequence: int = 0

    # Device
    device_state: str = "disconnected"
    device_name: Optional[str] = None
    device_id: Optional[str] = None

    # Sensors
    sensors: dict[str, SensorQuality] = field(
        default_factory=lambda: {
            "tp9": SensorQuality(),
            "af7": SensorQuality(),
            "af8": SensorQuality(),
            "tp10": SensorQuality(),
        }
    )

    # Baseline accumulation
    baseline_buffer: list[np.ndarray] = field(default_factory=list)
    baseline_accepted_seconds: float = 0.0
    baseline_features: Optional[BaselineFeatures] = None

    # Recording accumulation
    recording_segments: list[np.ndarray] = field(default_factory=list)  # list of clean continuous segments
    current_segment: list[np.ndarray] = field(default_factory=list)     # raw sample chunks in current good run
    accepted_seconds: float = 0.0
    wall_clock_start: Optional[float] = None
    pause_start: Optional[float] = None
    good_resume_start: Optional[float] = None   # when all-4-good after pause
    pause_count: int = 0
    rejected_epoch_count: int = 0

    # Results
    recording_features: Optional[RecordingFeatures] = None
    emotion: Optional[EmotionClassification] = None
    raw_data_path: Optional[str] = None

    # Timing helpers
    last_sample_time: float = field(default_factory=time.monotonic)

    @property
    def wall_clock_seconds(self) -> float:
        if self.wall_clock_start is None:
            return 0.0
        return time.monotonic() - self.wall_clock_start

    @property
    def all_sensors_good(self) -> bool:
        return all(s.state == "good" for s in self.sensors.values())

    @property
    def ready(self) -> bool:
        return self.all_sensors_good and self.phase in (Phase.READY, Phase.RECORDING)

    def next_sequence(self) -> int:
        self.sequence += 1
        return self.sequence


class EEGStateMachine:
    """
    Processes incoming EEG samples and manages state transitions.
    Designed to be driven by the LSL receiver in the WebSocket handler.
    """

    BASELINE_TARGET = settings.baseline_seconds         # 20
    RECORDING_TARGET = settings.accepted_recording_seconds  # 30
    WALL_CLOCK_LIMIT = settings.wall_clock_timeout_seconds  # 120
    RESUME_STABLE = settings.resume_stable_seconds          # 2

    def __init__(self, state: SessionState) -> None:
        self.state = state
        self._on_complete_callbacks: list = []

    # ── External control ────────────────────────────────────────────────────

    def transition_to(self, phase: Phase, reason: str = "") -> None:
        self.state.phase = phase

    def confirm_device(self, device_name: str, device_id: str) -> None:
        """Call when user confirms device in DEVICE_CONFIRMATION step."""
        self.state.device_name = device_name
        self.state.device_id = device_id
        self.state.device_state = "connecting"
        self.transition_to(Phase.CONNECTING)

    def mark_connected(self) -> None:
        self.state.device_state = "connected"
        self.transition_to(Phase.PREPARATION)

    def start_fitting(self) -> None:
        self.transition_to(Phase.FITTING)

    def start_baseline(self) -> None:
        self.state.baseline_buffer = []
        self.state.baseline_accepted_seconds = 0.0
        self.transition_to(Phase.BASELINE)

    def cancel(self) -> None:
        self.transition_to(Phase.CANCELLED)

    def confirm_emotion(self) -> None:
        """User confirms emotion result → mark completed."""
        self.transition_to(Phase.COMPLETED)

    def remeasure(self) -> None:
        """User requests re-measurement → reset recording."""
        self._reset_recording()
        self.transition_to(Phase.READY)

    # ── Sample ingestion ────────────────────────────────────────────────────

    def ingest_samples(
        self,
        samples: np.ndarray,
        timestamps: np.ndarray,
        sensor_qualities: Optional[dict[str, SensorQuality]] = None,
    ) -> None:
        """
        Called by LSL receiver with new EEG samples.
        samples.shape = (N, 4)  channels = [TP9, AF7, AF8, TP10]
        """
        now = time.monotonic()
        self.state.last_sample_time = now

        # Update per-sensor quality
        if sensor_qualities:
            for key, sq in sensor_qualities.items():
                self.state.sensors[key.lower()] = sq
        else:
            self._update_sensors(samples, now)

        phase = self.state.phase

        if phase == Phase.BASELINE:
            self._process_baseline(samples, now)

        elif phase == Phase.RECORDING:
            self._process_recording(samples, now)

        elif phase == Phase.PAUSED_SIGNAL_QUALITY:
            self._check_resume(now)

        elif phase == Phase.READY:
            # Check if we should auto-start recording (READY → RECORDING)
            # This is triggered by explicit user action, so we just update sensors.
            pass

    def start_recording(self) -> None:
        """Explicit call to begin recording phase."""
        if self.state.phase != Phase.READY:
            return
        self._reset_recording()
        self.state.wall_clock_start = time.monotonic()
        self.transition_to(Phase.RECORDING)

    # ── Baseline logic ────────────────────────────────────────────────────

    def _process_baseline(self, samples: np.ndarray, now: float) -> None:
        if not self.state.all_sensors_good:
            # Any sensor not good → reset baseline
            self._reset_baseline()
            return

        # Check for artifact in incoming samples
        if is_artifact(samples):
            self._reset_baseline()
            return

        self.state.baseline_buffer.append(samples.copy())
        added_seconds = len(samples) / SAMPLING_RATE
        self.state.baseline_accepted_seconds += added_seconds

        if self.state.baseline_accepted_seconds >= self.BASELINE_TARGET:
            self._finalize_baseline()

    def _reset_baseline(self) -> None:
        self.state.baseline_buffer = []
        self.state.baseline_accepted_seconds = 0.0

    def _finalize_baseline(self) -> None:
        buffer = np.vstack(self.state.baseline_buffer) if self.state.baseline_buffer else np.empty((0, 4))
        try:
            self.state.baseline_features = compute_baseline(buffer)
            self.transition_to(Phase.READY)
        except Exception:
            self._reset_baseline()

    # ── Recording logic ───────────────────────────────────────────────────

    def _reset_recording(self) -> None:
        self.state.recording_segments = []
        self.state.current_segment = []
        self.state.accepted_seconds = 0.0
        self.state.wall_clock_start = None
        self.state.pause_count = 0
        self.state.rejected_epoch_count = 0
        self.state.good_resume_start = None

    def _process_recording(self, samples: np.ndarray, now: float) -> None:
        # Wall-clock timeout check
        if self.state.wall_clock_seconds > self.WALL_CLOCK_LIMIT:
            self.transition_to(Phase.TIMEOUT)
            return

        if not self.state.all_sensors_good:
            # Save current segment, enter pause
            self._flush_current_segment()
            self.state.pause_start = now
            self.state.good_resume_start = None
            self.state.pause_count += 1
            self.transition_to(Phase.PAUSED_SIGNAL_QUALITY)
            return

        # Accumulate samples and count accepted time
        self.state.current_segment.append(samples.copy())
        self.state.accepted_seconds += len(samples) / SAMPLING_RATE

        if self.state.accepted_seconds >= self.RECORDING_TARGET:
            self._finalize_recording()

    def _check_resume(self, now: float) -> None:
        """Called in PAUSED state to check if sensors have been good for 2s."""
        if not self.state.all_sensors_good:
            self.state.good_resume_start = None
            return

        if self.state.good_resume_start is None:
            self.state.good_resume_start = now
            return

        if now - self.state.good_resume_start >= self.RESUME_STABLE:
            # Resume recording
            self.state.pause_start = None
            self.state.good_resume_start = None
            self.transition_to(Phase.RECORDING)

        # Also check wall-clock timeout during pause
        if self.state.wall_clock_seconds > self.WALL_CLOCK_LIMIT:
            self.transition_to(Phase.TIMEOUT)

    def _flush_current_segment(self) -> None:
        """Move current_segment buffer into recording_segments."""
        if self.state.current_segment:
            segment = np.vstack(self.state.current_segment)
            self.state.recording_segments.append(segment)
            self.state.current_segment = []

    def _finalize_recording(self) -> None:
        self._flush_current_segment()
        if self.state.baseline_features is None:
            self.transition_to(Phase.FAILED)
            return
        try:
            self.state.recording_features = compute_recording_features(
                self.state.recording_segments, self.state.baseline_features
            )
            self.state.emotion = classify_emotion(self.state.recording_features)
            self.state.rejected_epoch_count = self.state.recording_features.rejected_epochs
            self.transition_to(Phase.EMOTION_CONFIRMATION)
        except Exception:
            self.transition_to(Phase.FAILED)

    # ── Sensor update ─────────────────────────────────────────────────────

    def _update_sensors(self, samples: np.ndarray, now: float) -> None:
        channel_keys = ["tp9", "af7", "af8", "tp10"]
        for i, key in enumerate(channel_keys):
            self.state.sensors[key] = estimate_sensor_state(
                samples, i, self.state.last_sample_time, now
            )

    # ── State snapshot ────────────────────────────────────────────────────

    def to_ws_dict(self) -> dict:
        """Build WebSocket message dict matching PRD Section 7."""
        s = self.state
        return {
            "session_id": s.session_id,
            "phase": s.phase.value,
            "sequence": s.next_sequence(),
            "timestamp": time.time(),
            "device_state": s.device_state,
            "device_name": s.device_name,
            "tp9": _sensor_dict(s.sensors["tp9"]),
            "af7": _sensor_dict(s.sensors["af7"]),
            "af8": _sensor_dict(s.sensors["af8"]),
            "tp10": _sensor_dict(s.sensors["tp10"]),
            "accepted_seconds": round(s.accepted_seconds, 2),
            "wall_clock_seconds": round(s.wall_clock_seconds, 2),
            "ready": s.all_sensors_good and s.phase in (Phase.READY,),
            "baseline_seconds": round(s.baseline_accepted_seconds, 2),
        }


def _sensor_dict(sq: SensorQuality) -> dict:
    return {
        "state": sq.state,
        "quality_score": round(sq.quality_score, 1),
        "timestamp": sq.timestamp,
        "sequence": sq.sequence,
    }
