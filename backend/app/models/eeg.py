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

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="รหัสเซสชันคลื่นสมองสำหรับแอปการ์ตูน (Primary Key)")
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True, comment="รหัสผู้ใช้งาน (FK -> users.id)")
    device_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment="รหัสอุปกรณ์ Muse Headset")
    device_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment="ชื่ออุปกรณ์ Muse ที่ตรวจพบ")

    baseline_duration: Mapped[int] = mapped_column(Integer, default=20, comment="เวลาเป้าหมายบันทึก Baseline (วินาที เช่น 20s)")
    accepted_recording_duration: Mapped[int] = mapped_column(Integer, default=30, comment="เวลาเป้าหมายของคลื่นสะอาดขณะบันทึก (วินาที เช่น 30s)")
    wall_clock_duration: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="เวลาจริงทั้งหมดที่ใช้บันทึกคลื่น (วินาที)")
    rejected_epoch_count: Mapped[int] = mapped_column(Integer, default=0, comment="จำนวน Epoch ที่ถูกปฏิเสธเนื่องจากมีสิ่งรบกวน")
    pause_count: Mapped[int] = mapped_column(Integer, default=0, comment="จำนวนครั้งที่มีการหยุดชั่วคราว")
    raw_data_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, comment="ที่อยู่ไฟล์บันทึกคลื่นสมองดิบ")

    status: Mapped[SessionStatus] = mapped_column(
        Enum(SessionStatus), nullable=False, default=SessionStatus.baseline,
        comment="สถานะเซสชัน (baseline, recording, completed, timeout, cancelled, failed)"
    )
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), comment="เวลาที่เริ่มบันทึก")
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, comment="เวลาที่บันทึกเสร็จสิ้น")

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

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="รหัสชุดคุณลักษณะคลื่นสมอง (Primary Key)")
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("eeg_sessions.id"), nullable=False, index=True, comment="รหัสเซสชันคลื่นสมอง (FK -> eeg_sessions.id)")

    # Baseline values (log-transformed)
    baseline_log_alpha_af7: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="พลังงานคลื่น Alpha ขั้วหน้าผากซ้ายช่วงพัก Baseline (log-transformed)")
    baseline_log_alpha_af8: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="พลังงานคลื่น Alpha ขั้วหน้าผากขวาช่วงพัก Baseline (log-transformed)")
    baseline_log_beta_af7: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="พลังงานคลื่น Beta ขั้วหน้าผากซ้ายช่วงพัก Baseline (log-transformed)")
    baseline_log_beta_af8: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="พลังงานคลื่น Beta ขั้วหน้าผากขวาช่วงพัก Baseline (log-transformed)")
    baseline_faa: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="ค่าความไม่สมมาตรหน้าผากช่วงพัก FAA: logAlpha(AF8) - logAlpha(AF7)")
    baseline_arousal: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="ค่าความตื่นตัวช่วงพัก Baseline จากอัตราส่วน log(beta/alpha)")

    # Recording values
    recording_faa: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="ค่าความไม่สมมาตรหน้าผากขณะเปิดรับสิ่งเร้า (FAA)")
    recording_arousal: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="ค่าความตื่นตัวขณะเปิดรับสิ่งเร้า (beta/alpha)")

    # Delta (relative change)
    delta_faa: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="ผลต่างการเปลี่ยนแปลงของ FAA จาก Baseline (ใช้จำแนกสุข/ทุกข์)")
    delta_arousal: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="ผลต่างการเปลี่ยนแปลงของความตื่นตัวจาก Baseline (ใช้จำแนกความตื่นเต้น/สงบ)")

    # Epoch configuration
    epoch_size_seconds: Mapped[float] = mapped_column(Float, default=2.0, comment="ขนาดหน้าต่างเวลาที่ใช้ตัดคลื่นวิเคราะห์ (วินาที เช่น 2.0)")
    epoch_overlap_ratio: Mapped[float] = mapped_column(Float, default=0.5, comment="สัดส่วนการซ้อนทับกันของหน้าต่างเวลา (เช่น 0.5)")
    feature_version: Mapped[str] = mapped_column(String(20), default="v1.0", comment="เวอร์ชันอัลกอริทึมการสกัดคุณลักษณะ (เช่น v1.0)")

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), comment="วันที่สกัดคุณลักษณะ")

    session: Mapped[EEGSession] = relationship("EEGSession", back_populates="features")


class EmotionResult(Base):
    """Final emotion classification result for a session."""

    __tablename__ = "emotion_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="รหัสผลการทำนายอารมณ์ (Primary Key)")
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("eeg_sessions.id"), nullable=False, unique=True, comment="รหัสเซสชันคลื่นสมอง (FK -> eeg_sessions.id)")

    final_emotion: Mapped[EmotionLabel] = mapped_column(Enum(EmotionLabel), nullable=False, comment="ผลอารมณ์สุดท้ายที่จำแนกได้ (happy, sad, stressed, excited)")
    rule_version: Mapped[str] = mapped_column(String(20), default="v1.0", comment="เวอร์ชันของกฎเกณฑ์จำแนกอารมณ์")
    threshold_version: Mapped[str] = mapped_column(String(20), default="v1.0", comment="เวอร์ชันของค่าเกณฑ์ตัดสิน (Thresholds)")

    valence: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="ค่าคะแนน Valence ที่คำนวณได้")
    arousal: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="ค่าคะแนน Arousal ที่คำนวณได้")
    delta_faa: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="ค่า Delta FAA ของรอบนี้")
    delta_arousal: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="ค่า Delta Arousal ของรอบนี้")

    # Quality summary
    quality_score_avg: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="คะแนนคุณภาพสัญญาณเฉลี่ยตลอดทั้งรอบ (0.0 ถึง 1.0)")
    accepted_epochs: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="จำนวน Epoch ที่ผ่านเกณฑ์ความสะอาด")
    rejected_epochs: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="จำนวน Epoch ที่ไม่ผ่านเกณฑ์")

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), comment="เวลาที่วิเคราะห์ผลสำเร็จ")

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

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="รหัสตัวอย่างชุดข้อมูลเทรนโมเดล (Primary Key)")

    # Label
    label: Mapped[EmotionLabel] = mapped_column(Enum(EmotionLabel), nullable=False, index=True, comment="ป้ายกำกับอารมณ์เป้าหมาย (happy, sad, stressed, excited)")

    # EEG feature values (derived from signal_processor)
    focus_pct: Mapped[float] = mapped_column(Float, nullable=False, comment="เปอร์เซ็นต์สมาธิจดจ่อ คำนวณจาก beta/(alpha+beta) * 100")
    relax_pct: Mapped[float] = mapped_column(Float, nullable=False, comment="เปอร์เซ็นต์ความผ่อนคลาย คำนวณจาก alpha/(alpha+beta) * 100")
    delta_faa: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="ค่าการเปลี่ยนแปลงความไม่สมมาตรหน้าผาก (FAA Shift เทียบ Baseline)")
    delta_arousal: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="ค่าการเปลี่ยนแปลงความตื่นตัว (Arousal Shift เทียบ Baseline)")
    valence: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="ค่าคะแนนแกน Valence (-1.0 ถึง 1.0 หรือ 1-9)")
    arousal: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="ค่าคะแนนแกน Arousal (-1.0 ถึง 1.0 หรือ 1-9)")

    # Data quality / provenance
    source: Mapped[DatasetSource] = mapped_column(
        Enum(DatasetSource), nullable=False, default=DatasetSource.manual_entry,
        comment="แหล่งที่มาข้อมูล (manual_entry=ป้อนเอง, user_session=ดึงจากเซสชันจริง)"
    )
    session_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("eeg_sessions.id"), nullable=True,
        comment="รหัสเซสชันคลื่นสมองต้นทาง (FK -> eeg_sessions.id)"
    )
    participant_id: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True, comment="รหัสผู้เข้าร่วม เช่น P001"
    )
    quality_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="คะแนนคุณภาพสัญญาณคลื่นสมองเฉลี่ย (0.0 ถึง 1.0)")
    valid_label: Mapped[bool] = mapped_column(default=True, comment="แฟล็กคัดกรอง (True=ผ่านเกณฑ์นำไปเทรนได้, False=ไม่นำมาเทรน)")
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="หมายเหตุเพิ่มเติมเกี่ยวกับตัวอย่างนี้")

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), comment="เวลาที่สร้างตัวอย่าง")
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), comment="เวลาที่แก้ไขล่าสุด")

