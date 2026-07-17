from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel


# ─── WebSocket message schemas ────────────────────────────────────────────────

SensorState = Literal["unknown", "poor", "good", "stale"]
DeviceState = Literal["disconnected", "connecting", "connected"]
EEGPhase = Literal[
    "DISCOVERING",
    "DEVICE_CONFIRMATION",
    "CONNECTING",
    "PREPARATION",
    "FITTING",
    "BASELINE",
    "READY",
    "RECORDING",
    "PAUSED_SIGNAL_QUALITY",
    "EMOTION_CONFIRMATION",
    "COMPLETED",
    "TIMEOUT",
    "CANCELLED",
    "FAILED",
    "DISCONNECTED",
]


class SensorStatus(BaseModel):
    state: SensorState
    quality_score: float  # 0-100
    timestamp: float
    sequence: int


class EEGWebSocketMessage(BaseModel):
    """Server → Client WebSocket message (sent every ~100ms or on state change)."""

    session_id: Optional[str]
    phase: EEGPhase
    sequence: int
    timestamp: float

    # Device
    device_state: DeviceState
    device_name: Optional[str]

    # Sensors
    tp9: SensorStatus
    af7: SensorStatus
    af8: SensorStatus
    tp10: SensorStatus

    # Progress
    accepted_seconds: float  # clean seconds accumulated
    wall_clock_seconds: float
    ready: bool
    reason: Optional[str] = None  # human-readable tip or error code
    error_code: Optional[str] = None


class EEGSessionStart(BaseModel):
    user_id: int
    persona_id: Optional[int] = None
    input_story: str


class EEGSessionOut(BaseModel):
    id: int
    user_id: int
    status: str
    started_at: datetime
    completed_at: Optional[datetime]
    device_name: Optional[str]
    wall_clock_duration: Optional[float]
    rejected_epoch_count: int
    pause_count: int

    model_config = {"from_attributes": True}


class EmotionResultOut(BaseModel):
    final_emotion: str
    rule_version: str
    valence: Optional[float]
    arousal: Optional[float]
    delta_faa: Optional[float]
    delta_arousal: Optional[float]
    quality_score_avg: Optional[float]
    accepted_epochs: Optional[int]
    rejected_epochs: Optional[int]

    model_config = {"from_attributes": True}
