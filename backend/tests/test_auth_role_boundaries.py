from types import SimpleNamespace

from app.routers import auth
from app.schemas.auth import LoginRequest


def _user_without_role():
    return SimpleNamespace(
        id=7,
        username="orphan",
        email="orphan@example.com",
        role=None,
        is_active=True,
    )


def test_login_preserves_missing_role_as_invalid(monkeypatch):
    user = _user_without_role()
    monkeypatch.setattr(auth, "authenticate_user", lambda *_: user)
    monkeypatch.setattr(auth, "create_access_token", lambda _id, role: f"access:{role}")
    monkeypatch.setattr(auth, "create_refresh_token", lambda _id: "refresh")

    response = auth.login(LoginRequest(email=user.email, password="secret"), object())

    assert response.role == ""
    assert response.access_token == "access:"


def test_refresh_preserves_missing_role_as_invalid(monkeypatch):
    user = _user_without_role()
    monkeypatch.setattr(auth, "decode_token", lambda _token: {"type": "refresh", "sub": "7"})
    monkeypatch.setattr(auth, "get_user_by_id", lambda *_: user)
    monkeypatch.setattr(auth, "create_access_token", lambda _id, role: f"access:{role}")
    monkeypatch.setattr(auth, "create_refresh_token", lambda _id: "refresh")

    response = auth.refresh("refresh", object())

    assert response.role == ""
    assert response.access_token == "access:"


def test_me_preserves_missing_role_as_invalid():
    response = auth.me(_user_without_role())

    assert response.role == ""
