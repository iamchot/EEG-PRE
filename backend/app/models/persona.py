from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Persona(Base):
    __tablename__ = "personas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="รหัสตัวละคร/สไตล์การ์ตูน (Primary Key)")
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True, comment="รหัสผู้ใช้ที่เป็นเจ้าของตัวละคร (FK -> users.id)")
    persona_name: Mapped[str] = mapped_column(String(100), nullable=False, comment="ชื่อตัวละคร เช่น โนบิ, ฮีโร่")
    appearance: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="คำอธิบายรูปร่างหน้าตาและเครื่องแต่งกายของตัวละคร")
    art_style: Mapped[str] = mapped_column(String(50), nullable=False, default="Manga", comment="สไตล์ภาพวาด (เช่น manga, comic_strip, watercolor)")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), comment="เวลาที่สร้างตัวละคร")
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), comment="เวลาที่แก้ไขตัวละครล่าสุด")

    user: Mapped["User"] = relationship("User", back_populates="personas")  # type: ignore[name-defined]
    comics: Mapped[list["Comic"]] = relationship("Comic", back_populates="persona")  # type: ignore[name-defined]
