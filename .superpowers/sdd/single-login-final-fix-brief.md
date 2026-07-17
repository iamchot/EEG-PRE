# Final Review Fixes: Single Login Role Routing

Resolve all Important final-review findings using RED-GREEN TDD. One cohesive fix wave.

## Finding 1: Missing backend role is falsely returned as User

Current `backend/app/routers/auth.py` uses `user.role.name if user.role else "user"` at login, refresh, and `/auth/me`. A missing DB role must remain invalid, never become `user`.

- Preserve response/JWT field names and types, API paths, request bodies, and supported role strings.
- Return a non-supported string (prefer the empty string) when the relationship is missing so the existing frontend invalid-role path clears the session.
- Centralize role extraction if useful; do not alter DB schema/seeds.
- Add focused backend tests which fail against the fallback and pass after the fix. Test all three auth response boundaries or the shared extraction contract plus representative boundary wiring.

## Finding 2: Invalid-role cleanup races with eager `/auth/me`

Current `AuthService.login()` starts `_fetchMe()` for every response before Login can reject an invalid role.

- Keep token storage and `/auth/me` refresh behavior for exactly `user` and `admin` login responses.
- Do not start `/auth/me` for missing/unsupported roles; Login then calls `clearSession()` safely.
- Add an AuthService regression test proving an unsupported role emits the response/stores initially but produces no `/auth/me` request, allowing the component to clear it. Retain valid-role `/auth/me` test coverage.
- Do not change the API URL/shape or route guards.

## Finding 3: Loading button copy

- When `loading()` is true, the single submit button must display exact Thai `กำลังเข้าสู่ระบบ...` with the spinner.
- When idle it displays exact Thai `เข้าสู่ระบบ`.
- Add component assertions for both states.

## Files and scope

Expected files only:

- `backend/app/routers/auth.py`
- focused backend test file (new or existing appropriate test)
- `frontend/src/app/core/services/auth.service.ts`
- `frontend/src/app/core/services/auth.service.spec.ts`
- `frontend/src/app/features/auth/login/login.component.ts`
- `frontend/src/app/features/auth/login/login.component.spec.ts`

Do not modify DB, EEG WebSocket, routes/guards, CSS, or unrelated files. Run focused backend tests, frontend focused compile/test attempt, app type-check, Angular development build, DB diff, and source checks. Karma's known unrelated `app.component.spec.ts:20` blocker must be reported honestly.

Commit only scoped files. Append full evidence and commit hash to `.superpowers/sdd/single-login-final-fix-report.md`. Return short status, commit, test/build summary, concerns.
