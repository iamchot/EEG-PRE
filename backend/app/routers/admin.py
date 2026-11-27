from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth_middleware import AdminUser
from app.models.comic import Comic, Rating
from app.models.eeg import EmotionResult
from app.models.user import Role, User
from app.services.auth_service import hash_password

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/stats")
def dashboard_stats(admin: AdminUser, db: Session = Depends(get_db)):
    """PRD 5.6 — Check Statistics: emotion distribution + activity."""
    from datetime import datetime, timedelta, timezone
    from app.models.eeg import EEGSession, SessionStatus

    total_users = db.query(func.count(User.id)).scalar() or 0
    active_users = db.query(func.count(User.id)).filter(User.is_active == True).scalar() or 0
    total_comics = db.query(func.count(Comic.id)).scalar() or 0
    eeg_samples = db.query(func.count(EEGSession.id)).scalar() or 0

    emotion_rows = (
        db.query(EmotionResult.final_emotion, func.count(EmotionResult.id))
        .group_by(EmotionResult.final_emotion)
        .all()
    )
    emotion_dist = {row[0].value: row[1] for row in emotion_rows if row[0] is not None}

    avg_rating_row = db.query(func.avg(Rating.stars)).scalar()
    avg_rating = round(float(avg_rating_row), 2) if avg_rating_row else 0.0
    rating_count = db.query(func.count(Rating.id)).scalar() or 0

    recent_rating_rows = (
        db.query(Rating, Comic, User)
        .join(Comic, Rating.comic_id == Comic.id)
        .outerjoin(User, Rating.user_id == User.id)
        .order_by(Rating.created_at.desc())
        .limit(10)
        .all()
    )
    recent_reviews = []
    for r, c, u in recent_rating_rows:
        er = (
            db.query(EmotionResult)
            .filter(EmotionResult.session_id == c.session_id)
            .first()
            if c.session_id
            else None
        )
        recent_reviews.append(
            {
                "id": r.id,
                "stars": r.stars,
                "feedback": r.feedback,
                "created_at": r.created_at,
                "username": u.username if u else "User",
                "comic_id": c.id,
                "input_story": c.input_story,
                "emotion": er.final_emotion.value if er else None,
            }
        )

    bangkok_tz = timezone(timedelta(hours=7))
    today = datetime.now(bangkok_tz).date()
    daily_activity = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        day_start_utc = datetime.combine(day, datetime.min.time(), tzinfo=bangkok_tz).astimezone(timezone.utc).replace(tzinfo=None)
        day_end_utc = datetime.combine(day, datetime.max.time(), tzinfo=bangkok_tz).astimezone(timezone.utc).replace(tzinfo=None)
        eeg_count = db.query(func.count(EEGSession.id)).filter(
            EEGSession.status == SessionStatus.completed,
            EEGSession.completed_at >= day_start_utc,
            EEGSession.completed_at <= day_end_utc,
        ).scalar() or 0
        comic_count = db.query(func.count(Comic.id)).filter(
            Comic.created_at >= day_start_utc,
            Comic.created_at <= day_end_utc,
        ).scalar() or 0
        daily_activity.append(
            {
                "day": day.strftime("%a"),
                "count": comic_count,
                "eeg_count": eeg_count,
                "comic_count": comic_count,
            }
        )

    return {
        "total_users": total_users,
        "active_users": active_users,
        "total_comics": total_comics,
        "eeg_samples": eeg_samples,
        "emotion_distribution": emotion_dist,
        "average_rating": avg_rating,
        "rating_count": rating_count,
        "recent_reviews": recent_reviews,
        "daily_activity": daily_activity,
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


class AdminCreateUserRequest(BaseModel):
    username: str = Field(min_length=2, max_length=50)
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    role: Literal["user", "admin"] = "user"


@router.post("/users", status_code=201)
def create_user(body: AdminCreateUserRequest, admin: AdminUser, db: Session = Depends(get_db)):
    """Create a new user or admin account from the Admin panel."""
    username = body.username.strip()
    email = body.email.strip().lower()
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(status_code=409, detail="Username already taken")
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=409, detail="Email already registered")

    role_obj = db.query(Role).filter(Role.name == body.role).first()
    if role_obj is None:
        role_obj = Role(name=body.role)
        db.add(role_obj)
        db.flush()

    user = User(
        username=username,
        email=email,
        password_hash=hash_password(body.password),
        role_id=role_obj.id,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": body.role,
        "is_active": user.is_active,
        "created_at": user.created_at,
    }


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
