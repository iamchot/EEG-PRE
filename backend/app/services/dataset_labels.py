from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


AxisLabel = Literal["negative", "positive", "low", "high"]
ValenceLabel = Literal["negative", "positive"]
ArousalLabel = Literal["low", "high"]


class RatingInput(BaseModel):
    model_config = ConfigDict(frozen=True)

    valence: int = Field(ge=1, le=9, strict=True)
    arousal: int = Field(ge=1, le=9, strict=True)
    confidence: int = Field(ge=1, le=5, strict=True)


class DerivedLabels(BaseModel):
    model_config = ConfigDict(frozen=True)

    valence_label: ValenceLabel | None
    arousal_label: ArousalLabel | None
    valid_valence_label: bool
    valid_arousal_label: bool


def derive_labels(valence: int, arousal: int, confidence: int) -> DerivedLabels:
    rating = RatingInput(
        valence=valence,
        arousal=arousal,
        confidence=confidence,
    )
    confident = rating.confidence >= 3
    return DerivedLabels(
        valence_label=(
            None
            if rating.valence == 5
            else ("negative" if rating.valence <= 4 else "positive")
        ),
        arousal_label=(
            None
            if rating.arousal == 5
            else ("low" if rating.arousal <= 4 else "high")
        ),
        valid_valence_label=confident and rating.valence != 5,
        valid_arousal_label=confident and rating.arousal != 5,
    )
