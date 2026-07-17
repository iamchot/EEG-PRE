from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth_middleware import AdminUser
from app.models.dataset_collection import (
    CollectionSession,
    CollectionTrial,
    DatasetParticipant,
    EmotionStimulus,
    Quadrant,
    ReviewState,
)
from app.schemas.dataset_collection import (
    CollectionSessionCreate,
    CollectionSessionListResponse,
    CollectionSessionResponse,
    ParticipantCreate,
    ParticipantListResponse,
    ParticipantResponse,
    StimulusCreate,
    StimulusListResponse,
    StimulusResponse,
)
from app.services.dataset_collection_service import (
    DatasetConflictError,
    ParticipantUnavailableError,
    create_collection_session,
    create_participant,
    create_stimulus,
)

router = APIRouter(prefix="/admin/dataset-collection", tags=["Admin Dataset Collection"])


class ReviewCounts(BaseModel):
    pending: int = 0
    accepted: int = 0
    rejected: int = 0


class QuadrantCounts(BaseModel):
    positive_low: int = 0
    positive_high: int = 0
    negative_low: int = 0
    negative_high: int = 0


class CollectionOverviewResponse(BaseModel):
    participants: int
    sessions: int
    trials: int
    review_counts: ReviewCounts
    quadrant_counts: QuadrantCounts


@router.get("/overview", response_model=CollectionOverviewResponse)
def collection_overview(admin: AdminUser, db: Session = Depends(get_db)):
    review_rows = db.execute(
        select(CollectionTrial.review_state, func.count(CollectionTrial.id)).group_by(CollectionTrial.review_state)
    ).all()
    quadrant_rows = db.execute(
        select(EmotionStimulus.target_quadrant, func.count(EmotionStimulus.id)).group_by(
            EmotionStimulus.target_quadrant
        )
    ).all()
    review_counts = {state.value: count for state, count in review_rows}
    quadrant_counts = {quadrant.value: count for quadrant, count in quadrant_rows}
    return CollectionOverviewResponse(
        participants=db.scalar(select(func.count(DatasetParticipant.id))) or 0,
        sessions=db.scalar(select(func.count(CollectionSession.id))) or 0,
        trials=db.scalar(select(func.count(CollectionTrial.id))) or 0,
        review_counts={state.value: review_counts.get(state.value, 0) for state in ReviewState},
        quadrant_counts={quadrant.value: quadrant_counts.get(quadrant.value, 0) for quadrant in Quadrant},
    )


@router.get("/participants", response_model=ParticipantListResponse)
def list_participants(
    admin: AdminUser,
    db: Session = Depends(get_db),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
):
    query = select(DatasetParticipant).order_by(DatasetParticipant.id).offset(skip).limit(limit)
    return ParticipantListResponse(items=list(db.scalars(query)))


@router.post("/participants", response_model=ParticipantResponse, status_code=status.HTTP_201_CREATED)
def add_participant(body: ParticipantCreate, admin: AdminUser, db: Session = Depends(get_db)):
    try:
        return create_participant(db, body.consent_confirmed_at)
    except DatasetConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("/stimuli", response_model=StimulusListResponse)
def list_stimuli(
    admin: AdminUser,
    db: Session = Depends(get_db),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
):
    query = select(EmotionStimulus).order_by(EmotionStimulus.id).offset(skip).limit(limit)
    return StimulusListResponse(items=list(db.scalars(query)))


@router.post("/stimuli", response_model=StimulusResponse, status_code=status.HTTP_201_CREATED)
def add_stimulus(body: StimulusCreate, admin: AdminUser, db: Session = Depends(get_db)):
    try:
        return create_stimulus(db, body)
    except DatasetConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("/sessions", response_model=CollectionSessionListResponse)
def list_sessions(
    admin: AdminUser,
    db: Session = Depends(get_db),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
):
    query = select(CollectionSession).order_by(CollectionSession.id).offset(skip).limit(limit)
    return CollectionSessionListResponse(items=list(db.scalars(query)))


@router.post("/sessions", response_model=CollectionSessionResponse, status_code=status.HTTP_201_CREATED)
def add_session(body: CollectionSessionCreate, admin: AdminUser, db: Session = Depends(get_db)):
    try:
        return create_collection_session(db, body.participant_id, body.device_id, body.device_name)
    except ParticipantUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except DatasetConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
