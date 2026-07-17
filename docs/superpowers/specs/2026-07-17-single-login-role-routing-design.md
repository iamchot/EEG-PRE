# Single Login and Role Routing - Design Specification

**Project:** Dream Comicverse
**Date:** 2026-07-17
**Scope:** Authentication entry point and strict two-role access separation

## 1. Purpose

Replace the separate `Login as User` and `Login as Admin` actions with one login action. The system must determine the destination and permitted application area from the authenticated account's server-provided role.

The implementation must enforce the same two-role boundary in both Angular routing and FastAPI dependencies. Users must not choose or submit their own role during login.

## 2. Supported Roles

The only supported roles are:

- `user`
- `admin`

The existing database already supports this model through the `roles` table and `users.role_id`. The existing `users.is_active` field continues controlling suspended accounts. No database migration, new table, or new column is required.

Any missing or unsupported role is treated as an invalid authorization state. The frontend clears stored credentials, returns to `/login`, and displays an access error. Backend role dependencies reject unsupported roles with HTTP 403.

## 3. Login Screen

Preserve the existing PDF-inspired dark Navy-Purple card, email field, password field, registration link, loading state, and error presentation.

Replace both role-specific buttons with one submit button:

- Label: `เข้าสู่ระบบ`
- Loading label: `กำลังเข้าสู่ระบบ...`
- Button type: `submit`
- Form submission calls `onSubmit()` without a role parameter

Remove:

- `Login as User`
- `Login as Admin`
- `loginMode`
- Demo credential prefill based on the selected button
- The mock-login note, because authentication uses the real backend

The login request remains `{ email, password }`; it must never include `role`.

## 4. Post-Login Routing

Use the `role` returned by `POST /auth/login` as the immediate routing decision:

| Role | Destination |
|---|---|
| `user` | `/dashboard` |
| `admin` | `/admin` |
| missing or unsupported | clear credentials and return to `/login` with an access error |

The Auth service must expose the `TokenResponse` to the Login component instead of discarding it inside `tap`. It may continue fetching `/auth/me` to populate the full current user, but routing must not race against that asynchronous request.

## 5. Frontend Route Separation

### `authGuard`

Continues verifying that an access token exists for authenticated routes.

### `userGuard`

Add a guard for User-only routes:

- `/dashboard`
- `/persona`
- `/eeg-session`
- `/comic/:id`
- `/history`

Behavior:

- `user` -> allow
- `admin` -> redirect to `/admin`
- missing/unsupported role -> clear credentials and redirect to `/login`
- when `currentUser` has not loaded after refresh, fetch `/auth/me` before deciding

### `adminGuard`

Preserve Admin-only protection:

- `admin` -> allow
- `user` -> redirect to `/dashboard`
- missing/unsupported role -> clear credentials and redirect to `/login`
- when `currentUser` has not loaded after refresh, fetch `/auth/me` before deciding

### `guestGuard`

For authenticated visitors opening `/login` or `/register`:

- `user` -> `/dashboard`
- `admin` -> `/admin`
- missing/unsupported role -> clear credentials and allow `/login`
- when the token exists but `currentUser` has not loaded, fetch `/auth/me` before redirecting

## 6. Frontend Navigation Shell

Keep the existing role-based sidebar behavior:

- User sees Dashboard, Personas, Create Dream, and Timeline.
- Admin sees Admin Panel only.

The shell must not briefly render User navigation for an Admin during application initialization. Existing authentication initialization remains responsible for loading `/auth/me` before protected navigation renders.

## 7. Backend Role Separation

Keep the existing `require_admin` dependency for `/admin/*` endpoints.

Add `require_user`, plus a `StandardUser` annotated dependency, that allows only accounts whose role name is exactly `user`.

Apply `StandardUser` to User-owned functional endpoints:

- Persona CRUD
- EEG session HTTP endpoints
- Comic generation, listing, retrieval, and ratings

For the EEG WebSocket endpoint, preserve its current connection contract in this scope. WebSocket authorization requires a separate design because the current endpoint does not yet resolve a database user from the token; do not silently claim that HTTP dependency changes secure the WebSocket.

Backend behavior:

- User calling Admin API -> HTTP 403
- Admin calling User-only HTTP API -> HTTP 403
- Inactive account -> HTTP 401 through the existing current-user check
- Missing/unsupported role -> HTTP 403

## 8. Data and API Contract

No database schema changes are required.

Preserve:

- `TokenResponse.role`
- `UserPublic.role`
- JWT `role` claim
- `roles.name`
- `users.role_id`
- `users.is_active`
- Login request and response URLs and shapes

The database remains the source of truth for the current role. Route decisions use server responses, not a role selected by the browser.

## 9. Error Handling

- Invalid email/password: show the existing login failure message.
- Inactive account: use a generic login failure message to avoid disclosing account status.
- `/auth/me` failure with a stored token: clear credentials and redirect to `/login`.
- Unsupported role after login: clear both tokens, clear `currentUser`, remain on `/login`, and show `บัญชีนี้ไม่มีสิทธิ์เข้าใช้งานระบบ`.
- Role-restricted route: redirect to the valid home for the authenticated role without showing a false login failure.

## 10. Out of Scope

The following findings are tracked separately and must not expand this implementation:

- Admin EEG Dataset response does not match the current frontend row model.
- Add User has no complete Admin API workflow.
- Add Sample has no complete Admin API workflow.
- Admin statistics do not directly return `active_users` and `eeg_samples`.
- CSV export is not implemented.
- Full permission-table RBAC is not required for two roles.
- EEG WebSocket token-based role enforcement needs its own security design.

## 11. Testing and Acceptance Criteria

### Frontend

- Login screen renders exactly one submit button.
- Login request contains email and password only.
- User login navigates to `/dashboard`.
- Admin login navigates to `/admin`.
- Routing uses `TokenResponse.role` and does not wait for `currentUser` to populate.
- Unsupported role clears authentication and displays the access error.
- `userGuard`, `adminGuard`, and `guestGuard` cover loaded-user and refresh-fetch paths.
- Admin cannot activate User routes; User cannot activate Admin routes.
- Authenticated Admin opening `/login` is redirected to `/admin`.
- Authenticated User opening `/login` is redirected to `/dashboard`.

### Backend

- `require_user` allows role `user` and rejects role `admin` or missing roles with HTTP 403.
- `require_admin` continues allowing only role `admin`.
- Representative Persona, EEG HTTP, and Comic endpoints use `StandardUser`.
- Admin API endpoints continue using `AdminUser`.

### Verification

- Angular development build succeeds.
- Focused Angular tests compile and execute where the environment permits Chrome/Karma.
- Backend focused tests pass.
- Existing database tables remain unchanged.
