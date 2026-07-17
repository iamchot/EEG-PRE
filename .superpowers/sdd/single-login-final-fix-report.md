# Single Login Final Fix Report

## Commit

- `1d472c3 fix: reject invalid login roles safely`
- Commit contains only the six contracted source/test files.

## Changes

- Backend login, refresh, and `/auth/me` now preserve a missing relationship as the unsupported empty role string through shared `_role_name` extraction; the access-token role claim matches the response.
- `AuthService.login()` still stores and emits every response, but starts `/auth/me` only for exactly `user` or `admin`.
- The single login submit button renders `เข้าสู่ระบบ` while idle and `กำลังเข้าสู่ระบบ...` with its spinner while loading.

## RED evidence

- `backend/.venv/Scripts/python.exe -m pytest tests/test_auth_role_boundaries.py -q`: **3 failed as expected** before the implementation; login, refresh, and me each returned `user` instead of `""`.
- Focused Karma compile attempt after adding the frontend regression assertions: blocked before execution by the known unrelated `src/app/app.component.spec.ts:20` (`AppComponent.title` does not exist). A test-local typing error found on the first attempt was corrected; the rerun showed only the known blocker.

## GREEN / verification evidence

- `backend/.venv/Scripts/python.exe -m pytest tests/test_auth_role_boundaries.py tests/test_role_dependencies.py -q`: **9 passed**.
- `npx tsc --noEmit -p tsconfig.app.json`: **exit 0**.
- `npm run build -- --configuration development`: **exit 0**, Angular development bundle generated.
- Focused `npm test -- --watch=false --include src/app/core/services/auth.service.spec.ts --include src/app/features/auth/login/login.component.spec.ts`: **blocked**, exit 1 solely at unrelated `src/app/app.component.spec.ts:20` because `AppComponent.title` is absent; Karma did not execute specs.
- `git diff --cached --check`: **exit 0** before commit.
- DB diff check over `backend/app/models`, `backend/seed.py`, and `docker-compose.yml`: **empty**.
- Source checks confirmed empty-string backend fallback, exact `user`/`admin` fetch allowlist, and exact idle/loading Thai copy and assertions.

## Self-review

- API paths, request/response shapes, field types, supported roles, routes/guards, CSS, DB schema/seeds, and EEG/WebSocket code are unchanged.
- Invalid roles retain initial token storage/emission so the login component can synchronously clear the session, without a racing `/auth/me` request.
- Valid `user` and `admin` responses retain eager `/auth/me`; focused service assertions cover both roles.
- No concerns in the scoped diff. The only verification limitation is the pre-existing unrelated Karma compile blocker documented above.
