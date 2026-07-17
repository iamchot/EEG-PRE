from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth_middleware import AdminUser
from app.models.comic import Comic, Rating
from app.models.eeg import EmotionResult
from app.models.user import User

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/stats")
def dashboard_stats(admin: AdminUser, db: Session = Depends(get_db)):
    """PRD 5.6 — Check Statistics: emotion distribution + activity."""
    total_users = db.query(func.count(User.id)).scalar()
    total_comics = db.query(func.count(Comic.id)).scalar()

    emotion_rows = (
        db.query(EmotionResult.final_emotion, func.count(EmotionResult.id))
        .group_by(EmotionResult.final_emotion)
        .all()
    )
    emotion_dist = {row[0].value: row[1] for row in emotion_rows}

    avg_rating_row = db.query(func.avg(Rating.stars)).scalar()
    avg_rating = round(float(avg_rating_row), 2) if avg_rating_row else 0.0

    return {
        "total_users": total_users,
        "total_comics": total_comics,
        "emotion_distribution": emotion_dist,
        "average_rating": avg_rating,
    }


@router.get("/users")
def list_users(admin: AdminUser, db: Session = Depends(get_db), skip: int = 0, limit: int = 50):
    """PRD 5.6 — Manage Users."""
    users = db.query(User).offset(skip).limit(limit).all()
    return [
        {
            "id": u.id,
            "username": u.username,
            "email": u.email,
            "role": u.role.name if u.role else "user",
            "is_active": u.is_active,
            "created_at": u.created_at,
        }
        for u in users
    ]


@router.patch("/users/{user_id}/deactivate")
def deactivate_user(user_id: int, admin: AdminUser, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = False
    db.commit()
    return {"status": "deactivated"}


@router.patch("/users/{user_id}/activate")
def activate_user(user_id: int, admin: AdminUser, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = True
    db.commit()
    return {"status": "activated"}


@router.delete("/users/{user_id}", status_code=204)
def delete_user(user_id: int, admin: AdminUser, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()


@router.get("/eeg-dataset")
def list_eeg_dataset(admin: AdminUser, db: Session = Depends(get_db), skip: int = 0, limit: int = 100):
    """PRD 5.6 — Manage EEG Dataset: list sessions."""
    from app.models.eeg import EEGSession

    sessions = db.query(EEGSession).offset(skip).limit(limit).all()
    return [
        {
            "id": s.id,
            "user_id": s.user_id,
            "device_name": s.device_name,
            "status": s.status.value,
            "wall_clock_duration": s.wall_clock_duration,
            "accepted_recording_duration": s.accepted_recording_duration,
            "raw_data_path": s.raw_data_path,
            "started_at": s.started_at,
            "completed_at": s.completed_at,
        }
        for s in sessions
    ]


@router.delete("/eeg-dataset/{session_id}", status_code=204)
def delete_eeg_session(session_id: int, admin: AdminUser, db: Session = Depends(get_db)):
    from app.models.eeg import EEGSession

    s = db.query(EEGSession).filter(EEGSession.id == session_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    db.delete(s)
    db.commit()
