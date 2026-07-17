from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Enum, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Quadrant(str, enum.Enum):
    positive_low = "positive_low"
    positive_high = "positive_high"
    negative_low = "negative_low"
    negative_high = "negative_high"


class ParticipantState(str, enum.Enum):
    active = "active"
    withdrawn = "withdrawn"


class StimulusApprovalState(str, enum.Enum):
    draft = "draft"
    approved = "approved"
    retired = "retired"


class CollectionSessionState(str, enum.Enum):
    preparation = "preparation"
    baseline = "baseline"
    ready = "ready"
    in_progress = "in_progress"
    completed = "completed"
    interrupted = "interrupted"
    withdrawn = "withdrawn"
    failed = "failed"


class ReviewState(str, enum.Enum):
    pending = "pending"
    accepted = "accepted"
    rejected = "rejected"


class DatasetParticipant(Base):
    __tablename__ = "dataset_participants"

    id: Mapped[int] = mapped_column(primary_key=True)
    participant_code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    consent_confirmed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    state: Mapped[ParticipantState] = mapped_column(Enum(ParticipantState), default=ParticipantState.active)
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class EmotionStimulus(Base):
    __tablename__ = "emotion_stimuli"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(150))
    file_path: Mapped[str] = mapped_column(String(500))
    checksum: Mapped[str] = mapped_column(String(64), unique=True)
    duration_seconds: Mapped[float] = mapped_column(Float)
    target_quadrant: Mapped[Quadrant] = mapped_column(Enum(Quadrant), index=True)
    approval_state: Mapped[StimulusApprovalState] = mapped_column(Enum(StimulusApprovalState))
    stimulus_set_version: Mapped[str] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class CollectionSession(Base):
    __tablename__ = "collection_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    participant_id: Mapped[int] = mapped_column(ForeignKey("dataset_participants.id"), index=True)
    device_id: Mapped[str] = mapped_column(String(100))
    device_name: Mapped[str | None] = mapped_column(String(100))
    eyes_open_baseline_path: Mapped[str | None] = mapped_column(String(500))
    eyes_open_baseline_checksum: Mapped[str | None] = mapped_column(String(64))
    eyes_closed_baseline_path: Mapped[str | None] = mapped_column(String(500))
    eyes_closed_baseline_checksum: Mapped[str | None] = mapped_column(String(64))
    completed_trials: Mapped[int] = mapped_column(Integer, default=0)
    total_trials: Mapped[int] = mapped_column(Integer, default=0)
    state: Mapped[CollectionSessionState] = mapped_column(
        Enum(CollectionSessionState), default=CollectionSessionState.preparation, index=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class CollectionTrial(Base):
    __tablename__ = "collection_trials"
    __table_args__ = (
        CheckConstraint("valence_rating BETWEEN 1 AND 9", name="ck_collection_trials_valence"),
        CheckConstraint("arousal_rating BETWEEN 1 AND 9", name="ck_collection_trials_arousal"),
        CheckConstraint("confidence BETWEEN 1 AND 5", name="ck_collection_trials_confidence"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("collection_sessions.id"), index=True)
    stimulus_id: Mapped[int] = mapped_column(ForeignKey("emotion_stimuli.id"), index=True)
    randomized_order: Mapped[int] = mapped_column(Integer)
    valence_rating: Mapped[int] = mapped_column(Integer)
    arousal_rating: Mapped[int] = mapped_column(Integer)
    confidence: Mapped[int] = mapped_column(Integer)
    valence_label: Mapped[bool | None] = mapped_column(Boolean)
    arousal_label: Mapped[bool | None] = mapped_column(Boolean)
    valid_valence_label: Mapped[bool] = mapped_column(Boolean, default=False)
    valid_arousal_label: Mapped[bool] = mapped_column(Boolean, default=False)
    qc_summary_json: Mapped[str | None] = mapped_column(Text)
    eeg_file_path: Mapped[str] = mapped_column(String(500))
    eeg_checksum: Mapped[str] = mapped_column(String(64))
    review_state: Mapped[ReviewState] = mapped_column(Enum(ReviewState), default=ReviewState.pending, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ArtifactEvent(Base):
    __tablename__ = "artifact_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    trial_id: Mapped[int] = mapped_column(ForeignKey("collection_trials.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(50))
    start_seconds: Mapped[float] = mapped_column(Float)
    duration_seconds: Mapped[float] = mapped_column(Float)
    details_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class DatasetVersion(Base):
    __tablename__ = "dataset_versions"

    id: Mapped[int] = mapped_column(primary_key=True)
    version: Mapped[str] = mapped_column(String(30), unique=True)
    manifest_json: Mapped[str] = mapped_column(Text)
    manifest_checksum: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ModelVersion(Base):
    __tablename__ = "model_versions"

    id: Mapped[int] = mapped_column(primary_key=True)
    version: Mapped[str] = mapped_column(String(30), unique=True)
    dataset_version: Mapped[str] = mapped_column(String(30))
    artifact_path: Mapped[str] = mapped_column(String(500))
    artifact_checksum: Mapped[str] = mapped_column(String(64), unique=True)
    metadata_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
