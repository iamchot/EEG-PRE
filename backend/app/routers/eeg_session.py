from __future__ import annotations

import uuid
from collections import defaultdict, deque
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth_middleware import StandardUser
from app.models.eeg import EEGSession, EEGFeature, EmotionResult, SessionStatus
from app.schemas.eeg import EEGSessionOut, EmotionResultOut
from app.services.eeg_service import EEGStateMachine, Phase, SessionState
from app.services.signal_processor import estimate_sensor_state, SensorQuality
from app.schemas.muse import MuseBridgeState, MuseConnectionStatus, MuseOwner
from app.services.eeg_stream_runner import user_eeg_stream_runner
from app.services.muse_ble import MuseBleDevice
from app.services.muse_bridge_manager import managed_muse_bridge_manager
from app.ws import eeg_manager
import numpy as np
import time

router = APIRouter(prefix="/sessions", tags=["eeg-sessions"])

# In-memory store for active state machines (session_id → EEGStateMachine)
_active_machines: dict[str, EEGStateMachine] = {}

# Rolling EEG sample buffer per WebSocket session (Web Bluetooth path).
# Stores the last 256 samples [tp9, af7, af8, tp10]; used for sensor quality estimation.
_web_bt_buffers: dict[str, deque] = defaultdict(lambda: deque(maxlen=256))
_session_quality_streak: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
_session_quality_display: dict[str, dict[str, str]] = defaultdict(lambda: defaultdict(lambda: "unknown"))

_GOOD_GAIN = 2
_POOR_LOSS = 1
_GOOD_THRESH = 6
_POOR_THRESH = 6


def _apply_session_quality_debounce(
    session_key: str,
    sensors: dict[str, SensorQuality],
) -> dict[str, SensorQuality]:
    streaks = _session_quality_streak[session_key]
    displays = _session_quality_display[session_key]
    stable: dict[str, SensorQuality] = {}
    for ch, sq in sensors.items():
        s = streaks.get(ch, 0)
        if sq.state == "good":
            s = min(s + _GOOD_GAIN, _GOOD_THRESH)
        elif sq.state == "poor":
            s = max(s - _POOR_LOSS, -_POOR_THRESH)
        elif sq.state in ("unknown", "stale"):
            s = max(s - _POOR_LOSS, 0) if s > 0 else min(s + 1, 0)
        streaks[ch] = s

        if s >= _GOOD_THRESH:
            displays[ch] = "good"
        elif s <= -_POOR_THRESH:
            displays[ch] = "poor"

        display_state = displays[ch] if displays[ch] != "unknown" else sq.state
        stable[ch] = SensorQuality(
            state=display_state,
            quality_score=sq.quality_score,
            timestamp=sq.timestamp,
        )
    return stable


class MuseConnectRequest(BaseModel):
    address: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=100)


_pending_muse_devices: dict[str, MuseConnectRequest] = {}


def _owned_session_machine(session_id: int, current_user: StandardUser, db: Session) -> EEGStateMachine:
    db_session = db.query(EEGSession).filter(
        EEGSession.id == session_id, EEGSession.user_id == current_user.id
    ).first()
    if db_session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    key = str(session_id)
    machine = _active_machines.get(key)
    if machine is None:
        machine = EEGStateMachine(SessionState(session_id=key, user_id=current_user.id))
        _active_machines[key] = machine
    return machine


async def _activate_connected_muse(
    session_id: int,
    machine: EEGStateMachine,
    connection: MuseConnectionStatus,
) -> None:
    if connection.state is not MuseBridgeState.connected or machine.state.device_state == "connected":
        return
    selected_device = _pending_muse_devices.get(str(session_id))
    if selected_device is None:
        return
    machine.confirm_device(selected_device.name, selected_device.address)
    machine.mark_connected()
    await user_eeg_stream_runner.start(session_id, machine, connection)


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
    session_id: int,
    device_name: str,
    device_id: str,
    current_user: StandardUser,
    db: Session = Depends(get_db),
):
    """User confirms device selection (AC-EEG-01)."""
    machine = _owned_session_machine(session_id, current_user, db)
    machine.confirm_device(device_name, device_id)
    return {"status": "ok", "phase": machine.state.phase.value}


@router.post("/{session_id}/start-baseline")
def start_baseline(
    session_id: int,
    current_user: StandardUser,
    db: Session = Depends(get_db),
    subphase: str = "eyes_open",
):
    machine = _owned_session_machine(session_id, current_user, db)
    machine.start_baseline(subphase=subphase)
    return {"status": "ok", "phase": machine.state.phase.value, "subphase": machine.state.baseline_subphase}


@router.post("/{session_id}/start-recording")
def start_recording(session_id: int, current_user: StandardUser, db: Session = Depends(get_db)):
    machine = _owned_session_machine(session_id, current_user, db)
    if machine.state.phase != Phase.READY:
        raise HTTPException(status_code=400, detail="Not in READY state")
    machine.start_recording()
    return {"status": "ok", "phase": machine.state.phase.value}


@router.post("/{session_id}/confirm-emotion")
async def confirm_emotion(session_id: str, current_user: StandardUser, db: Session = Depends(get_db)):
    """User confirms emotion result and saves to DB."""
    db_session = db.query(EEGSession).filter(
        EEGSession.id == int(session_id), EEGSession.user_id == current_user.id
    ).first()
    if db_session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    machine = _active_machines.get(session_id)
    if not machine:
        raise HTTPException(status_code=404, detail="Active session not found")
    if machine.state.phase != Phase.EMOTION_CONFIRMATION:
        raise HTTPException(status_code=400, detail="Not in EMOTION_CONFIRMATION state")

    state = machine.state
    machine.confirm_emotion()
    await user_eeg_stream_runner.stop(int(session_id))
    await managed_muse_bridge_manager.release(MuseOwner(kind="user", session_id=int(session_id)))
    _pending_muse_devices.pop(session_id, None)

    # Persist results
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
async def cancel_session(session_id: str, current_user: StandardUser, db: Session = Depends(get_db)):
    machine = _owned_session_machine(int(session_id), current_user, db)
    machine.cancel()
    db_session = db.query(EEGSession).filter(
        EEGSession.id == int(session_id), EEGSession.user_id == current_user.id
    ).first()
    db_session.status = SessionStatus.cancelled
    db.commit()
    await user_eeg_stream_runner.stop(int(session_id))
    await managed_muse_bridge_manager.release(MuseOwner(kind="user", session_id=int(session_id)))
    _active_machines.pop(session_id, None)
    _pending_muse_devices.pop(session_id, None)
    return {"status": "cancelled"}


@router.post("/{session_id}/muse", response_model=MuseConnectionStatus)
async def connect_muse(
    session_id: int,
    body: MuseConnectRequest,
    current_user: StandardUser,
    db: Session = Depends(get_db),
):
    machine = _owned_session_machine(session_id, current_user, db)
    owner = MuseOwner(kind="user", session_id=session_id)
    _pending_muse_devices[str(session_id)] = body
    connection = await managed_muse_bridge_manager.connect(owner, MuseBleDevice(address=body.address, name=body.name))
    await _activate_connected_muse(session_id, machine, connection)
    return connection


@router.get("/{session_id}/muse", response_model=MuseConnectionStatus)
async def muse_status(session_id: int, current_user: StandardUser, db: Session = Depends(get_db)):
    machine = _owned_session_machine(session_id, current_user, db)
    connection = await managed_muse_bridge_manager.status(MuseOwner(kind="user", session_id=session_id))
    await _activate_connected_muse(session_id, machine, connection)
    return connection


@router.delete("/{session_id}/muse", response_model=MuseConnectionStatus)
async def disconnect_muse(session_id: int, current_user: StandardUser, db: Session = Depends(get_db)):
    machine = _owned_session_machine(session_id, current_user, db)
    await user_eeg_stream_runner.stop(session_id)
    machine.state.device_state = "disconnected"
    machine.transition_to(Phase.DISCONNECTED)
    await eeg_manager.broadcast(str(session_id), machine.to_ws_dict())
    _pending_muse_devices.pop(str(session_id), None)
    return await managed_muse_bridge_manager.release(MuseOwner(kind="user", session_id=session_id))


# ─── WebSocket endpoint ────────────────────────────────────────────────────────

@router.websocket("/ws/{session_id}")
async def eeg_websocket(
    session_id: int,
    websocket: WebSocket,
    token: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """
    Real-time WebSocket for EEG state updates.
    Frontend connects here to receive live sensor/phase/progress data.
    Requires token parameter and verifies database session ownership.
    """
    from app.services.auth_service import decode_token, get_user_by_id

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
        await websocket.close(code=4401 if user is None else 4403)
        return

    db_session = db.query(EEGSession).filter(EEGSession.id == session_id).first()
    if db_session is None:
        await websocket.close(code=4404)
        return

    if db_session.user_id != user.id:
        await websocket.close(code=4403)
        return

    key = str(session_id)
    machine = _active_machines.get(key)
    if machine is None:
        machine = EEGStateMachine(SessionState(session_id=key, user_id=user.id))
        _active_machines[key] = machine

    await eeg_manager.connect(key, websocket)
    # Release the request's checked-out DB connection back to QueuePool so
    # long-lived WebSocket connections do not starve the pool.
    try:
        db.close()
    except Exception:
        pass
    try:
        # Send immediate status
        await eeg_manager.send_to(websocket, machine.to_ws_dict())
        last_broadcast_time = time.monotonic()

        while True:
            try:
                data = await websocket.receive_json()
            except Exception:
                break

            cmd = data.get("cmd", "") if isinstance(data, dict) else ""
            if not cmd:
                continue

            try:
                phase_before = machine.state.phase
                if cmd == "confirm_device":
                    machine.confirm_device(data.get("device_name", ""), data.get("device_id", ""))
                    machine.mark_connected()
                    await eeg_manager.broadcast(key, machine.to_ws_dict())
                elif cmd == "eeg_sample":
                    tp9 = float(data.get("tp9", 0.0))
                    af7 = float(data.get("af7", 0.0))
                    af8 = float(data.get("af8", 0.0))
                    tp10 = float(data.get("tp10", 0.0))
                    ts = float(data.get("timestamp", 0.0))
                    _web_bt_buffers[key].append([tp9, af7, af8, tp10])
                    buf_matrix = np.array(_web_bt_buffers[key], dtype=float)
                    now_mono = time.monotonic()
                    raw_sensor_qualities = {
                        ch: estimate_sensor_state(buf_matrix, idx, now_mono, now_mono)
                        for idx, ch in enumerate(("tp9", "af7", "af8", "tp10"))
                    }
                    debounced_qualities = _apply_session_quality_debounce(key, raw_sensor_qualities)
                    machine.ingest_samples(
                        np.array([[tp9, af7, af8, tp10]], dtype=float),
                        np.array([ts], dtype=float),
                        sensor_qualities=debounced_qualities,
                    )
                    # Broadcast immediately on phase change, or throttle to ~4 Hz
                    if machine.state.phase != phase_before or (now_mono - last_broadcast_time) >= 0.25:
                        last_broadcast_time = now_mono
                        await eeg_manager.broadcast(key, machine.to_ws_dict())
                elif cmd == "start_fitting":
                    machine.start_fitting()
                    await eeg_manager.broadcast(key, machine.to_ws_dict())
                elif cmd == "start_baseline":
                    subphase = data.get("subphase", "eyes_open") if isinstance(data, dict) else "eyes_open"
                    machine.start_baseline(subphase=subphase)
                    await eeg_manager.broadcast(key, machine.to_ws_dict())
                elif cmd == "start_recording":
                    machine.start_recording()
                    await eeg_manager.broadcast(key, machine.to_ws_dict())
                elif cmd == "cancel":
                    machine.cancel()
                    await eeg_manager.broadcast(key, machine.to_ws_dict())
            except Exception:
                pass

    finally:
        eeg_manager.disconnect(key, websocket)
        if not eeg_manager.has_clients(key):
            _session_quality_streak.pop(key, None)
            _session_quality_display.pop(key, None)
            _web_bt_buffers.pop(key, None)
            if machine and machine.state.phase not in {Phase.BASELINE, Phase.RECORDING}:
                await user_eeg_stream_runner.stop(session_id)
                await managed_muse_bridge_manager.release(MuseOwner(kind="user", session_id=session_id))

