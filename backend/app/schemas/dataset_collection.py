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
