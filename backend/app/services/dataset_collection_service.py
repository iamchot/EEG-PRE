from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.dataset_collection import (
    CollectionSession,
    CollectionSessionState,
    DatasetParticipant,
    EmotionStimulus,
    ParticipantState,
)
from app.schemas.dataset_collection import StimulusCreate
from app.services.trial_scheduler import ScheduleUnavailableError, create_trial_schedule


class DatasetCollectionError(Exception):
    """Base exception for collection-domain failures."""


class DatasetConflictError(DatasetCollectionError):
    """Raised when a collection-domain unique value already exists."""


class ParticipantUnavailableError(DatasetCollectionError):
    """Raised when a participant cannot begin a collection session."""


def allocate_participant_code(db: Session) -> str:
    codes = db.scalars(select(DatasetParticipant.participant_code)).all()
    suffixes = [int(code[1:]) for code in codes if code.startswith("P") and code[1:].isdigit()]
    return f"P{max(suffixes, default=0) + 1:03d}"


def create_participant(db: Session, consent_confirmed_at: datetime) -> DatasetParticipant:
    for _ in range(3):
        participant = DatasetParticipant(
            participant_code=allocate_participant_code(db),
            consent_confirmed_at=consent_confirmed_at,
            state=ParticipantState.active,
        )
        db.add(participant)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            continue
        db.refresh(participant)
        return participant
    raise DatasetConflictError("Unable to allocate a unique participant code")


def create_stimulus(db: Session, body: StimulusCreate) -> EmotionStimulus:
    stimulus = EmotionStimulus(**body.model_dump())
    db.add(stimulus)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise DatasetConflictError("A stimulus with this checksum already exists") from exc
    db.refresh(stimulus)
    return stimulus


def create_collection_session(
    db: Session,
    participant_id: int,
    device_id: str | None,
    device_name: str | None,
) -> CollectionSession:
    participant = db.get(DatasetParticipant, participant_id)
    if participant is None or participant.state is not ParticipantState.active:
        raise ParticipantUnavailableError("Participant is unavailable for collection")

    collection_session = CollectionSession(
        participant_id=participant_id,
        device_id=device_id,
        device_name=device_name,
        completed_trials=0,
        total_trials=0,
        state=CollectionSessionState.preparation,
    )
    db.add(collection_session)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise DatasetConflictError("Unable to create collection session") from exc
    db.refresh(collection_session)
    return collection_session
