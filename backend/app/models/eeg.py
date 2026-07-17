from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SessionStatus(str, enum.Enum):
    baseline = "baseline"
    recording = "recording"
    completed = "completed"
    timeout = "timeout"
    cancelled = "cancelled"
    failed = "failed"


class EmotionLabel(str, enum.Enum):
    happy = "happy"
    sad = "sad"
    stressed = "stressed"
    excited = "excited"


class EEGSession(Base):
    """One EEG recording session per comic generation attempt."""

    __tablename__ = "eeg_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    device_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    device_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    baseline_duration: Mapped[int] = mapped_column(Integer, default=20, comment="target baseline seconds")
    accepted_recording_duration: Mapped[int] = mapped_column(Integer, default=30, comment="target accepted seconds")
    wall_clock_duration: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="actual elapsed seconds")
    rejected_epoch_count: Mapped[int] = mapped_column(Integer, default=0)
    pause_count: Mapped[int] = mapped_column(Integer, default=0)
    raw_data_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    status: Mapped[SessionStatus] = mapped_column(
        Enum(SessionStatus), nullable=False, default=SessionStatus.baseline
    )
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    features: Mapped[list["EEGFeature"]] = relationship(
        "EEGFeature", back_populates="session", cascade="all, delete-orphan"
    )
    emotion_result: Mapped[Optional["EmotionResult"]] = relationship(
        "EmotionResult", back_populates="session", uselist=False, cascade="all, delete-orphan"
    )
    comics: Mapped[list["Comic"]] = relationship("Comic", back_populates="session")  # type: ignore[name-defined]


class EEGFeature(Base):
    """Per-session feature extraction results (baseline + recording)."""

    __tablename__ = "eeg_features"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("eeg_sessions.id"), nullable=False, index=True)

    # Baseline values (log-transformed)
    baseline_log_alpha_af7: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    baseline_log_alpha_af8: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    baseline_log_beta_af7: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    baseline_log_beta_af8: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    baseline_faa: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="logAlpha(AF8)-logAlpha(AF7)")
    baseline_arousal: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="log(beta/alpha)")

    # Recording values
    recording_faa: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    recording_arousal: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Delta (relative change)
    delta_faa: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    delta_arousal: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Epoch configuration
    epoch_size_seconds: Mapped[float] = mapped_column(Float, default=2.0)
    epoch_overlap_ratio: Mapped[float] = mapped_column(Float, default=0.5)
    feature_version: Mapped[str] = mapped_column(String(20), default="v1.0")

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    session: Mapped[EEGSession] = relationship("EEGSession", back_populates="features")


class EmotionResult(Base):
    """Final emotion classification result for a session."""

    __tablename__ = "emotion_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("eeg_sessions.id"), nullable=False, unique=True)

    final_emotion: Mapped[EmotionLabel] = mapped_column(Enum(EmotionLabel), nullable=False)
    rule_version: Mapped[str] = mapped_column(String(20), default="v1.0")
    threshold_version: Mapped[str] = mapped_column(String(20), default="v1.0")

    valence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    arousal: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    delta_faa: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    delta_arousal: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Quality summary
    quality_score_avg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    accepted_epochs: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    rejected_epochs: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    session: Mapped[EEGSession] = relationship("EEGSession", back_populates="emotion_result")


class DatasetSource(str, enum.Enum):
    manual_entry = "manual_entry"
    user_session = "user_session"


class MLTrainingSample(Base):
    """Labeled EEG training samples for ML classifier.

    Admin can add manual samples or auto-import from completed user sessions.
    Each row represents one labeled data point used for training / evaluation.
    """

    __tablename__ = "ml_training_samples"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Label
    label: Mapped[EmotionLabel] = mapped_column(Enum(EmotionLabel), nullable=False, index=True)

    # EEG feature values (derived from signal_processor)
    focus_pct: Mapped[float] = mapped_column(Float, nullable=False, comment="beta/(alpha+beta) * 100")
    relax_pct: Mapped[float] = mapped_column(Float, nullable=False, comment="alpha/(alpha+beta) * 100")
    delta_faa: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    delta_arousal: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    valence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    arousal: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Data quality / provenance
    source: Mapped[DatasetSource] = mapped_column(
        Enum(DatasetSource), nullable=False, default=DatasetSource.manual_entry
    )
    session_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("eeg_sessions.id"), nullable=True,
        comment="FK to eeg_sessions if source=user_session"
    )
    participant_id: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True, comment="Pseudonymous ID e.g. P001"
    )
    quality_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="0–1 signal quality")
    valid_label: Mapped[bool] = mapped_column(default=True, comment="False = exclude from training")
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

