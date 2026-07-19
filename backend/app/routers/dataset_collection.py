import hashlib
import mimetypes
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from starlette.responses import FileResponse

from app.config import get_settings
from app.database import get_db
from app.middleware.auth_middleware import AdminUser
from app.models.dataset_collection import (
    BaselineKind,
    CollectionSession,
    CollectionTrial,
    DatasetParticipant,
    EmotionStimulus,
    Quadrant,
    ReviewState,
    TrialState,
)
from app.schemas.dataset_collection import (
    ArtifactRequest,
    CollectionRunnerStateResponse,
    CollectionSessionCreate,
    CollectionSessionListResponse,
    CollectionSessionResponse,
    DeviceSelectionRequest,
    InterruptRequest,
    ParticipantCreate,
    ParticipantListResponse,
    ParticipantResponse,
    RatingRequest,
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
from app.services.auth_service import decode_token, get_user_by_id
from app.services.collection_state_machine import CollectionStateError
from app.services.trial_scheduler import ScheduleUnavailableError, create_trial_schedule
from app.ws.collection_manager import collection_manager

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


def _collection_session(db: Session, session_id: int) -> CollectionSession:
    collection_session = db.get(CollectionSession, session_id)
    if collection_session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collection session not found")
    return collection_session


def _run_session(db: Session, session_id: int, operation):
    collection_session = _collection_session(db, session_id)
    return collection_manager.run(db, collection_session, operation)


def _safe_transition(call):
    try:
        return call()
    except CollectionStateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


async def _publish_response(
    db: Session,
    session_id: int,
    state,
) -> CollectionRunnerStateResponse:
    response = _state_response(db, state)
    await collection_manager.publish(session_id, response)
    return response


def _runner_trial(runner, session_id: int, trial_id: int) -> CollectionTrial:
    trial = runner.db.get(CollectionTrial, trial_id)
    if trial is None or trial.session_id != session_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trial not found for session")
    return trial


def _state_response(db: Session, state) -> CollectionRunnerStateResponse:
    response = CollectionRunnerStateResponse.model_validate(state)
    if state.current_trial_id is not None:
        row = db.execute(
            select(CollectionTrial.stimulus_id, EmotionStimulus.title)
            .join(EmotionStimulus, EmotionStimulus.id == CollectionTrial.stimulus_id)
            .where(CollectionTrial.id == state.current_trial_id)
        ).first()
        if row is None:
            return response
        return response.model_copy(update={
            "current_stimulus_id": row.stimulus_id,
            "current_stimulus_title": row.title,
        })
    if state.next_trial_order is None:
        return response
    row = db.execute(
        select(CollectionTrial.id, CollectionTrial.stimulus_id, EmotionStimulus.title)
        .join(EmotionStimulus, EmotionStimulus.id == CollectionTrial.stimulus_id)
        .where(
            CollectionTrial.session_id == state.session_id,
            CollectionTrial.randomized_order == state.next_trial_order,
            CollectionTrial.state == TrialState.scheduled,
        )
    ).first()
    if row is None:
        return response
    return response.model_copy(update={
        "next_trial_id": row.id,
        "next_stimulus_id": row.stimulus_id,
        "next_stimulus_title": row.title,
    })


@router.post("/sessions/{session_id}/schedule", response_model=CollectionRunnerStateResponse)
async def schedule_trials(session_id: int, admin: AdminUser, db: Session = Depends(get_db)):
    def operation(runner):
        try:
            create_trial_schedule(runner.db, runner.session)
        except ScheduleUnavailableError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
        return runner.state()

    state = _run_session(db, session_id, operation)
    return await _publish_response(db, session_id, state)


@router.post("/sessions/{session_id}/device", response_model=CollectionRunnerStateResponse)
async def select_collection_device(
    session_id: int,
    body: DeviceSelectionRequest,
    admin: AdminUser,
    db: Session = Depends(get_db),
):
    state = _safe_transition(
        lambda: _run_session(
            db,
            session_id,
            lambda runner: runner.select_device(body.device_id, body.device_name),
        )
    )
    response = await _publish_response(db, session_id, state)
    await collection_manager.ensure_source(session_id)
    return response


@router.post("/sessions/{session_id}/baseline/{kind}/start", response_model=CollectionRunnerStateResponse)
async def start_collection_baseline(
    session_id: int,
    kind: BaselineKind,
    admin: AdminUser,
    db: Session = Depends(get_db),
):
    state = _safe_transition(
        lambda: _run_session(db, session_id, lambda runner: runner.start_baseline(kind))
    )
    return await _publish_response(db, session_id, state)


@router.post("/sessions/{session_id}/trials/{trial_id}/rest/start", response_model=CollectionRunnerStateResponse)
async def start_trial_rest(
    session_id: int,
    trial_id: int,
    admin: AdminUser,
    db: Session = Depends(get_db),
):
    def operation(runner):
        trial = _runner_trial(runner, session_id, trial_id)
        before = runner.state()
        if trial.state is not TrialState.scheduled or trial.randomized_order != before.next_trial_order:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Trial is not next in schedule")
        state = runner.start_trial_rest()
        if state.current_trial_id != trial.id:
            runner.interrupt("Scheduled Trial mismatch")
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Trial is not next in schedule")
        return state

    state = _safe_transition(lambda: _run_session(db, session_id, operation))
    return await _publish_response(db, session_id, state)


@router.post("/sessions/{session_id}/trials/{trial_id}/stimulus/start", response_model=CollectionRunnerStateResponse)
async def start_trial_stimulus(
    session_id: int,
    trial_id: int,
    admin: AdminUser,
    db: Session = Depends(get_db),
):
    def operation(runner):
        _runner_trial(runner, session_id, trial_id)
        return runner.start_stimulus(trial_id)

    state = _safe_transition(lambda: _run_session(db, session_id, operation))
    return await _publish_response(db, session_id, state)


@router.post("/sessions/{session_id}/trials/{trial_id}/artifacts", response_model=CollectionRunnerStateResponse)
async def mark_trial_artifact(
    session_id: int,
    trial_id: int,
    body: ArtifactRequest,
    admin: AdminUser,
    db: Session = Depends(get_db),
):
    def operation(runner):
        _runner_trial(runner, session_id, trial_id)
        return runner.mark_artifact(
            trial_id,
            body.event_type,
            start_seconds=runner.state().wall_clock_seconds,
            duration_seconds=0.0,
            details={"note": body.note} if body.note is not None else None,
        )

    state = _safe_transition(lambda: _run_session(db, session_id, operation))
    return await _publish_response(db, session_id, state)


@router.post("/sessions/{session_id}/trials/{trial_id}/stimulus/finish", response_model=CollectionRunnerStateResponse)
async def finish_trial_stimulus(
    session_id: int,
    trial_id: int,
    admin: AdminUser,
    db: Session = Depends(get_db),
):
    def operation(runner):
        _runner_trial(runner, session_id, trial_id)
        return runner.finish_stimulus(trial_id)

    state = _safe_transition(lambda: _run_session(db, session_id, operation))
    return await _publish_response(db, session_id, state)


@router.post("/sessions/{session_id}/trials/{trial_id}/rating", response_model=CollectionRunnerStateResponse)
async def submit_trial_rating(
    session_id: int,
    trial_id: int,
    body: RatingRequest,
    admin: AdminUser,
    db: Session = Depends(get_db),
):
    def operation(runner):
        _runner_trial(runner, session_id, trial_id)
        return runner.submit_rating(
            trial_id,
            valence=body.valence,
            arousal=body.arousal,
            confidence=body.confidence,
        )

    state = _safe_transition(lambda: _run_session(db, session_id, operation))
    return await _publish_response(db, session_id, state)


@router.post("/sessions/{session_id}/interrupt", response_model=CollectionRunnerStateResponse)
async def interrupt_collection(
    session_id: int,
    body: InterruptRequest,
    admin: AdminUser,
    db: Session = Depends(get_db),
):
    state = _safe_transition(
        lambda: _run_session(db, session_id, lambda runner: runner.interrupt(body.reason))
    )
    return await _publish_response(db, session_id, state)


@router.post("/sessions/{session_id}/resume", response_model=CollectionRunnerStateResponse)
async def resume_collection(session_id: int, admin: AdminUser, db: Session = Depends(get_db)):
    state = _safe_transition(lambda: _run_session(db, session_id, lambda runner: runner.resume()))
    response = await _publish_response(db, session_id, state)
    await collection_manager.ensure_source(session_id)
    return response


@router.get("/sessions/{session_id}/runner-state", response_model=CollectionRunnerStateResponse)
async def runner_state(session_id: int, admin: AdminUser, db: Session = Depends(get_db)):
    state = _run_session(db, session_id, lambda runner: runner.state())
    return _state_response(db, state)


@router.get("/stimuli/{stimulus_id}/media")
def stimulus_media(stimulus_id: int, admin: AdminUser, db: Session = Depends(get_db)):
    stimulus = db.get(EmotionStimulus, stimulus_id)
    if stimulus is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stimulus media not found")
    root = Path(get_settings().collection_stimulus_dir).resolve()
    relative = Path(stimulus.file_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stimulus media not found")
    media_path = (root / relative).resolve(strict=False)
    if not media_path.is_relative_to(root) or not media_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stimulus media not found")
    digest = hashlib.sha256()
    with media_path.open("rb") as media_file:
        for chunk in iter(lambda: media_file.read(1024 * 1024), b""):
            digest.update(chunk)
    if not stimulus.checksum or not digest.hexdigest().lower() == stimulus.checksum.lower():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Stimulus media verification failed")
    media_type = mimetypes.guess_type(media_path.name)[0]
    if media_type is None or not media_type.startswith("video/"):
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Stimulus media is not a video")
    return FileResponse(media_path, media_type=media_type, filename=media_path.name)


@router.websocket("/ws/{session_id}")
async def collection_websocket(
    session_id: int,
    websocket: WebSocket,
    token: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    if token is None:
        await websocket.close(code=4401)
        return
    payload = decode_token(token)
    if payload is None or payload.get("type") != "access" or not payload.get("sub"):
        await websocket.close(code=4401)
        return
    try:
        user = get_user_by_id(db, int(payload["sub"]))
    except (TypeError, ValueError):
        user = None
    if user is None or not user.is_active:
        await websocket.close(code=4401)
        return
    if user.role is None or user.role.name != "admin":
        await websocket.close(code=4403)
        return
    if db.get(CollectionSession, session_id) is None:
        await websocket.close(code=4404)
        return
    await websocket.accept()
    try:
        await collection_manager.connect(session_id, websocket, db)
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await collection_manager.disconnect(session_id, websocket)
