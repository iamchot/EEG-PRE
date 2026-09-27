from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.dataset_collection import (
    BaselineKind,
    CollectionSessionState,
    ParticipantState,
    Quadrant,
    StimulusApprovalState,
    TrialState,
)


class ParticipantCreate(BaseModel):
    consent_confirmed_at: datetime


class ParticipantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    participant_code: str
    consent_confirmed_at: datetime
    state: ParticipantState
    withdrawn_at: datetime | None
    created_at: datetime


class ParticipantListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    items: list[ParticipantResponse]


class StimulusCreate(BaseModel):
    title: str
    file_path: str
    checksum: str
    duration_seconds: float = Field(ge=45, le=60)
    target_quadrant: Quadrant
    approval_state: StimulusApprovalState
    stimulus_set_version: str


class StimulusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    file_path: str
    checksum: str
    duration_seconds: float
    target_quadrant: Quadrant
    approval_state: StimulusApprovalState
    stimulus_set_version: str
    created_at: datetime


class StimulusListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    items: list[StimulusResponse]


class CollectionSessionCreate(BaseModel):
    participant_id: int
    device_id: str | None = None
    device_name: str | None = None


class CollectionSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    participant_id: int
    device_id: str | None
    device_name: str | None
    completed_trials: int
    total_trials: int
    state: CollectionSessionState
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime


class CollectionSessionListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    items: list[CollectionSessionResponse]


class DeviceSelectionRequest(BaseModel):
    device_id: str = Field(min_length=1, max_length=100)
    device_name: str = Field(min_length=1, max_length=100)


class ArtifactRequest(BaseModel):
    event_type: str = Field(min_length=1, max_length=50)
    note: str | None = Field(default=None, max_length=500)


class RatingRequest(BaseModel):
    valence: int = Field(ge=1, le=9)
    arousal: int = Field(ge=1, le=9)
    confidence: int = Field(ge=1, le=5)


class InterruptRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


class CollectionSensorQuality(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    state: str
    quality_score: float = Field(ge=0, le=100)
    timestamp: float
    sequence: int = 0


class CollectionRunnerStateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    session_id: int
    state: CollectionSessionState
    active_baseline: BaselineKind | None
    current_trial_id: int | None
    current_trial_order: int | None
    current_stimulus_id: int | None = None
    current_stimulus_title: str | None = None
    trial_state: TrialState | None
    completed_trials: int
    total_trials: int
    next_trial_order: int | None
    next_trial_id: int | None = None
    next_stimulus_id: int | None = None
    next_stimulus_title: str | None = None
    break_required: bool
    interruption_reason: str | None
    accepted_clean_seconds: float
    wall_clock_seconds: float
    file_recovery_required: bool
    sensors: dict[str, CollectionSensorQuality] = Field(default_factory=lambda: {
        name: CollectionSensorQuality(state="unknown", quality_score=0, timestamp=0)
        for name in ("tp9", "af7", "af8", "tp10")
    })
    sampling_rate_hz: float | None = None
    sampling_rate_ok: bool = False
    live_sensor_ready: bool = False
    stimulus_start_ready: bool = False
    eyes_open_complete: bool = False
    eyes_closed_complete: bool = False
    quality_source: str = "derived_eeg_window"


class ReviewCounts(BaseModel):
    pending: int = 0
    accepted: int = 0
    rejected: int = 0


class QuadrantCounts(BaseModel):
    positive_low: int = 0
    positive_high: int = 0
    negative_low: int = 0
    negative_high: int = 0


class TrialRatingPoint(BaseModel):
    trial_id: int
    session_id: int
    participant_code: str | None = None
    stimulus_title: str
    target_quadrant: str
    valence: int
    arousal: int
    confidence: int
    eeg_file_path: str | None = None
    raw_size_bytes: int | None = None


class QuadrantStat(BaseModel):
    target_count: int = 0
    avg_valence: float | None = None
    avg_arousal: float | None = None


class CollectionOverviewResponse(BaseModel):
    participants: int
    sessions: int
    trials: int
    review_counts: ReviewCounts
    quadrant_counts: QuadrantCounts
    completed_trials: int = 0
    scheduled_trials: int = 0
    total_eeg_bytes: int = 0
    sessions_by_state: dict[str, int] = Field(default_factory=dict)
    ratings_distribution: list[TrialRatingPoint] = Field(default_factory=list)
    quadrant_stats: dict[str, QuadrantStat] = Field(default_factory=dict)


class SessionTrialItemResponse(BaseModel):
    id: int
    randomized_order: int
    stimulus_id: int
    stimulus_title: str
    target_quadrant: str
    state: str
    review_state: str
    valence_rating: int | None = None
    arousal_rating: int | None = None
    confidence: int | None = None
    eeg_file_path: str | None = None
    eeg_checksum: str | None = None
    raw_size_bytes: int | None = None
    duration_seconds: float | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class SessionTrialsDetailResponse(BaseModel):
    session_id: int
    participant_id: int
    participant_code: str
    device_id: str | None = None
    device_name: str | None = None
    state: str
    completed_trials: int
    total_trials: int
    total_eeg_bytes: int = 0
    avg_valence: float | None = None
    avg_arousal: float | None = None
    items: list[SessionTrialItemResponse]
