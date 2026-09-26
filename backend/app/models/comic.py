from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Comic(Base):
    """Generated 4-panel comic with prompt and image URLs."""

    __tablename__ = "comics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="รหัสการ์ตูนที่สร้างขึ้น (Primary Key)")
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True, comment="รหัสผู้ใช้ที่เป็นเจ้าของ (FK -> users.id)")
    session_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("eeg_sessions.id"), nullable=True, index=True, comment="รหัสเซสชันคลื่นสมองที่ใช้อารมณ์มากำกับ (FK -> eeg_sessions.id)")
    persona_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("personas.id"), nullable=True, comment="รหัสตัวละคร/สไตล์ที่เลือกใช้ (FK -> personas.id)")

    input_story: Mapped[str] = mapped_column(Text, nullable=False, comment="เนื้อเรื่องหรือข้อความที่ผู้ใช้พิมพ์เข้ามา")
    generated_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="พรอมต์ที่ AI สรุปสำหรับนำไปสร้างภาพ")

    # 4-panel image URLs
    panel_1_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, comment="URL ภาพการ์ตูนช่องที่ 1")
    panel_2_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, comment="URL ภาพการ์ตูนช่องที่ 2")
    panel_3_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, comment="URL ภาพการ์ตูนช่องที่ 3")
    panel_4_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, comment="URL ภาพการ์ตูนช่องที่ 4")

    # Panel dialogues from Gemini
    panel_1_dialogue: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="บทสนทนาหรือคำบรรยายการ์ตูนช่องที่ 1")
    panel_2_dialogue: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="บทสนทนาหรือคำบรรยายการ์ตูนช่องที่ 2")
    panel_3_dialogue: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="บทสนทนาหรือคำบรรยายการ์ตูนช่องที่ 3")
    panel_4_dialogue: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="บทสนทนาหรือคำบรรยายการ์ตูนช่องที่ 4")

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), comment="เวลาที่สร้างการ์ตูน")

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="comics")  # type: ignore[name-defined]
    session: Mapped[Optional["EEGSession"]] = relationship("EEGSession", back_populates="comics")  # type: ignore[name-defined]
    persona: Mapped[Optional["Persona"]] = relationship("Persona", back_populates="comics")  # type: ignore[name-defined]
    ratings: Mapped[list["Rating"]] = relationship("Rating", back_populates="comic", cascade="all, delete-orphan")


class Rating(Base):
    """User satisfaction rating per comic (1-5 stars + optional feedback)."""

    __tablename__ = "ratings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="รหัสการให้คะแนนความพึงพอใจการ์ตูน (Primary Key)")
    comic_id: Mapped[int] = mapped_column(Integer, ForeignKey("comics.id"), nullable=False, index=True, comment="รหัสการ์ตูนที่ให้คะแนน (FK -> comics.id)")
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, comment="รหัสผู้ใช้ที่ให้คะแนน (FK -> users.id)")
    stars: Mapped[int] = mapped_column(Integer, nullable=False, comment="คะแนนความพึงพอใจ (1 ถึง 5 ดาว)")  # 1-5
    feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="ความคิดเห็นหรือข้อเสนอแนะเพิ่มเติม")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), comment="เวลาที่ให้คะแนน")

    comic: Mapped[Comic] = relationship("Comic", back_populates="ratings")
    user: Mapped["User"] = relationship("User", back_populates="ratings")  # type: ignore[name-defined]
