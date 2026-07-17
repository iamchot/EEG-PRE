from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Persona(Base):
    __tablename__ = "personas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    persona_name: Mapped[str] = mapped_column(String(100), nullable=False)
    appearance: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    art_style: Mapped[str] = mapped_column(String(50), nullable=False, default="Manga")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship("User", back_populates="personas")  # type: ignore[name-defined]
    comics: Mapped[list["Comic"]] = relationship("Comic", back_populates="persona")  # type: ignore[name-defined]
