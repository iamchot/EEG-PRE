from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Comic(Base):
    """Generated 4-panel comic with prompt and image URLs."""

    __tablename__ = "comics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    session_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("eeg_sessions.id"), nullable=True, index=True)
    persona_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("personas.id"), nullable=True)

    input_story: Mapped[str] = mapped_column(Text, nullable=False)
    generated_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 4-panel image URLs
    panel_1_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    panel_2_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    panel_3_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    panel_4_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Panel dialogues from Gemini
    panel_1_dialogue: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    panel_2_dialogue: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    panel_3_dialogue: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    panel_4_dialogue: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="comics")  # type: ignore[name-defined]
    session: Mapped[Optional["EEGSession"]] = relationship("EEGSession", back_populates="comics")  # type: ignore[name-defined]
    persona: Mapped[Optional["Persona"]] = relationship("Persona", back_populates="comics")  # type: ignore[name-defined]
    ratings: Mapped[list["Rating"]] = relationship("Rating", back_populates="comic", cascade="all, delete-orphan")


class Rating(Base):
    """User satisfaction rating per comic (1-5 stars + optional feedback)."""

    __tablename__ = "ratings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    comic_id: Mapped[int] = mapped_column(Integer, ForeignKey("comics.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    stars: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-5
    feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    comic: Mapped[Comic] = relationship("Comic", back_populates="ratings")
    user: Mapped["User"] = relationship("User", back_populates="ratings")  # type: ignore[name-defined]
