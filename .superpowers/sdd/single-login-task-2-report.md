# Task 2 Report: Auth Service and Single Login Action

## Files changed

- `frontend/src/app/core/services/auth.service.spec.ts`
- `frontend/src/app/core/services/auth.service.ts`
- `frontend/src/app/features/auth/login/login.component.spec.ts`
- `frontend/src/app/features/auth/login/login.component.ts`
- `frontend/src/app/features/auth/login/login.component.css`

## RED evidence

Before production changes, `node node_modules/typescript/bin/tsc --noEmit -p tsconfig.spec.json` failed on the intended missing contracts:

- `auth.service.spec.ts`: `clearSession` did not exist.
- `login.component.spec.ts`: `clearSession` was not mockable and `onSubmit()` required a role argument.

The same command also exposed the unrelated pre-existing `app.component.spec.ts:20` error: `TS2339: Property 'title' does not exist on type 'AppComponent'`.

## GREEN evidence

- Focused TypeScript spec compilation using the bundled Node v20.20.2 runtime and an isolated temporary spec tsconfig: exit 0.
- Angular development build using bundled Node v20.20.2: exit 0.
- Focused Karma command was attempted with both requested specs and ChromeHeadless, but Angular compiled the pre-existing `app.component.spec.ts` despite `--include`; Karma stopped before executing tests on its `title` TS2339 error.
- Required full `tsc --noEmit -p tsconfig.spec.json`: blocked by the same pre-existing `app.component.spec.ts:20` TS2339 error; task specs have no errors in the focused compilation.

## Commit

`23b27d5 feat: route single login by account role`

## Self-review

- Login posts only typed email/password credentials and routes from the emitted response role.
- Unsupported roles clear both session tokens/current user, avoid navigation, set the exact required access error, and stop loading.
- Logout delegates session cleanup before login navigation; `/auth/me` refresh behavior remains intact.
- Template has one submit button, no role mode/demo UI, and all component styles are in the CSS file with required sizing, colors, hover, and focus-visible treatment.
- Commit contains only the five named task files. Unrelated dirty and untracked files were preserved.

## Concerns

- Karma test execution and the repository-wide spec type-check remain blocked by the unrelated pre-existing `app.component.spec.ts:20` missing `title` property. This task did not alter that out-of-scope file.

## Review fix follow-up

### Files changed

- `frontend/src/app/core/services/auth.service.spec.ts`
- `frontend/src/app/features/auth/login/login.component.spec.ts`
- `frontend/src/app/features/auth/login/login.component.ts`

### Fixes and test coverage

- Replaced all visible mojibake in Login with UTF-8 Thai and Unicode symbols, including exact submit label `เข้าสู่ระบบ`, unsupported-role error `บัญชีนี้ไม่มีสิทธิ์เข้าใช้งานระบบ`, footer copy, ordinary error copy, icons, and password bullets.
- Corrected the template and unsupported-role assertions to require exact Thai rather than repeating corrupted text.
- Added missing-role cleanup coverage alongside unsupported-role coverage.
- Added empty-credentials and already-loading no-op coverage.
- Added logout cleanup-before-navigation call-order coverage.

### RED/GREEN and commands

- RED Karma attempt with bundled Node v20.20.2 and the two `--include` paths was blocked before test execution. It reported the known out-of-scope `app.component.spec.ts:20` TS2339 plus an initial test typing error for Jasmine `invocationOrder`; the call-order test was rewritten with an explicit call log.
- Focused compilation: `node node_modules/typescript/bin/tsc --noEmit -p ../tmp/single-login-tsconfig.spec.json` — exit 0.
- Development build: `node node_modules/@angular/cli/bin/ng.js build --configuration development` — exit 0.
- Mojibake scan of `login.component.ts` for the prior corruption markers — no matches.
- Karma was not represented as executed: the pre-existing `app.component.spec.ts:20` error still prevents the browser test suite from starting.

### Commit

`3e6250b fix: preserve Thai single login copy`

### Self-review and concerns

- The exact Thai literals are independently asserted in the tests, so corrupted production text can no longer be masked by a matching corrupted expectation.
- Missing and unsupported roles take the same safe cleanup path without protected navigation.
- No production behavior beyond Login copy was changed; minor behavior gaps were covered against the implementation already committed.
- Only the three modified Task 2 source/spec files were staged in the follow-up commit. The report remains untracked as requested by the five-file staging constraint.
- Remaining concern: Karma execution is still blocked solely by the out-of-scope `app.component.spec.ts:20` missing `title` property.
