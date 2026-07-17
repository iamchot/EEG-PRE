# Single Login and Role Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace role-selection login buttons with one login action and enforce strict User/Admin separation in Angular routes and FastAPI HTTP endpoints without changing the database.

**Architecture:** The Login component routes immediately from `TokenResponse.role`, while `AuthService` continues loading `/auth/me` for the application shell. Angular uses role-aware `userGuard`, `adminGuard`, and `guestGuard`; FastAPI uses `StandardUser` and `AdminUser` dependencies at endpoint boundaries. Existing role tables, JWT claims, API shapes, and the EEG WebSocket contract remain unchanged.

**Tech Stack:** Angular 19 standalone components, Angular Signals, RxJS, Jasmine/Karma, FastAPI, SQLAlchemy 2, pytest.

## Global Constraints

- Supported roles are exactly `user` and `admin`.
- Login requests contain only `email` and `password`; the browser never submits a role.
- `user` routes to `/dashboard`; `admin` routes to `/admin`.
- Missing or unsupported roles clear credentials and return to `/login`.
- User HTTP APIs reject Admin accounts with HTTP 403; Admin APIs continue rejecting User accounts.
- Do not change database tables, columns, role seeds, JWT payload shape, or Login API URL/response shape.
- Do not change EEG WebSocket authorization in this scope.
- Preserve unrelated working-tree changes and stage only files listed by each task.
- Any CSS changed in the Login component must live in `login.component.css`, not inline component metadata.

## File Structure

- Create `backend/tests/test_role_dependencies.py`: direct tests for `require_user` and `require_admin`.
- Modify `backend/app/middleware/auth_middleware.py`: add `require_user` and `StandardUser`.
- Modify `backend/app/routers/persona.py`: use `StandardUser` for Persona endpoints.
- Modify `backend/app/routers/eeg_session.py`: use `StandardUser` for HTTP endpoints while leaving WebSocket unchanged.
- Modify `backend/app/routers/comic.py`: use `StandardUser` for User comic and rating endpoints.
- Create `frontend/src/app/core/services/auth.service.spec.ts`: token persistence and login-response tests.
- Modify `frontend/src/app/core/services/auth.service.ts`: expose `TokenResponse`, centralize credential clearing.
- Create `frontend/src/app/features/auth/login/login.component.spec.ts`: one-button and role-routing tests.
- Modify `frontend/src/app/features/auth/login/login.component.ts`: one submit action and role-based routing.
- Create `frontend/src/app/features/auth/login/login.component.css`: extracted Login styles.
- Create `frontend/src/app/core/guards/auth.guard.spec.ts`: loaded-user and refresh-fetch role-guard tests.
- Modify `frontend/src/app/core/guards/auth.guard.ts`: add `userGuard` and make all guards role-aware.
- Modify `frontend/src/app/app.routes.ts`: attach `userGuard` to User routes.

---

### Task 1: FastAPI User/Admin HTTP Boundary

**Files:**

- Create: `backend/tests/test_role_dependencies.py`
- Modify: `backend/app/middleware/auth_middleware.py`
- Modify: `backend/app/routers/persona.py`
- Modify: `backend/app/routers/eeg_session.py`
- Modify: `backend/app/routers/comic.py`

**Interfaces:**

- Produces: `require_user(current_user: User) -> User` and `StandardUser = Annotated[User, Depends(require_user)]`.
- Preserves: `require_admin`, `CurrentUser`, `AdminUser`, HTTP endpoint paths, request/response models, and `eeg_websocket` signature.

- [ ] **Step 1: Write failing dependency tests**

Create `backend/tests/test_role_dependencies.py`:

```python
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.middleware.auth_middleware import require_admin, require_user


def account(role_name: str | None):
    role = SimpleNamespace(name=role_name) if role_name else None
    return SimpleNamespace(id=1, role=role)


def test_require_user_accepts_user():
    user = account("user")
    assert require_user(user) is user


@pytest.mark.parametrize("role_name", ["admin", None, "editor"])
def test_require_user_rejects_non_user_roles(role_name):
    with pytest.raises(HTTPException) as exc:
        require_user(account(role_name))
    assert exc.value.status_code == 403
    assert exc.value.detail == "User access required"


def test_require_admin_accepts_admin_and_rejects_user():
    admin = account("admin")
    assert require_admin(admin) is admin
    with pytest.raises(HTTPException) as exc:
        require_admin(account("user"))
    assert exc.value.status_code == 403
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
cd backend
python -m pytest tests/test_role_dependencies.py -q
```

Expected: collection/import failure because `require_user` does not exist.

- [ ] **Step 3: Implement `require_user`**

Add to `auth_middleware.py`:

```python
def require_user(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.role or current_user.role.name != "user":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User access required",
        )
    return current_user


StandardUser = Annotated[User, Depends(require_user)]
```

- [ ] **Step 4: Apply `StandardUser` to User HTTP endpoints**

Replace `CurrentUser` with `StandardUser` in Persona CRUD and Comic/Rating endpoints. In `eeg_session.py`, use `StandardUser` only for normal HTTP endpoint parameters. Keep this exact WebSocket declaration unchanged:

```python
@router.websocket("/ws/{session_id}")
async def eeg_websocket(session_id: str, websocket: WebSocket):
```

Update imports to:

```python
from app.middleware.auth_middleware import StandardUser
```

Do not change endpoint URLs, database filters, request bodies, or response types.

- [ ] **Step 5: Run focused backend tests and source contract checks**

Run:

```powershell
cd backend
python -m pytest tests/test_role_dependencies.py -q
rg -n "current_user: StandardUser" app/routers/persona.py app/routers/eeg_session.py app/routers/comic.py
rg -n "async def eeg_websocket\(session_id: str, websocket: WebSocket\)" app/routers/eeg_session.py
```

Expected: dependency tests pass; User HTTP endpoints show `StandardUser`; WebSocket signature remains present.

- [ ] **Step 6: Commit backend role boundary**

```powershell
git add -- backend/tests/test_role_dependencies.py backend/app/middleware/auth_middleware.py backend/app/routers/persona.py backend/app/routers/eeg_session.py backend/app/routers/comic.py
git commit -m "feat: enforce user-only API boundaries"
```

---

### Task 2: Auth Service and Single Login Action

**Files:**

- Create: `frontend/src/app/core/services/auth.service.spec.ts`
- Modify: `frontend/src/app/core/services/auth.service.ts`
- Create: `frontend/src/app/features/auth/login/login.component.spec.ts`
- Modify: `frontend/src/app/features/auth/login/login.component.ts`
- Create: `frontend/src/app/features/auth/login/login.component.css`

**Interfaces:**

- `AuthService.login(body: LoginRequest)` emits `TokenResponse` after storing tokens.
- `AuthService.clearSession(): void` removes both tokens and clears `currentUser` without navigation.
- `LoginComponent.onSubmit(): void` routes from `TokenResponse.role`.

- [ ] **Step 1: Write failing Auth service tests**

Create `auth.service.spec.ts` using `HttpTestingController`. Assert that `login()` POSTs only email/password, emits the complete response, stores both tokens, and calls `/auth/me`. Add a test that `clearSession()` removes both tokens and clears `currentUser`.

Core expectations:

```ts
service.login({ email: 'admin@example.com', password: 'secret123' }).subscribe(response => {
  expect(response.role).toBe('admin');
});

const login = http.expectOne(`${environment.apiUrl}/auth/login`);
expect(login.request.body).toEqual({ email: 'admin@example.com', password: 'secret123' });
login.flush({ access_token: 'a', refresh_token: 'r', token_type: 'bearer', role: 'admin' });

expect(localStorage.getItem('access_token')).toBe('a');
expect(localStorage.getItem('refresh_token')).toBe('r');
```

- [ ] **Step 2: Write failing Login component tests**

Create `login.component.spec.ts` with Auth/Router doubles. Assert:

```ts
expect(element.querySelectorAll('button[type="submit"]').length).toBe(1);
expect(element.textContent).not.toContain('Login as User');
expect(element.textContent).not.toContain('Login as Admin');
```

For `onSubmit()`:

```ts
auth.login.and.returnValue(of(tokenResponse('user')));
component.email = 'user@example.com';
component.password = 'secret123';
component.onSubmit();
expect(router.navigate).toHaveBeenCalledWith(['/dashboard']);

auth.login.and.returnValue(of(tokenResponse('admin')));
component.onSubmit();
expect(router.navigate).toHaveBeenCalledWith(['/admin']);
```

For an unsupported role, assert `auth.clearSession()`, no protected navigation, and `บัญชีนี้ไม่มีสิทธิ์เข้าใช้งานระบบ`.

- [ ] **Step 3: Run frontend tests and verify RED**

Run with the bundled Node runtime:

```powershell
cd frontend
& 'C:\Users\sirik\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' '.\node_modules\@angular\cli\bin\ng.js' test --watch=false --include='src/app/core/services/auth.service.spec.ts' --include='src/app/features/auth/login/login.component.spec.ts'
```

Expected: failures because `clearSession()` and the parameterless single-login behavior do not exist. If the repository's existing `app.component.spec.ts` blocks compilation, record that exact pre-existing failure and also run TypeScript compilation after implementation.

- [ ] **Step 4: Implement Auth service contract**

Keep `login()` returning the HTTP observable with `TokenResponse`:

```ts
login(body: LoginRequest) {
  return this.http.post<TokenResponse>(`${this.apiUrl}/auth/login`, body).pipe(
    tap((res) => {
      localStorage.setItem('access_token', res.access_token);
      localStorage.setItem('refresh_token', res.refresh_token);
      this._fetchMe();
    }),
  );
}

clearSession() {
  localStorage.removeItem('access_token');
  localStorage.removeItem('refresh_token');
  this.currentUser.set(null);
}

logout() {
  this.clearSession();
  this.router.navigate(['/login']);
}
```

- [ ] **Step 5: Replace Login template and component logic**

Use one form submit:

```html
<form (ngSubmit)="onSubmit()" novalidate>
  <button type="submit" class="btn btn-login" id="btn-login" [disabled]="loading()">
    @if (loading()) {
      <span class="spinner" aria-hidden="true"></span>
      <span>กำลังเข้าสู่ระบบ...</span>
    } @else {
      <span>เข้าสู่ระบบ</span>
    }
  </button>
</form>
```

Treat this as a bounded replacement for the current `<form>` opening tag and the current `.btn-group` containing the two role buttons. Leave the existing email field, password field, and `@if (error())` alert between them unchanged; delete only the old `.btn-group`, role buttons, and mock note.

Implement role routing:

```ts
onSubmit() {
  if (!this.email || !this.password || this.loading()) return;
  this.loading.set(true);
  this.error.set('');

  this.authService.login({ email: this.email, password: this.password }).subscribe({
    next: ({ role }) => {
      if (role === 'user') {
        this.router.navigate(['/dashboard']);
      } else if (role === 'admin') {
        this.router.navigate(['/admin']);
      } else {
        this.authService.clearSession();
        this.error.set('บัญชีนี้ไม่มีสิทธิ์เข้าใช้งานระบบ');
        this.loading.set(false);
      }
    },
    error: (err: { error?: { detail?: string } }) => {
      this.error.set(err?.error?.detail ?? 'เข้าสู่ระบบไม่สำเร็จ กรุณาตรวจสอบอีเมลและรหัสผ่าน');
      this.loading.set(false);
    },
  });
}
```

Remove `loginMode`, role parameters, demo prefill, role-specific buttons, and mock note.

- [ ] **Step 6: Extract Login CSS**

Move the existing Login styles to `login.component.css`, remove the inline `styles` array, and set:

```ts
styleUrl: './login.component.css',
```

Replace `.btn-user`/`.btn-admin` rules with:

```css
.btn-login {
  width: 100%;
  min-height: 48px;
  color: #fff;
  background: #7c3aed;
  box-shadow: 0 4px 20px rgba(124, 58, 237, 0.3);
}
.btn-login:hover:not(:disabled) { background: #6d28d9; }
.btn-login:focus-visible { outline: 3px solid rgba(196, 181, 253, 0.55); outline-offset: 3px; }
```

- [ ] **Step 7: Run focused checks and commit**

Run focused tests, `tsc --noEmit -p tsconfig.spec.json`, and Angular development build. Expected: new specs type-check; build exits 0; any remaining `app.component.spec.ts` failure is reported separately.

```powershell
git add -- frontend/src/app/core/services/auth.service.ts frontend/src/app/core/services/auth.service.spec.ts frontend/src/app/features/auth/login/login.component.ts frontend/src/app/features/auth/login/login.component.css frontend/src/app/features/auth/login/login.component.spec.ts
git commit -m "feat: route single login by account role"
```

---

### Task 3: Role-Aware Angular Guards and Routes

**Files:**

- Create: `frontend/src/app/core/guards/auth.guard.spec.ts`
- Modify: `frontend/src/app/core/guards/auth.guard.ts`
- Modify: `frontend/src/app/app.routes.ts`

**Interfaces:**

- Produces: `userGuard`, revised `adminGuard`, revised `guestGuard`.
- Consumes: `AuthService.currentUser`, `AuthService.getToken()`, `AuthService.clearSession()`, `/auth/me`.

- [ ] **Step 1: Write failing guard tests**

Use `TestBed.runInInjectionContext()` with Router, HttpClient testing, and an AuthService double. Cover:

- loaded User: `userGuard` true, `adminGuard` returns `/dashboard`, `guestGuard` returns `/dashboard`
- loaded Admin: `adminGuard` true, `userGuard` returns `/admin`, `guestGuard` returns `/admin`
- stored token with null `currentUser`: each role-aware guard requests `/auth/me` before deciding
- unsupported role: calls `clearSession()` and returns `/login` or allows the guest route
- missing token: protected guards return `/login`; guest guard returns true

- [ ] **Step 2: Run guard tests and verify RED**

Expected: import/behavior failures because `userGuard` does not exist and `guestGuard` always returns `/dashboard`.

- [ ] **Step 3: Implement shared role resolution**

Add a private helper in `auth.guard.ts`:

```ts
type SupportedRole = 'user' | 'admin';

function roleOf(user: UserPublic | null): SupportedRole | null {
  return user?.role === 'user' || user?.role === 'admin' ? user.role : null;
}
```

For refresh paths, request `/auth/me`, set `currentUser`, then map the supported role to the correct allow/redirect result. On request error, call `clearSession()` and return `/login`.

- [ ] **Step 4: Implement and apply `userGuard`**

Export `userGuard` and update User routes:

```ts
import { authGuard, adminGuard, guestGuard, userGuard } from './core/guards/auth.guard';

{
  path: 'dashboard',
  canActivate: [authGuard, userGuard],
  // existing loadComponent unchanged
}
```

Apply the same `[authGuard, userGuard]` sequence to `/persona`, `/eeg-session`, `/comic/:id`, and `/history`. Keep `/admin` as `[authGuard, adminGuard]`.

- [ ] **Step 5: Run guards, build, and route source checks**

Run focused guard tests, TypeScript compilation, and development build. Then:

```powershell
rg -n "canActivate: \[authGuard, userGuard\]" src/app/app.routes.ts
rg -n "canActivate: \[authGuard, adminGuard\]" src/app/app.routes.ts
```

Expected: five User routes and one Admin route.

- [ ] **Step 6: Commit Angular role guards**

```powershell
git add -- frontend/src/app/core/guards/auth.guard.ts frontend/src/app/core/guards/auth.guard.spec.ts frontend/src/app/app.routes.ts
git commit -m "feat: enforce role-aware Angular routes"
```

---

### Task 4: End-to-End Verification

**Files:** No planned production changes.

- [ ] **Step 1: Run backend focused tests**

```powershell
cd backend
python -m pytest tests/test_role_dependencies.py -q
```

Expected: all role-dependency tests pass.

- [ ] **Step 2: Run Angular focused tests and development build**

Run Login/Auth/Guard focused specs and the Angular development build with bundled Node. Record exact failures if Chrome/Karma is unavailable; do not claim test execution from compilation alone.

- [ ] **Step 3: Verify database schema is untouched**

```powershell
git diff a52a937..HEAD -- backend/app/models backend/app/database.py backend/seed.py
```

Expected: no output.

- [ ] **Step 4: Verify role boundary source contracts**

Confirm one Login button, no role-specific labels, five User routes, one Admin route, `StandardUser` on User HTTP endpoints, and unchanged EEG WebSocket signature.

- [ ] **Step 5: Final review**

Review the complete diff against `docs/superpowers/specs/2026-07-17-single-login-role-routing-design.md`. Fix Critical and Important findings with a failing test before implementation changes.
