from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth_middleware import StandardUser
from app.models.eeg import EEGSession, EEGFeature, EmotionResult, SessionStatus
from app.schemas.eeg import EEGSessionOut, EmotionResultOut
from app.services.eeg_service import EEGStateMachine, Phase, SessionState
from app.ws import eeg_manager

router = APIRouter(prefix="/sessions", tags=["eeg-sessions"])

# In-memory store for active state machines (session_id → EEGStateMachine)
_active_machines: dict[str, EEGStateMachine] = {}


@router.post("/", response_model=EEGSessionOut, status_code=201)
def create_session(current_user: StandardUser, db: Session = Depends(get_db)):
    """Create a new EEG session record and initialize state machine."""
    db_session = EEGSession(user_id=current_user.id, status=SessionStatus.baseline)
    db.add(db_session)
    db.commit()
    db.refresh(db_session)

    session_id = str(db_session.id)
    state = SessionState(session_id=session_id, user_id=current_user.id)
    _active_machines[session_id] = EEGStateMachine(state)

    return db_session


@router.get("/{session_id}", response_model=EEGSessionOut)
def get_session(session_id: int, current_user: StandardUser, db: Session = Depends(get_db)):
    s = db.query(EEGSession).filter(
        EEGSession.id == session_id, EEGSession.user_id == current_user.id
    ).first()
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    return s


@router.post("/{session_id}/confirm-device")
def confirm_device(
    session_id: str,
    device_name: str,
    device_id: str,
    current_user: StandardUser,
):
    """User confirms device selection (AC-EEG-01)."""
    machine = _active_machines.get(session_id)
    if not machine:
        raise HTTPException(status_code=404, detail="Active session not found")
    machine.confirm_device(device_name, device_id)
    return {"status": "ok", "phase": machine.state.phase.value}


@router.post("/{session_id}/start-baseline")
def start_baseline(session_id: str, current_user: StandardUser):
    machine = _active_machines.get(session_id)
    if not machine:
        raise HTTPException(status_code=404, detail="Active session not found")
    machine.start_baseline()
    return {"status": "ok", "phase": machine.state.phase.value}


@router.post("/{session_id}/start-recording")
def start_recording(session_id: str, current_user: StandardUser):
    machine = _active_machines.get(session_id)
    if not machine:
        raise HTTPException(status_code=404, detail="Active session not found")
    if machine.state.phase != Phase.READY:
        raise HTTPException(status_code=400, detail="Not in READY state")
    machine.start_recording()
    return {"status": "ok", "phase": machine.state.phase.value}


@router.post("/{session_id}/confirm-emotion")
def confirm_emotion(session_id: str, current_user: StandardUser, db: Session = Depends(get_db)):
    """User confirms emotion result and saves to DB."""
    machine = _active_machines.get(session_id)
    if not machine:
        raise HTTPException(status_code=404, detail="Active session not found")
    if machine.state.phase != Phase.EMOTION_CONFIRMATION:
        raise HTTPException(status_code=400, detail="Not in EMOTION_CONFIRMATION state")

    state = machine.state
    machine.confirm_emotion()

    # Persist results
    db_session = db.query(EEGSession).filter(EEGSession.id == int(session_id)).first()
    if db_session:
        db_session.status = SessionStatus.completed
        db_session.completed_at = datetime.now(timezone.utc)
        db_session.wall_clock_duration = state.wall_clock_seconds
        db_session.pause_count = state.pause_count
        db_session.rejected_epoch_count = state.rejected_epoch_count
        if state.device_name:
            db_session.device_name = state.device_name
        db.commit()

    if state.recording_features and state.emotion:
        rf = state.recording_features
        ec = state.emotion
        bl = state.baseline_features

        feature = EEGFeature(
            session_id=int(session_id),
            baseline_faa=bl.faa if bl else None,
            baseline_arousal=bl.arousal if bl else None,
            baseline_log_alpha_af7=bl.log_alpha_af7 if bl else None,
            baseline_log_alpha_af8=bl.log_alpha_af8 if bl else None,
            baseline_log_beta_af7=bl.log_beta_af7 if bl else None,
            baseline_log_beta_af8=bl.log_beta_af8 if bl else None,
            recording_faa=rf.faa,
            recording_arousal=rf.arousal,
            delta_faa=rf.delta_faa,
            delta_arousal=rf.delta_arousal,
        )
        db.add(feature)

        emotion_result = EmotionResult(
            session_id=int(session_id),
            final_emotion=ec.emotion,
            rule_version=ec.rule_version,
            threshold_version=ec.threshold_version,
            valence=ec.valence,
            arousal=ec.arousal_value,
            delta_faa=ec.delta_faa,
            delta_arousal=ec.delta_arousal,
            quality_score_avg=rf.quality_score_avg,
            accepted_epochs=rf.accepted_epochs,
            rejected_epochs=rf.rejected_epochs,
        )
        db.add(emotion_result)
        db.commit()

        return EmotionResultOut.model_validate(emotion_result)

    return {"status": "ok"}


@router.post("/{session_id}/cancel")
def cancel_session(session_id: str, current_user: StandardUser, db: Session = Depends(get_db)):
    machine = _active_machines.get(session_id)
    if machine:
        machine.cancel()
    db_session = db.query(EEGSession).filter(EEGSession.id == int(session_id)).first()
    if db_session:
        db_session.status = SessionStatus.cancelled
        db.commit()
    _active_machines.pop(session_id, None)
    return {"status": "cancelled"}


# ─── WebSocket endpoint ────────────────────────────────────────────────────────

@router.websocket("/ws/{session_id}")
async def eeg_websocket(session_id: str, websocket: WebSocket):
    """
    Real-time WebSocket for EEG state updates.
    Frontend connects here to receive live sensor/phase/progress data.
    """
    await eeg_manager.connect(session_id, websocket)
    try:
        machine = _active_machines.get(session_id)
        if machine is None:
            await eeg_manager.send_to(websocket, {"error": "Session not found"})
            await websocket.close()
            return

        # Send immediate status
        await eeg_manager.send_to(websocket, machine.to_ws_dict())

        while True:
            # Receive commands from client (e.g., confirm device, start recording)
            try:
                data = await websocket.receive_json()
                cmd = data.get("cmd", "")
                if cmd == "confirm_device":
                    machine.confirm_device(data["device_name"], data["device_id"])
                elif cmd == "start_fitting":
                    machine.start_fitting()
                elif cmd == "start_baseline":
                    machine.start_baseline()
                elif cmd == "start_recording":
                    machine.start_recording()
                elif cmd == "cancel":
                    machine.cancel()
                # Broadcast updated state
                await eeg_manager.broadcast(session_id, machine.to_ws_dict())
            except Exception:
                break

    except WebSocketDisconnect:
        pass
    finally:
        eeg_manager.disconnect(session_id, websocket)
