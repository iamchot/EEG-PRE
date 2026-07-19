import random
import secrets

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.dataset_collection import (
    CollectionSession,
    CollectionTrial,
    EmotionStimulus,
    Quadrant,
    StimulusApprovalState,
    TrialState,
)


REQUIRED_PER_QUADRANT = 3
TOTAL_TRIALS = 12


class ScheduleUnavailableError(Exception):
    """Raised when a balanced schedule cannot be safely persisted."""


def create_trial_schedule(
    db: Session,
    session: CollectionSession,
    *,
    seed: int | None = None,
) -> list[CollectionTrial]:
    existing = list(
        db.scalars(
            select(CollectionTrial)
            .where(CollectionTrial.session_id == session.id)
            .order_by(CollectionTrial.randomized_order)
        )
    )
    if existing:
        return existing

    rng = random.Random(seed) if seed is not None else secrets.SystemRandom()
    selected: list[EmotionStimulus] = []
    for quadrant in Quadrant:
        candidates = list(
            db.scalars(
                select(EmotionStimulus)
                .where(
                    EmotionStimulus.target_quadrant == quadrant,
                    EmotionStimulus.approval_state == StimulusApprovalState.approved,
                )
                .order_by(EmotionStimulus.id)
            )
        )
        if len(candidates) < REQUIRED_PER_QUADRANT:
            raise ScheduleUnavailableError(
                f"At least {REQUIRED_PER_QUADRANT} approved stimuli required for {quadrant.value}"
            )
        selected.extend(rng.sample(candidates, REQUIRED_PER_QUADRANT))

    rng.shuffle(selected)
    trials = [
        CollectionTrial(
            session_id=session.id,
            stimulus_id=stimulus.id,
            randomized_order=order,
            state=TrialState.scheduled,
        )
        for order, stimulus in enumerate(selected, start=1)
    ]
    db.add_all(trials)
    session.total_trials = TOTAL_TRIALS
    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise ScheduleUnavailableError("Unable to create trial schedule") from exc
    return trials
