import random
import secrets

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.dataset_collection import (
    CollectionSession,
    CollectionSessionState,
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


def _load_trials(db: Session, session_id: int) -> list[CollectionTrial]:
    return list(
        db.scalars(
            select(CollectionTrial)
            .where(CollectionTrial.session_id == session_id)
            .order_by(CollectionTrial.randomized_order)
        )
    )


def _has_complete_schedule_rows(trials: list[CollectionTrial]) -> bool:
    return (
        len(trials) == TOTAL_TRIALS
        and [trial.randomized_order for trial in trials] == list(range(1, TOTAL_TRIALS + 1))
        and len({trial.stimulus_id for trial in trials}) == TOTAL_TRIALS
    )


def has_complete_trial_schedule(db: Session, session: CollectionSession) -> bool:
    return (
        session.total_trials == TOTAL_TRIALS
        and _has_complete_schedule_rows(_load_trials(db, session.id))
    )


def _reload_winner_schedule(db: Session, session_id: int) -> list[CollectionTrial]:
    winner_session = db.get(CollectionSession, session_id)
    winner_trials = _load_trials(db, session_id)
    if (
        winner_session is not None
        and winner_session.total_trials == TOTAL_TRIALS
        and _has_complete_schedule_rows(winner_trials)
    ):
        return winner_trials
    raise ScheduleUnavailableError("Unable to create trial schedule")


def create_trial_schedule(
    db: Session,
    session: CollectionSession,
    *,
    seed: int | None = None,
) -> list[CollectionTrial]:
    session_id = session.id
    try:
        locked_session = db.scalars(
            select(CollectionSession)
            .where(CollectionSession.id == session_id)
            .with_for_update()
        ).one_or_none()
        if locked_session is None:
            raise ScheduleUnavailableError("Unable to create trial schedule")
        if (
            locked_session.state is not CollectionSessionState.preparation
            or not locked_session.device_id
        ):
            raise ScheduleUnavailableError(
                "Trial schedule requires preparation with a selected device"
            )

        existing = _load_trials(db, session_id)
        if existing:
            if not _has_complete_schedule_rows(existing):
                raise ScheduleUnavailableError("Unable to create trial schedule")
            locked_session.total_trials = TOTAL_TRIALS
            db.commit()
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
                session_id=session_id,
                stimulus_id=stimulus.id,
                randomized_order=order,
                state=TrialState.scheduled,
            )
            for order, stimulus in enumerate(selected, start=1)
        ]
        db.add_all(trials)
        locked_session.total_trials = TOTAL_TRIALS
        db.commit()
        return trials
    except IntegrityError as exc:
        db.rollback()
        try:
            return _reload_winner_schedule(db, session_id)
        except SQLAlchemyError as reload_exc:
            db.rollback()
            raise ScheduleUnavailableError("Unable to create trial schedule") from reload_exc
        except ScheduleUnavailableError:
            raise ScheduleUnavailableError("Unable to create trial schedule") from exc
    except ScheduleUnavailableError:
        db.rollback()
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        raise ScheduleUnavailableError("Unable to create trial schedule") from exc
