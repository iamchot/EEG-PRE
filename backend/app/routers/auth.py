from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth_middleware import CurrentUser
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserPublic
from app.services.auth_service import (
    authenticate_user,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_user_by_email,
    get_user_by_id,
    register_user,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _role_name(user) -> str:
    return user.role.name if user.role else ""


@router.post("/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    if get_user_by_email(db, body.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    user = register_user(db, body.username, body.email, body.password)
    return UserPublic(id=user.id, username=user.username, email=user.email, role=user.role.name)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = authenticate_user(db, body.email, body.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    role_name = _role_name(user)
    return TokenResponse(
        access_token=create_access_token(user.id, role_name),
        refresh_token=create_refresh_token(user.id),
        role=role_name,
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh(refresh_token: str, db: Session = Depends(get_db)):
    payload = decode_token(refresh_token)
    if payload is None or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    user = get_user_by_id(db, int(payload["sub"]))
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found")
    role_name = _role_name(user)
    return TokenResponse(
        access_token=create_access_token(user.id, role_name),
        refresh_token=create_refresh_token(user.id),
        role=role_name,
    )


@router.get("/me", response_model=UserPublic)
def me(current_user: CurrentUser):
    role_name = _role_name(current_user)
    return UserPublic(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        role=role_name,
    )
