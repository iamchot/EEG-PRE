Task 1: complete (commit d744756, review clean)
Task 2: complete (commit 0ddc051, review clean)
Task 3: complete (verification pass, no code commit)

## Single Login Role Routing (2026-07-17)

Task 1: complete (commit 87666a4..f37112b, spec PASS, quality APPROVED; one provenance-only Minor noted)
Task 2: complete (commits f37112b..3e6250b, spec PASS, quality APPROVED; Karma blocked by pre-existing app.component.spec.ts)
Task 3: complete (commit 3e6250b..60f27b9, spec PASS, quality APPROVED; three Minor test/comment findings noted)
Task 4: complete (commit 1d472c3; broad review READY; backend 9 passed, Angular app type-check/build passed, DB diff empty; Karma blocked by pre-existing app.component.spec.ts:20)

## EEG Dataset Collection Foundation (2026-07-17)

Plan commit: 6b949cc
Task 1: complete (commit 6b949cc..49dc9b3, spec PASS, quality APPROVED; two Minor resilience findings noted)
Task 2: complete (commits 49dc9b3..4dfdd72, spec PASS, quality APPROVED)
Task 3: complete (commits 4dfdd72..c87177e, spec PASS, quality APPROVED)
Task 4: complete (commits c87177e..b2b8978, spec PASS, quality APPROVED)
Task 5: complete (commits b2b8978..611431e, spec PASS, quality APPROVED; unused legacy CSS selectors noted)
Task 6: complete (commits 611431e..e8eb70b, spec PASS, quality APPROVED; 28 focused Karma tests)
Task 7: complete (broad review READY; backend 62 passed, focused Karma 28 passed, app type-check/build passed, MySQL at 20260717_01)

## Muse and Trial Runner (2026-07-19)
Plan commit: c810ecf
- [x] Task 1: Persisted Collection Lifecycle Schema — 9fa0c15 — SPEC PASS / QUALITY APPROVED
- [x] Task 2: Balanced Schedule Creation — d615f26 — SPEC PASS / QUALITY APPROVED
- [x] Task 3: Atomic Raw EEG Writer — d8666e3 — SPEC PASS / QUALITY APPROVED
- [x] Task 4: Recoverable Trial State Machine — 2de38b9 — SPEC PASS / QUALITY APPROVED
- [x] Task 5: Muse Adapter and Admin Collection API/WebSocket — af97a8b — SPEC PASS / QUALITY APPROVED
- [x] Task 6: Angular HTTP and WebSocket Clients — 29b6585 — SPEC PASS / QUALITY APPROVED
- [x] Task 7: Admin Trial Runner UI — a47f25d — SPEC PASS / QUALITY APPROVED
- [ ] Task 8: End-to-End Verification and Final Review

### PAUSED CHECKPOINT — 2026-07-19

User requested a pause. All active subagents were interrupted; do not resume automatically.

Committed HEAD: `f728794` (`fix: enforce collection signal and media integrity`).

Additional committed broad-review fixes before HEAD:

- `5641aa5` — serialize trial schedule creation; adds Alembic `20260719_03`.
- `b24e8d9` — real independent-connection MySQL scheduler/migration tests; final review SPEC PASS / QUALITY APPROVED.
- `f728794` — first signal-integrity/media synchronization fix; follow-up review still found three issues listed below.

Live database status at pause: Alembic `20260719_02`. Migration `20260719_03` is committed but NOT yet applied. Existing Task-8 schema backup for the 02 migration is preserved at `.superpowers/sdd/muse-runner-task-8-schema-before-20260719.sql`; create a new nonempty backup before applying 03.

Uncommitted work that must be preserved:

1. Device/deployment hardening (implementation complete but interrupted before commit): `README.md`, `backend/.env.example`, `backend/app/config.py`, `backend/app/routers/dataset_collection.py`, `backend/app/ws/collection_manager.py`, `backend/requirements_backend.txt`, `backend/tests/test_collection_runner_api.py`, plus new `backend/COLLECTION_OPERATIONS.md`, `backend/start_collection_backend.ps1`, and `backend/tests/test_collection_recovery_integration.py`. Intended behavior: SHA-256 keyed cross-process FileLock device lease, Muse-to-LSL/single-worker operator workflow, no local media basename disclosure, and a committed real-writer recovery regression. Last focused evidence reported: 35 passed; not independently reviewed yet.

2. Signal-integrity follow-up is only at RED-test stage after interrupt: modified `backend/tests/test_collection_state_machine.py` and `frontend/src/app/features/dataset-collection-runner/dataset-collection-runner.component.spec.ts`. Required production fixes are not yet implemented: adapter-owned source sequence watermark + LSL-bound marker clock; state-machine recomputation of 256±8 readiness and sensor score/state consistency; fail-closed duplicate/backward/nonfinite post-boundary samples while Raw-auditing strictly increasing rate-invalid samples; handle rejected post-start `video.play()` by interrupting the Backend exactly once.

3. `.superpowers/sdd/broad-fix-signal-media-report.md` contains the independent FAIL review details and is intentionally uncommitted scratch/report state.

Remaining sequence when resumed:

- Finish and exact-commit the device/deployment hardening without losing the uncommitted files above.
- Implement the two RED test files' signal/media follow-up; run Backend + focused Angular + build; exact-commit.
- Independent review both fix sets; resolve all Critical/Important findings.
- Create a fresh schema-only MySQL backup, apply Alembic `20260719_03`, and verify uniqueness/schema parity.
- Rerun full Task-8 Backend, focused Karma, TypeScript/build, real-writer fake-Muse recovery, auth/privacy/no-BLOB/source-isolation checks.
- Run final broad review from Plan-2 baseline `c810ecf` to the final HEAD. Mark Task 8 complete only after READY / SPEC PASS / QUALITY APPROVED.

### RESUMED — 2026-07-27

- Added root `AGENTS.md` in `3b63a6b`, including the user-requested no-build rule.
- Task 8A device/deployment hardening: complete (`3b63a6b..bb06eb4`), independent review SPEC PASS / QUALITY APPROVED, no findings; focused Backend evidence 37 passed.
- Task 8B signal/media integrity follow-up: in progress.

Task 8B: complete (`bb06eb4..2d22797`, review clean after fix rounds 1–3).
- Round 1: `1a936ac`, 3/4 findings addressed.
- Round 2: `b00ec17`, physical pull watermark Critical addressed; one marker-ordering Important found.
- Round 3: `2d22797`, marker boundary ordering addressed; no new Critical/Important.
- Latest focused evidence: Backend 84 passed, Angular 27 passed; no build run.

Task 8C non-build end-to-end verification: in progress.

Task 8C partial result:
- Non-DB verification PASS: Backend 190 passed / 2 expected skipped; focused Angular 72 passed; fake-Muse/real-writer recovery 1 passed; scope/privacy checks 5 passed.
- No build run per root `AGENTS.md`.
- BLOCKED only on live MySQL: configured localhost refused connection and no MySQL/MariaDB Windows service or port 3306 listener was found.
- Safety guard held: no new backup was created and migration `20260719_03` was not applied.

### PAUSED CHECKPOINT — 2026-07-27 (final fix wave)

User requested status/list and work is paused. Do not resume automatically.

- Last committed HEAD: `2d22797` (`fix: make Muse marker boundary atomic`).
- Final broad review: SPEC FAIL / QUALITY CHANGES_REQUIRED / CODE READY NO.
- The single final fix-wave agent was interrupted after reproducing all RED
  findings and after beginning GREEN implementation. Its production/test
  changes are uncommitted and have not yet received final GREEN verification,
  scope audit, commit, or independent re-review.
- Preserve all current dirty files. The final-wave changes include Backend
  state response/WS, stimulus timing, schedule/baseline preconditions, startup
  script safety, and Angular stream/media recovery files.
- Final-wave RED evidence before interruption:
  - Backend: 10 expected failing regressions.
  - Angular: 3 expected failing regressions, 36 passed.
- Remaining final-review findings being fixed:
  1. Canonical enriched runner-state DTO for HTTP and WebSocket.
  2. Bounded finish grace for valid 60-second stimuli.
  3. Launcher refusal for missing/placeholder secret.
  4. Terminal/completed summary must not acquire Muse lease.
  5. Backend enforcement of device → 12-row schedule → baseline.
  6. Surface safe `stream_error`.
  7. Media error triggers exactly-once Backend interruption.
- After implementation: run focused GREEN tests (no build), exact-commit the
  final fix wave, and perform exactly one scoped final re-review.
- External DB blocker remains: MySQL localhost unavailable. Before applying
  `20260719_03`, create/verify a new nonempty schema-only backup; then apply
  migration and verify revision, uniqueness constraint, and schema parity.
- Only after code re-review and DB gate pass: update Task 8 to complete.

### RESUMED RESULT — 2026-07-27

- Final fix wave committed as `52ee21e` (`fix: close final Muse runner review findings`).
- Focused GREEN evidence: Backend 105 passed / 1 expected MySQL-only skip /
  1 existing warning; Angular 39/39 passed; no build run.
- Single scoped final re-review: NOT APPROVED.
- Six of seven findings were addressed.
- Residual load-bearing Important finding: `start_collection_backend.ps1`
  validates the raw `.env` line instead of the effective Pydantic
  `Settings.secret_key`. An inline dotenv comment or process-level
  `SECRET_KEY` override can still make the effective secret equal the public
  placeholder while bypassing the launcher guard.
- Per the final-review one-fix-wave cap, no second fix wave was started.
  Human authorization is required to open an additional TDD fix/re-review
  round for this residual security finding.
- External DB blocker remains unchanged: MySQL localhost unavailable; no fresh
  backup and no `20260719_03` migration.
- Task 8 remains incomplete.

### RESUMED — 2026-08-07 (Finding #3 fix + DB Migration Gate)

**Finding #3 (Important)** — `start_collection_backend.ps1` launcher secret validation:
- **Fixed:** Replaced raw PowerShell `.env` line-grep with Python `Settings().secret_key`
  validation so that process-level env overrides, quoted values, and dotenv inline comments
  are all handled by Pydantic (not PowerShell string parsing).
- **Tests:** `test_startup_refuses_public_secret_key_placeholder` (upgraded to real Python),
  `test_startup_refuses_process_env_placeholder_override` (new behavioral RED→GREEN).
- **Evidence:** 3/3 passed for startup tests; full suite 278 passed, 3 skipped.

**Commits:**
- `ccd4fef` — fix: enforce auth/IDOR, single-Muse ownership, session cleanup, and truthful health (Items 1–6)
- `4d1c75e` — fix: validate effective secret_key via Pydantic in collection launcher (Finding #3)

**DB Migration Gate (20260719_03):**
- Pre-migration schema-only backup created: `.superpowers/sdd/schema-before-20260719_03.sql` (nonempty, 20+ tables).
- Migration applied: `alembic upgrade 20260719_03` → `20260719_03 (head)`.
- Uniqueness constraint verified: `uq_collection_trials_session_randomized_order (session_id, randomized_order)` in `collection_trials`.
- Full backend suite with live MySQL: **278 passed, 3 skipped** in 36.17s.

- [x] Task 8: End-to-End Verification and Final Review — **COMPLETE**
  - All Critical and Important findings from final broad review addressed.
  - Alembic at `20260719_03 (head)`.
  - Backend 278 passed / 3 skipped (live MySQL).
  - Angular focused Karma 39/39 passed.



