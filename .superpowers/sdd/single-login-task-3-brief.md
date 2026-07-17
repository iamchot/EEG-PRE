# Task 3: Role-Aware Angular Guards and Routes

Implement the approved Angular role boundary using strict RED-GREEN TDD.

## Files

- Create `frontend/src/app/core/guards/auth.guard.spec.ts`
- Modify `frontend/src/app/core/guards/auth.guard.ts`
- Modify `frontend/src/app/app.routes.ts`

## Requirements

- Supported roles are exactly `user` and `admin`.
- Add exported `userGuard`; revise `adminGuard` and `guestGuard` to be role-aware.
- Loaded User: `userGuard` allows, `adminGuard` redirects `/dashboard`, `guestGuard` redirects `/dashboard`.
- Loaded Admin: `adminGuard` allows, `userGuard` redirects `/admin`, `guestGuard` redirects `/admin`.
- With a stored token and null `currentUser`, role-aware guards request the existing `/auth/me`, set `currentUser`, then decide.
- Missing token: protected role guards return `/login`; guest guard allows.
- Missing/unsupported role: call `clearSession()` and return `/login` for protected access; guest route is allowed.
- On `/auth/me` error: call `clearSession()`; protected guards return `/login`, guest route is allowed.
- Use the existing `AuthService.currentUser`, `getToken()`, `clearSession()`, existing `UserPublic`, and API URL. Do not change AuthService in this task.
- Attach `[authGuard, userGuard]` to exactly these five User routes: `/dashboard`, `/persona`, `/eeg-session`, `/comic/:id`, `/history`.
- Keep `/admin` as `[authGuard, adminGuard]`.
- Do not alter component lazy loading, paths, backend, DB, or unrelated files.
- Stage only the three files above and commit `feat: enforce role-aware Angular routes`.

## Required tests

Write guard tests first using `TestBed.runInInjectionContext()` and suitable Router/AuthService/HTTP testing doubles. Cover all loaded User/Admin cases, refresh-fetch for role-aware guards, unsupported/missing role cleanup, missing token behavior, and request-error cleanup.

Capture the expected RED failure because `userGuard` does not yet exist or old `guestGuard` behavior is wrong. After implementation, run focused compilation/tests where possible, TypeScript compilation, Angular development build, and source checks:

- exactly five `canActivate: [authGuard, userGuard]` routes;
- exactly one `canActivate: [authGuard, adminGuard]` route.

The existing unrelated `app.component.spec.ts:20` TS2339 may block Karma/full spec compilation. Record this precisely and still run focused spec compilation plus the development build with the bundled Node runtime.

## Report

Write `.superpowers/sdd/single-login-task-3-report.md` with files changed, RED/GREEN evidence, source-check counts, build/type-check result, commit, self-review, and concerns. Return only status, commit hash, one-line test summary, and concerns.
