from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.middleware.auth_middleware import require_admin, require_user


def _account(role_name):
    role = None if role_name is None else SimpleNamespace(name=role_name)
    return SimpleNamespace(role=role)


def test_require_user_returns_same_user_role_account():
    account = _account("user")

    assert require_user(account) is account


@pytest.mark.parametrize("role_name", ["admin", None, "editor"])
def test_require_user_rejects_non_user_roles(role_name):
    with pytest.raises(HTTPException) as exc_info:
        require_user(_account(role_name))

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "User access required"


def test_require_admin_accepts_admin_role():
    account = _account("admin")

    assert require_admin(account) is account


def test_require_admin_rejects_user_role():
    with pytest.raises(HTTPException) as exc_info:
        require_admin(_account("user"))

    assert exc_info.value.status_code == 403
