from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.dataset_collection import (
    CollectionSessionState,
    ParticipantState,
    Quadrant,
    StimulusApprovalState,
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


class CollectionOverviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    participant_count: int
    stimulus_count: int
    session_count: int
