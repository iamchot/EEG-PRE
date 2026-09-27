import asyncio
import hashlib
import logging
import mimetypes
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from starlette.responses import FileResponse

from app.config import get_settings
from app.database import get_db
from app.middleware.auth_middleware import AdminUser
from app.models.dataset_collection import (
    BaselineKind,
    CollectionSession,
    CollectionSessionState,
    CollectionTrial,
    DatasetParticipant,
    EmotionStimulus,
    Quadrant,
    ReviewState,
    TrialState,
)
from app.schemas.dataset_collection import (
    ArtifactRequest,
    CollectionOverviewResponse,
    CollectionRunnerStateResponse,
    CollectionSessionCreate,
    CollectionSessionListResponse,
    CollectionSessionResponse,
    DeviceSelectionRequest,
    InterruptRequest,
    ParticipantCreate,
    ParticipantListResponse,
    ParticipantResponse,
    QuadrantCounts,
    QuadrantStat,
    RatingRequest,
    ReviewCounts,
    SessionTrialItemResponse,
    SessionTrialsDetailResponse,
    StimulusCreate,
    StimulusListResponse,
    StimulusResponse,
    TrialRatingPoint,
)
from app.schemas.muse import MuseBridgeState, MuseConnectionStatus, MuseOwner
from app.services.dataset_collection_service import (
    DatasetConflictError,
    ParticipantUnavailableError,
    create_collection_session,
    create_participant,
    create_stimulus,
)
from app.services.auth_service import decode_token, get_user_by_id
from app.services.collection_state_machine import CollectionStateError
from app.services.collection_state_response import collection_state_response
from app.services.trial_scheduler import ScheduleUnavailableError, create_trial_schedule
from app.services.muse_ble import MuseBleDevice
from app.services.muse_bridge_manager import managed_muse_bridge_manager
from app.ws.collection_manager import CollectionContextUnavailableError, collection_manager

router = APIRouter(prefix="/admin/dataset-collection", tags=["Admin Dataset Collection"])
log = logging.getLogger(__name__)


class MuseConnectRequest(BaseModel):
    address: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=100)


@router.get("/overview", response_model=CollectionOverviewResponse)
def collection_overview(admin: AdminUser, db: Session = Depends(get_db)):
    total_participants = db.scalar(select(func.count(DatasetParticipant.id))) or 0
    total_sessions = db.scalar(select(func.count(CollectionSession.id))) or 0
    total_trials = db.scalar(select(func.count(CollectionTrial.id))) or 0

    completed_trials = db.scalar(
        select(func.count(CollectionTrial.id)).where(CollectionTrial.state == TrialState.completed)
    ) or 0

    scheduled_trials = db.scalar(
        select(func.count(CollectionTrial.id)).where(CollectionTrial.state == TrialState.scheduled)
    ) or 0

    total_eeg_bytes = db.scalar(
        select(func.sum(CollectionTrial.raw_size_bytes)).where(CollectionTrial.state == TrialState.completed)
    ) or 0

    # Only count completed trials in review counts (cannot review trials that have not occurred)
    review_rows = db.execute(
        select(CollectionTrial.review_state, func.count(CollectionTrial.id))
        .where(CollectionTrial.state == TrialState.completed)
        .group_by(CollectionTrial.review_state)
    ).all()
    review_counts_map = {state.value: count for state, count in review_rows}
    review_counts = {state.value: review_counts_map.get(state.value, 0) for state in ReviewState}

    quadrant_rows = db.execute(
        select(EmotionStimulus.target_quadrant, func.count(EmotionStimulus.id)).group_by(
            EmotionStimulus.target_quadrant
        )
    ).all()
    quadrant_counts_map = {quadrant.value: count for quadrant, count in quadrant_rows}
    quadrant_counts = {quadrant.value: quadrant_counts_map.get(quadrant.value, 0) for quadrant in Quadrant}

    sess_rows = db.execute(
        select(CollectionSession.state, func.count(CollectionSession.id)).group_by(CollectionSession.state)
    ).all()
    sessions_by_state = {s.value: c for s, c in sess_rows}

    rated_trials = db.execute(
        select(
            CollectionTrial.id,
            CollectionTrial.session_id,
            DatasetParticipant.participant_code,
            EmotionStimulus.title,
            EmotionStimulus.target_quadrant,
            CollectionTrial.valence_rating,
            CollectionTrial.arousal_rating,
            CollectionTrial.confidence,
            CollectionTrial.eeg_file_path,
            CollectionTrial.raw_size_bytes,
        )
        .join(CollectionSession, CollectionTrial.session_id == CollectionSession.id)
        .join(DatasetParticipant, CollectionSession.participant_id == DatasetParticipant.id)
        .join(EmotionStimulus, CollectionTrial.stimulus_id == EmotionStimulus.id)
        .where(
            CollectionTrial.state == TrialState.completed,
            CollectionTrial.valence_rating.isnot(None),
            CollectionTrial.arousal_rating.isnot(None),
        )
        .order_by(CollectionTrial.session_id, CollectionTrial.randomized_order)
    ).all()

    ratings_distribution = [
        TrialRatingPoint(
            trial_id=row.id,
            session_id=row.session_id,
            participant_code=row.participant_code,
            stimulus_title=row.title,
            target_quadrant=row.target_quadrant.value,
            valence=row.valence_rating,
            arousal=row.arousal_rating,
            confidence=row.confidence or 3,
            eeg_file_path=row.eeg_file_path,
            raw_size_bytes=row.raw_size_bytes,
        )
        for row in rated_trials
    ]

    quadrant_stats = {}
    for q in Quadrant:
        trials_in_q = [t for t in ratings_distribution if t.target_quadrant == q.value]
        count = len(trials_in_q)
        avg_v = round(sum(t.valence for t in trials_in_q) / count, 2) if count > 0 else None
        avg_a = round(sum(t.arousal for t in trials_in_q) / count, 2) if count > 0 else None
        quadrant_stats[q.value] = QuadrantStat(target_count=count, avg_valence=avg_v, avg_arousal=avg_a)

    return CollectionOverviewResponse(
        participants=total_participants,
        sessions=total_sessions,
        trials=total_trials,
        completed_trials=completed_trials,
        scheduled_trials=scheduled_trials,
        total_eeg_bytes=total_eeg_bytes,
        review_counts=ReviewCounts(**review_counts),
        quadrant_counts=QuadrantCounts(**quadrant_counts),
        sessions_by_state=sessions_by_state,
        ratings_distribution=ratings_distribution,
        quadrant_stats=quadrant_stats,
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


@router.get("/sessions/{session_id}/trials", response_model=SessionTrialsDetailResponse)
def session_trials_detail(session_id: int, admin: AdminUser, db: Session = Depends(get_db)):
    session = db.get(CollectionSession, session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collection session not found")

    participant = db.get(DatasetParticipant, session.participant_id)
    participant_code = participant.participant_code if participant else "Unknown"

    trials = db.execute(
        select(
            CollectionTrial,
            EmotionStimulus.title,
            EmotionStimulus.target_quadrant,
            EmotionStimulus.duration_seconds,
        )
        .join(EmotionStimulus, CollectionTrial.stimulus_id == EmotionStimulus.id)
        .where(CollectionTrial.session_id == session_id)
        .order_by(CollectionTrial.randomized_order)
    ).all()

    items = []
    total_bytes = 0
    valences = []
    arousals = []

    for trial, stim_title, stim_quadrant, stim_duration in trials:
        if trial.raw_size_bytes:
            total_bytes += trial.raw_size_bytes
        if trial.valence_rating is not None:
            valences.append(trial.valence_rating)
        if trial.arousal_rating is not None:
            arousals.append(trial.arousal_rating)

        items.append(
            SessionTrialItemResponse(
                id=trial.id,
                randomized_order=trial.randomized_order,
                stimulus_id=trial.stimulus_id,
                stimulus_title=stim_title,
                target_quadrant=stim_quadrant.value,
                state=trial.state.value if trial.state else "scheduled",
                review_state=trial.review_state.value if trial.review_state else "pending",
                valence_rating=trial.valence_rating,
                arousal_rating=trial.arousal_rating,
                confidence=trial.confidence,
                eeg_file_path=trial.eeg_file_path,
                eeg_checksum=trial.eeg_checksum,
                raw_size_bytes=trial.raw_size_bytes,
                duration_seconds=stim_duration,
                started_at=trial.started_at,
                completed_at=trial.completed_at,
            )
        )

    completed_count = sum(1 for item in items if item.state == "completed")
    avg_v = round(sum(valences) / len(valences), 2) if valences else None
    avg_a = round(sum(arousals) / len(arousals), 2) if arousals else None

    return SessionTrialsDetailResponse(
        session_id=session.id,
        participant_id=session.participant_id,
        participant_code=participant_code,
        device_id=session.device_id,
        device_name=session.device_name,
        state=session.state.value if session.state else "ready",
        completed_trials=completed_count,
        total_trials=len(items),
        total_eeg_bytes=total_bytes,
        avg_valence=avg_v,
        avg_arousal=avg_a,
        items=items,
    )


def _collection_session(db: Session, session_id: int) -> CollectionSession:
    collection_session = db.get(CollectionSession, session_id)
    if collection_session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collection session not found")
    return collection_session


def _bridgeable_collection_session(db: Session, session_id: int) -> CollectionSession:
    collection_session = _collection_session(db, session_id)
    if collection_session.state in {
        CollectionSessionState.completed,
        CollectionSessionState.failed,
        CollectionSessionState.withdrawn,
    }:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Collection session is terminal")
    return collection_session


@router.post("/sessions/{session_id}/muse", response_model=MuseConnectionStatus)
async def connect_collection_muse(
    session_id: int,
    body: MuseConnectRequest,
    admin: AdminUser,
    db: Session = Depends(get_db),
):
    _bridgeable_collection_session(db, session_id)
    return await managed_muse_bridge_manager.connect(
        MuseOwner(kind="collection", session_id=session_id),
        MuseBleDevice(address=body.address, name=body.name),
    )


@router.get("/sessions/{session_id}/muse", response_model=MuseConnectionStatus)
async def collection_muse_status(session_id: int, admin: AdminUser, db: Session = Depends(get_db)):
    _collection_session(db, session_id)
    return await managed_muse_bridge_manager.status(MuseOwner(kind="collection", session_id=session_id))


@router.delete("/sessions/{session_id}/muse", response_model=MuseConnectionStatus)
async def disconnect_collection_muse(session_id: int, admin: AdminUser, db: Session = Depends(get_db)):
    _collection_session(db, session_id)
    await collection_manager.stop_source(session_id)
    return await managed_muse_bridge_manager.status(MuseOwner(kind="collection", session_id=session_id))


def _run_session(db: Session, session_id: int, operation):
    collection_session = _collection_session(db, session_id)
    return collection_manager.run(db, collection_session, operation)


def _run_capture_session(db: Session, session_id: int, operation):
    collection_session = _collection_session(db, session_id)
    try:
        return collection_manager.run_capture(db, collection_session, operation)
    except CollectionContextUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


def _validate_session_trial(db: Session, session_id: int, trial_id: int) -> None:
    trial = db.get(CollectionTrial, trial_id)
    if trial is None or trial.session_id != session_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trial not found for session")


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
    return collection_state_response(db, state)


@router.post("/sessions/{session_id}/schedule", response_model=CollectionRunnerStateResponse)
async def schedule_trials(session_id: int, admin: AdminUser, db: Session = Depends(get_db)):
    def operation(runner):
        try:
            create_trial_schedule(runner.db, runner.session)
        except ScheduleUnavailableError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
        return runner.state()

    try:
        state = _run_session(db, session_id, operation)
        return await _publish_response(db, session_id, state)
    finally:
        collection_manager.release_if_idle(session_id)


@router.post("/sessions/{session_id}/device", response_model=CollectionRunnerStateResponse)
async def select_collection_device(
    session_id: int,
    body: DeviceSelectionRequest,
    admin: AdminUser,
    db: Session = Depends(get_db),
):
    try:
        state = _safe_transition(
            lambda: _run_session(
                db,
                session_id,
                lambda runner: runner.select_device(body.device_id, body.device_name),
            )
        )
        # Discard stale EEG quality history so the new Muse connection starts fresh,
        # but preserve active flag if Web Bluetooth is already streaming.
        collection_manager.clear_web_bt_buffer(session_id, preserve_active_flag=True)
        response = await _publish_response(db, session_id, state)
        asyncio.create_task(collection_manager.ensure_source(session_id))
        return response
    finally:
        collection_manager.release_if_idle(session_id)


@router.post("/sessions/{session_id}/baseline/{kind}/start", response_model=CollectionRunnerStateResponse)
async def start_collection_baseline(
    session_id: int,
    kind: BaselineKind,
    admin: AdminUser,
    db: Session = Depends(get_db),
):
    """Start a baseline recording for the given session.

    Admin confirms physical sensor contact via UI checkboxes, so
    require_live_sensor_ready() is not used here.  Signal quality is
    enforced naturally during accumulation — poor/unknown sensors simply
    will not contribute accepted seconds to the 20-second target.
    """
    def operation(runner):
        return runner.start_baseline(kind)

    state = _safe_transition(lambda: _run_capture_session(db, session_id, operation))
    return await _publish_response(db, session_id, state)


@router.post("/sessions/{session_id}/trials/{trial_id}/rest/start", response_model=CollectionRunnerStateResponse)
async def start_trial_rest(
    session_id: int,
    trial_id: int,
    admin: AdminUser,
    db: Session = Depends(get_db),
):
    _validate_session_trial(db, session_id, trial_id)

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

    state = _safe_transition(lambda: _run_capture_session(db, session_id, operation))
    return await _publish_response(db, session_id, state)


@router.post("/sessions/{session_id}/trials/{trial_id}/stimulus/start", response_model=CollectionRunnerStateResponse)
async def start_trial_stimulus(
    session_id: int,
    trial_id: int,
    admin: AdminUser,
    db: Session = Depends(get_db),
):
    _validate_session_trial(db, session_id, trial_id)

    def operation(runner):
        _runner_trial(runner, session_id, trial_id)
        runner.require_live_sensor_ready()
        return runner.start_stimulus(trial_id)

    state = _safe_transition(lambda: _run_capture_session(db, session_id, operation))
    return await _publish_response(db, session_id, state)


@router.post("/sessions/{session_id}/trials/{trial_id}/artifacts", response_model=CollectionRunnerStateResponse)
async def mark_trial_artifact(
    session_id: int,
    trial_id: int,
    body: ArtifactRequest,
    admin: AdminUser,
    db: Session = Depends(get_db),
):
    _validate_session_trial(db, session_id, trial_id)

    def operation(runner):
        _runner_trial(runner, session_id, trial_id)
        return runner.mark_artifact(
            trial_id,
            body.event_type,
            start_seconds=runner.state().wall_clock_seconds,
            duration_seconds=0.0,
            details={"note": body.note} if body.note is not None else None,
        )

    state = _safe_transition(lambda: _run_capture_session(db, session_id, operation))
    return await _publish_response(db, session_id, state)


@router.post("/sessions/{session_id}/trials/{trial_id}/stimulus/finish", response_model=CollectionRunnerStateResponse)
async def finish_trial_stimulus(
    session_id: int,
    trial_id: int,
    admin: AdminUser,
    db: Session = Depends(get_db),
):
    _validate_session_trial(db, session_id, trial_id)

    def operation(runner):
        _runner_trial(runner, session_id, trial_id)
        return runner.finish_stimulus(trial_id)

    state = _safe_transition(lambda: _run_capture_session(db, session_id, operation))
    return await _publish_response(db, session_id, state)


@router.post("/sessions/{session_id}/trials/{trial_id}/rating", response_model=CollectionRunnerStateResponse)
async def submit_trial_rating(
    session_id: int,
    trial_id: int,
    body: RatingRequest,
    admin: AdminUser,
    db: Session = Depends(get_db),
):
    _validate_session_trial(db, session_id, trial_id)

    def operation(runner):
        _runner_trial(runner, session_id, trial_id)
        return runner.submit_rating(
            trial_id,
            valence=body.valence,
            arousal=body.arousal,
            confidence=body.confidence,
        )

    state = _safe_transition(lambda: _run_capture_session(db, session_id, operation))
    return await _publish_response(db, session_id, state)


@router.post("/sessions/{session_id}/interrupt", response_model=CollectionRunnerStateResponse)
async def interrupt_collection(
    session_id: int,
    body: InterruptRequest,
    admin: AdminUser,
    db: Session = Depends(get_db),
):
    state = _safe_transition(
        lambda: _run_capture_session(db, session_id, lambda runner: runner.interrupt(body.reason))
    )
    return await _publish_response(db, session_id, state)


@router.post("/sessions/{session_id}/resume", response_model=CollectionRunnerStateResponse)
async def resume_collection(session_id: int, admin: AdminUser, db: Session = Depends(get_db)):
    try:
        state = _safe_transition(lambda: _run_session(db, session_id, lambda runner: runner.resume()))
        response = await _publish_response(db, session_id, state)
        asyncio.create_task(collection_manager.ensure_source(session_id))
        return response
    finally:
        collection_manager.release_if_idle(session_id)


@router.get("/sessions/{session_id}/runner-state", response_model=CollectionRunnerStateResponse)
async def runner_state(session_id: int, admin: AdminUser, db: Session = Depends(get_db)):
    try:
        state = _run_session(db, session_id, lambda runner: runner.state())
        return _state_response(db, state)
    finally:
        collection_manager.release_if_idle(session_id)


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
    return FileResponse(media_path, media_type=media_type)


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
        # Release the request's checked-out DB connection back to QueuePool so
        # long-lived WebSocket connections do not starve the pool.
        try:
            db.close()
        except Exception:
            pass
        while True:
            try:
                data = await websocket.receive_json()
            except Exception:
                # receive_json failed (disconnect or parse error) — exit loop
                break
            cmd = data.get("cmd", "") if isinstance(data, dict) else ""
            if cmd == "eeg_sample_admin":
                # EEG sample forwarded from Web Bluetooth (muse-js) — Admin runner path.
                # Routes into CollectionConnectionManager.ingest_web_bluetooth_sample()
                # which feeds the collection state machine directly (no LSL bridge needed).
                try:
                    await collection_manager.ingest_web_bluetooth_sample(
                        session_id,
                        tp9=float(data.get("tp9", 0.0)),
                        af7=float(data.get("af7", 0.0)),
                        af8=float(data.get("af8", 0.0)),
                        tp10=float(data.get("tp10", 0.0)),
                        timestamp=float(data.get("timestamp", 0.0)),
                    )
                except Exception as exc:
                    # Log but don't break — EEG errors are non-fatal for the WS loop
                    log.warning("eeg_sample_admin error for session %s: %s", session_id, exc)
    except WebSocketDisconnect:
        pass
    finally:
        await collection_manager.disconnect(session_id, websocket)
