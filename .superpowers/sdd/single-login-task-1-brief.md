# Task 1: FastAPI User/Admin HTTP Boundary

Implement Task 1 from the approved single-login plan using strict TDD.

## Files

- Create `backend/tests/test_role_dependencies.py`
- Modify `backend/app/middleware/auth_middleware.py`
- Modify `backend/app/routers/persona.py`
- Modify `backend/app/routers/eeg_session.py`
- Modify `backend/app/routers/comic.py`

## Requirements

- Add `require_user(current_user: User = Depends(get_current_user)) -> User`.
- It returns accounts whose role name is exactly `user`.
- It raises HTTP 403 with detail `User access required` for `admin`, missing roles, and unsupported roles.
- Add `StandardUser = Annotated[User, Depends(require_user)]`.
- Preserve `require_admin`, `CurrentUser`, `AdminUser`, endpoint paths, bodies, filters, and response models.
- Replace `CurrentUser` with `StandardUser` for Persona CRUD and User Comic/Rating HTTP endpoints.
- In `eeg_session.py`, apply `StandardUser` only to normal HTTP endpoints.
- Keep this WebSocket declaration exactly unchanged:
  `async def eeg_websocket(session_id: str, websocket: WebSocket):`
- Do not change database schema, role seeds, JWT payloads, or unrelated files.
- Stage only the five files listed above and commit with message `feat: enforce user-only API boundaries`.

## Required tests (write and run before production code)

Create direct tests using `SimpleNamespace`:

- `require_user` returns the same User-role object.
- `require_user` rejects role names `admin`, `None`, and `editor` with status 403 and exact detail.
- `require_admin` accepts Admin and rejects User with 403.

Run from `backend`:

`python -m pytest tests/test_role_dependencies.py -q`

First capture the expected RED import failure because `require_user` does not exist. After implementation, rerun to GREEN. Also run source checks for `current_user: StandardUser` across the three routers and confirm the WebSocket signature remains present.

## Report

Write `.superpowers/sdd/single-login-task-1-report.md` with files changed, RED evidence, GREEN evidence, source-check results, commit hash, self-review, and concerns. Return only status (`DONE`, `DONE_WITH_CONCERNS`, `NEEDS_CONTEXT`, or `BLOCKED`), commit hash, one-line test summary, and concerns.
