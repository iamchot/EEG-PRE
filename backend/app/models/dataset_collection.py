from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
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


class BaselineKind(str, enum.Enum):
    eyes_open = "eyes_open"
    eyes_closed = "eyes_closed"


class TrialState(str, enum.Enum):
    scheduled = "scheduled"
    rest = "rest"
    stimulus = "stimulus"
    rating = "rating"
    completed = "completed"
    interrupted = "interrupted"
    failed = "failed"


class ReviewState(str, enum.Enum):
    pending = "pending"
    accepted = "accepted"
    rejected = "rejected"


class DatasetParticipant(Base):
    __tablename__ = "dataset_participants"

    id: Mapped[int] = mapped_column(primary_key=True, comment="รหัสผู้เข้าร่วมในระบบ (Primary Key)")
    participant_code: Mapped[str] = mapped_column(String(20), unique=True, index=True, comment="รหัสนามสมมติของผู้เข้าร่วม เช่น P001, P002")
    consent_confirmed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, comment="วันที่และเวลายินยอมเข้าร่วมการทดลอง (Informed Consent)")
    state: Mapped[ParticipantState] = mapped_column(Enum(ParticipantState), default=ParticipantState.active, comment="สถานะผู้เข้าร่วม (active = ร่วมวิจัย, withdrawn = ถอนตัว)")
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime, comment="วันที่และเวลาที่แจ้งถอนตัวจากการทดลอง (ถ้ามี)")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), comment="วันที่และเวลาที่ลงทะเบียนผู้เข้าร่วม")


class EmotionStimulus(Base):
    __tablename__ = "emotion_stimuli"

    id: Mapped[int] = mapped_column(primary_key=True, comment="รหัสสิ่งเร้าอารมณ์ (Primary Key)")
    title: Mapped[str] = mapped_column(String(150), comment="ชื่อคลิปวิดีโอหรือสิ่งเร้าอารมณ์")
    file_path: Mapped[str] = mapped_column(String(500), comment="ที่อยู่ไฟล์วิดีโอบนเซิร์ฟเวอร์")
    checksum: Mapped[str] = mapped_column(String(64), unique=True, comment="ค่าแฮช SHA-256 ของไฟล์วิดีโอเพื่อความถูกต้องสมบูรณ์")
    duration_seconds: Mapped[float] = mapped_column(Float, comment="ความยาวของคลิปวิดีโอ (วินาที)")
    target_quadrant: Mapped[Quadrant] = mapped_column(Enum(Quadrant), index=True, comment="พิกัดอารมณ์เป้าหมาย (positive_high, positive_low, negative_high, negative_low)")
    approval_state: Mapped[StimulusApprovalState] = mapped_column(Enum(StimulusApprovalState), comment="สถานะการอนุมัติสื่อ (draft, approved, retired)")
    stimulus_set_version: Mapped[str] = mapped_column(String(30), comment="เวอร์ชันของชุดสื่อสิ่งเร้า เช่น v1.0")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), comment="วันที่บันทึกสิ่งเร้าเข้าสู่ระบบ")


class CollectionSession(Base):
    __tablename__ = "collection_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, comment="รหัสรอบการเก็บข้อมูลการทดลอง (Primary Key)")
    participant_id: Mapped[int] = mapped_column(ForeignKey("dataset_participants.id"), index=True, comment="รหัสผู้เข้าร่วมที่ทำการทดลอง (FK -> dataset_participants.id)")
    device_id: Mapped[str | None] = mapped_column(String(100), comment="รหัสอุปกรณ์ Muse Headset (BLE Address / MAC)")
    device_name: Mapped[str | None] = mapped_column(String(100), comment="ชื่ออุปกรณ์ Muse ที่เชื่อมต่อ เช่น Muse-2016")
    eyes_open_baseline_path: Mapped[str | None] = mapped_column(String(500), comment="พาธไฟล์ CSV สัญญาณ Baseline ลืมตา 60 วินาที")
    eyes_open_baseline_checksum: Mapped[str | None] = mapped_column(String(64), comment="ค่าแฮช SHA-256 ของไฟล์ Baseline ลืมตา")
    eyes_closed_baseline_path: Mapped[str | None] = mapped_column(String(500), comment="พาธไฟล์ CSV สัญญาณ Baseline หลับตา 60 วินาที")
    eyes_closed_baseline_checksum: Mapped[str | None] = mapped_column(String(64), comment="ค่าแฮช SHA-256 ของไฟล์ Baseline หลับตา")
    eyes_open_accepted_clean_seconds: Mapped[float] = mapped_column(Float, default=0.0, comment="เวลาคลื่นสะอาดที่บันทึกได้ใน Baseline ลืมตา (วินาที)")
    eyes_open_wall_clock_seconds: Mapped[float] = mapped_column(Float, default=0.0, comment="เวลาจริงทั้งหมดที่ใช้บันทึก Baseline ลืมตา (วินาที)")
    eyes_closed_accepted_clean_seconds: Mapped[float] = mapped_column(Float, default=0.0, comment="เวลาคลื่นสะอาดที่บันทึกได้ใน Baseline หลับตา (วินาที)")
    eyes_closed_wall_clock_seconds: Mapped[float] = mapped_column(Float, default=0.0, comment="เวลาจริงทั้งหมดที่ใช้บันทึก Baseline หลับตา (วินาที)")
    active_baseline: Mapped[BaselineKind | None] = mapped_column(Enum(BaselineKind), comment="Baseline ที่กำลังทำการบันทึกอยู่ (eyes_open หรือ eyes_closed)")
    current_trial_id: Mapped[int | None] = mapped_column(ForeignKey("collection_trials.id"), index=True, comment="รหัส Trial ปัจจุบันที่กำลังดำเนินการ (FK -> collection_trials.id)")
    interruption_reason: Mapped[str | None] = mapped_column(Text, comment="สาเหตุการหยุดชะงักระหว่างการทดลอง")
    recovery_at: Mapped[datetime | None] = mapped_column(DateTime, comment="วันที่และเวลาที่กู้คืนเซสชันหลังหยุดชะงัก")
    completed_trials: Mapped[int] = mapped_column(Integer, default=0, comment="จำนวน Trial ที่เสร็จสมบูรณ์แล้ว")
    total_trials: Mapped[int] = mapped_column(Integer, default=0, comment="จำนวน Trial ทั้งหมดในเซสชันนี้")
    state: Mapped[CollectionSessionState] = mapped_column(
        Enum(CollectionSessionState), default=CollectionSessionState.preparation, index=True,
        comment="สถานะเซสชัน (preparation, baseline, ready, in_progress, completed, interrupted, withdrawn, failed)"
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime, comment="เวลาที่เริ่มเซสชันการทดลอง")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, comment="เวลาที่เสร็จสิ้นการทดลอง")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), comment="เวลาที่สร้างเซสชัน")


class CollectionTrial(Base):
    __tablename__ = "collection_trials"
    __table_args__ = (
        CheckConstraint("valence_rating BETWEEN 1 AND 9", name="ck_collection_trials_valence"),
        CheckConstraint("arousal_rating BETWEEN 1 AND 9", name="ck_collection_trials_arousal"),
        CheckConstraint("confidence BETWEEN 1 AND 5", name="ck_collection_trials_confidence"),
        UniqueConstraint(
            "session_id",
            "randomized_order",
            name="uq_collection_trials_session_randomized_order",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, comment="รหัสรอบการทดสอบคลิปสิ่งเร้า (Primary Key)")
    session_id: Mapped[int] = mapped_column(ForeignKey("collection_sessions.id"), index=True, comment="รหัสเซสชันการทดลอง (FK -> collection_sessions.id)")
    stimulus_id: Mapped[int] = mapped_column(ForeignKey("emotion_stimuli.id"), index=True, comment="รหัสคลิปสิ่งเร้าที่เปิดในรอบนี้ (FK -> emotion_stimuli.id)")
    randomized_order: Mapped[int] = mapped_column(Integer, comment="ลำดับของ Trial ที่ถูกสุ่ม (1 ถึง N)")
    valence_rating: Mapped[int | None] = mapped_column(Integer, comment="คะแนนประเมินสุข/ทุกข์ที่ผู้ใช้ประเมินตนเอง (SAM Scale 1-9: 1=ลบมาก, 9=บวกมาก)")
    arousal_rating: Mapped[int | None] = mapped_column(Integer, comment="คะแนนประเมินความตื่นตัวที่ผู้ใช้ประเมินตนเอง (SAM Scale 1-9: 1=สงบ, 9=ตื่นเต้นมาก)")
    confidence: Mapped[int | None] = mapped_column(Integer, comment="ความมั่นใจของผู้ใช้ต่อคะแนนประเมินอารมณ์ตนเอง (1-5)")
    valence_label: Mapped[bool | None] = mapped_column(Boolean, comment="ป้ายกำกับอารมณ์ด้าน Valence (1=Positive/สุข, 0=Negative/ทุกข์)")
    arousal_label: Mapped[bool | None] = mapped_column(Boolean, comment="ป้ายกำกับอารมณ์ด้าน Arousal (1=High Arousal/ตื่นเต้น, 0=Low Arousal/สงบ)")
    valid_valence_label: Mapped[bool] = mapped_column(Boolean, default=False, comment="แฟล็กยืนยันว่า Valence ชัดเจนสำหรับเทรนโมเดล (ตัดคะแนนก้ำกึ่ง 5 ออก)")
    valid_arousal_label: Mapped[bool] = mapped_column(Boolean, default=False, comment="แฟล็กยืนยันว่า Arousal ชัดเจนสำหรับเทรนโมเดล (ตัดคะแนนก้ำกึ่ง 5 ออก)")
    qc_summary_json: Mapped[str | None] = mapped_column(Text, comment="สรุปผลตรวจคุณภาพสัญญาณคลื่นสมอง (เฉลี่ย 4 ขั้ว, จำนวน Blink, สิ่งรบกวน)")
    eeg_file_path: Mapped[str | None] = mapped_column(String(500), comment="พาธไฟล์ CSV ที่เก็บสัญญาณคลื่นสมองดิบ/สะอาดขณะดูคลิปนี้ (จุดเก็บข้อมูลคลื่น!)")
    eeg_checksum: Mapped[str | None] = mapped_column(String(64), comment="ค่าแฮช SHA-256 ของไฟล์ CSV คลื่นสมองเพื่อป้องกันการแก้ไข")
    state: Mapped[TrialState] = mapped_column(Enum(TrialState), default=TrialState.scheduled, index=True, comment="สถานะรอบการทดสอบ (scheduled, rest, stimulus, rating, completed, interrupted, failed)")
    rest_started_at: Mapped[datetime | None] = mapped_column(DateTime, comment="เวลาที่เริ่มช่วงพักสายตาก่อนดูคลิป (Rest 15s)")
    stimulus_started_at: Mapped[datetime | None] = mapped_column(DateTime, comment="เวลาที่เริ่มเปิดคลิปและเริ่มบันทึกคลื่นสมอง")
    rating_started_at: Mapped[datetime | None] = mapped_column(DateTime, comment="เวลาที่เริ่มทำแบบประเมินตนเองหลังคลิปจบ")
    failure_reason: Mapped[str | None] = mapped_column(Text, comment="สาเหตุความล้มเหลวของรอบนี้ (ถ้ามี)")
    raw_size_bytes: Mapped[int | None] = mapped_column(Integer, comment="ขนาดไฟล์ CSV ของคลื่นสมอง (ไบต์)")
    accepted_clean_seconds: Mapped[float] = mapped_column(Float, default=0.0, comment="จำนวนวินาทีของสัญญาณคลื่นที่สะอาดผ่านเกณฑ์ QC ขณะดูคลิป")
    wall_clock_seconds: Mapped[float] = mapped_column(Float, default=0.0, comment="เวลาจริงทั้งหมดที่บันทึกคลื่นขณะดูคลิป (วินาที)")
    review_state: Mapped[ReviewState] = mapped_column(Enum(ReviewState), default=ReviewState.pending, index=True, comment="สถานะการตรวจประเมินข้อมูล (pending=รอตรวจ, accepted=ผ่านนำไปเทรนได้, rejected=ไม่ผ่าน)")
    started_at: Mapped[datetime | None] = mapped_column(DateTime, comment="เวลาที่เริ่มรอบ Trial")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, comment="เวลาที่เสร็จสิ้นรอบ Trial")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), comment="เวลาที่สร้างข้อมูล Trial")


class ArtifactEvent(Base):
    __tablename__ = "artifact_events"

    id: Mapped[int] = mapped_column(primary_key=True, comment="รหัสเหตุการณ์สัญญาณรบกวน (Primary Key)")
    trial_id: Mapped[int] = mapped_column(ForeignKey("collection_trials.id"), index=True, comment="รหัส Trial ที่เกิดสัญญาณรบกวน (FK -> collection_trials.id)")
    event_type: Mapped[str] = mapped_column(String(50), comment="ประเภทของสิ่งรบกวน เช่น blink (กะพริบตา), jaw_clench (ขบฟัน), contact_loss (เซนเซอร์หลุด)")
    start_seconds: Mapped[float] = mapped_column(Float, comment="วินาทีเริ่มต้นที่ตรวจพบสิ่งรบกวนนับจากเริ่มคลิป")
    duration_seconds: Mapped[float] = mapped_column(Float, comment="ระยะเวลาที่เกิดสิ่งรบกวน (วินาที)")
    details_json: Mapped[str | None] = mapped_column(Text, comment="รายละเอียดเพิ่มเติมเชิงเทคนิค (JSON)")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), comment="เวลาที่บันทึกข้อมูล")


class DatasetVersion(Base):
    __tablename__ = "dataset_versions"

    id: Mapped[int] = mapped_column(primary_key=True, comment="รหัสเวอร์ชันชุดข้อมูล (Primary Key)")
    version: Mapped[str] = mapped_column(String(30), unique=True, comment="เลขเวอร์ชันของ Dataset สำหรับเทรนโมเดล เช่น v1.0.0")
    manifest_json: Mapped[str] = mapped_column(Text, comment="รายการข้อมูล Manifest (รายการ Trials, ไฟล์คลื่น, Label, ข้อมูลแบ่ง Train/Val/Test)")
    manifest_checksum: Mapped[str] = mapped_column(String(64), unique=True, comment="ค่าแฮช SHA-256 ของ Manifest JSON เพื่อความถูกต้องของชุดข้อมูล")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), comment="วันที่จัดทำเวอร์ชันของชุดข้อมูล")


class ModelVersion(Base):
    __tablename__ = "model_versions"

    id: Mapped[int] = mapped_column(primary_key=True, comment="รหัสโมเดล Machine Learning (Primary Key)")
    version: Mapped[str] = mapped_column(String(30), unique=True, comment="เลขเวอร์ชันของโมเดล เช่น emotion-clf-v1.0")
    dataset_version: Mapped[str] = mapped_column(String(30), comment="เวอร์ชันของ Dataset ที่ใช้เทรนโมเดลนี้ (อ้างอิง dataset_versions.version)")
    artifact_path: Mapped[str] = mapped_column(String(500), comment="พาธไฟล์น้ำหนักโมเดลที่บันทึกไว้ (.onnx, .pkl, .pt)")
    artifact_checksum: Mapped[str] = mapped_column(String(64), unique=True, comment="ค่าแฮช SHA-256 ของไฟล์โมเดล")
    metadata_json: Mapped[str] = mapped_column(Text, comment="ข้อมูลประสิทธิภาพโมเดล (Accuracy, F1-Score, Hyperparameters)")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), comment="วันที่บันทึกโมเดล")
