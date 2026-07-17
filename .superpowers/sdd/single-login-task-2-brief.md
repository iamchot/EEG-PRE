# Task 2: Auth Service and Single Login Action

Implement the approved single-login UI using strict RED-GREEN TDD.

## Files

- Create `frontend/src/app/core/services/auth.service.spec.ts`
- Modify `frontend/src/app/core/services/auth.service.ts`
- Create `frontend/src/app/features/auth/login/login.component.spec.ts`
- Modify `frontend/src/app/features/auth/login/login.component.ts`
- Create `frontend/src/app/features/auth/login/login.component.css`

## Required behavior

- Export or otherwise make the existing `TokenResponse` type consumable by Login tests/component.
- `AuthService.login({email,password})` POSTs only those fields to the existing `/auth/login`, emits the complete `TokenResponse`, stores access/refresh tokens, and retains the existing `/auth/me` refresh behavior.
- Add `clearSession(): void` which removes both tokens and clears `currentUser` without navigation; make `logout()` call it before navigating to `/login`.
- Replace the two role-select Login buttons with exactly one submit button labeled `เข้าสู่ระบบ`; the form calls parameterless `onSubmit()`.
- Remove role parameters, `loginMode`, demo Admin credential prefill, role-specific labels, and mock/demo note.
- Route directly from the Login response role: `user` -> `/dashboard`, `admin` -> `/admin`.
- Missing/unsupported role must call `clearSession()`, perform no protected navigation, show `บัญชีนี้ไม่มีสิทธิ์เข้าใช้งานระบบ`, and stop loading.
- Empty credentials or an already-loading form do nothing.
- Keep existing email/password fields and ordinary login error handling.
- Move every Login component style from inline metadata into `login.component.css`; use `styleUrl: './login.component.css'`.
- Main button should be full width, at least 48px high, purple (`#7c3aed`, hover `#6d28d9`) with accessible focus-visible outline.
- Do not change backend, routes/guards (Task 3), DB, API URL/response shape, or unrelated files.
- Stage only the five files above and commit `feat: route single login by account role`.

## Required tests

Write tests before production changes and capture RED evidence.

Auth service tests with `HttpTestingController`:

- request body is exactly `{ email, password }`;
- subscriber receives complete response including `role`;
- both tokens are stored and `/auth/me` is requested;
- `clearSession()` removes both tokens and clears `currentUser`.

Login component tests:

- rendered template has exactly one `button[type="submit"]` and no `Login as User` / `Login as Admin` text;
- User response navigates to `/dashboard`;
- Admin response navigates to `/admin`;
- unsupported role clears session, does not navigate to protected pages, and renders/sets the exact Thai access error.

Use the bundled Node runtime for focused tests. Also run `tsc --noEmit -p tsconfig.spec.json` and Angular development build after implementation. If Karma/Chrome or the pre-existing `app.component.spec.ts` blocks tests, report the exact failure separately; do not represent compilation as test execution.

## Report

Write `.superpowers/sdd/single-login-task-2-report.md` with files changed, RED/GREEN evidence, type-check/build results, commit hash, self-review, and concerns. Return only status, commit hash, one-line test summary, and concerns.
