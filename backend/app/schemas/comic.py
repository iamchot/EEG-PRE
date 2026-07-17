from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator


class ComicGenerateRequest(BaseModel):
    session_id: int
    persona_id: Optional[int] = None
    input_story: str
    art_style: str = "Manga"


class PanelOut(BaseModel):
    panel_number: int
    image_url: Optional[str]
    dialogue: Optional[str]


class ComicOut(BaseModel):
    id: int
    user_id: int
    session_id: Optional[int]
    persona_id: Optional[int]
    input_story: str
    generated_prompt: Optional[str]
    panel_1_url: Optional[str]
    panel_2_url: Optional[str]
    panel_3_url: Optional[str]
    panel_4_url: Optional[str]
    panel_1_dialogue: Optional[str]
    panel_2_dialogue: Optional[str]
    panel_3_dialogue: Optional[str]
    panel_4_dialogue: Optional[str]
    emotion: Optional[str] = None  # joined from EmotionResult
    persona_name: Optional[str] = None  # joined from Persona
    created_at: datetime

    model_config = {"from_attributes": True}


class RatingCreate(BaseModel):
    comic_id: int
    stars: int
    feedback: Optional[str] = None

    @field_validator("stars")
    @classmethod
    def stars_range(cls, v: int) -> int:
        if v < 1 or v > 5:
            raise ValueError("Stars must be between 1 and 5")
        return v


class RatingOut(BaseModel):
    id: int
    comic_id: int
    stars: int
    feedback: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}
