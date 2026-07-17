from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel


ART_STYLES = Literal["Webtoon", "Manga", "American Comic", "Comic"]


class PersonaCreate(BaseModel):
    persona_name: str
    appearance: Optional[str] = None
    art_style: ART_STYLES = "Manga"


class PersonaUpdate(BaseModel):
    persona_name: Optional[str] = None
    appearance: Optional[str] = None
    art_style: Optional[ART_STYLES] = None


class PersonaOut(BaseModel):
    id: int
    user_id: int
    persona_name: str
    appearance: Optional[str]
    art_style: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
