# Muse and Trial Runner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the collection foundation into a recoverable Admin-only Muse 2 experiment runner with dual baselines, balanced randomized 12-Trial schedules, Backend-owned markers, atomic Raw EEG files, artifact events, and Valence/Arousal self-rating.

**Architecture:** A dedicated collection state machine owns session/Trial transitions and persists every boundary before the UI advances. A `MuseStreamSource` interface isolates the real local LSL/Muse adapter from deterministic tests; a separate Admin-authenticated collection WebSocket streams device/sensor/progress state without changing the ordinary comic EEG WebSocket. Raw data is written locally through an atomic CSV writer and only paths/checksums are stored in MySQL.

**Tech Stack:** FastAPI, SQLAlchemy 2, Alembic, MySQL 8, asyncio, pylsl/muselsl, CSV/SHA-256, pytest, Angular 19 standalone components, Signals, RxJS, Jasmine/Karma, HTML5 video.

## Global Constraints

- This is an entertainment and prototype-research workflow, not medical diagnosis or treatment.
- Collection endpoints and the new collection WebSocket are Admin-only.
- Do not change ordinary User EEG/comic endpoints or `/api/v1/sessions/ws/{session_id}`.
- Participant identity remains pseudonymous; Raw EEG paths contain participant codes, session IDs, and Trial IDs only.
- Muse EEG channel order is exactly `tp9,af7,af8,tp10`; expected sampling rate is 256 Hz.
- Baseline order is eyes-open 60 seconds followed by eyes-closed 60 seconds; each phase requires at least 30 accepted clean seconds.
- A schedule has exactly 12 approved stimuli: three from each of `positive_low`, `positive_high`, `negative_low`, `negative_high`.
- Trial order is randomized once, persisted, and never regenerated when a session resumes.
- Per Trial: rest/fixation 10–15 seconds, stimulus 45–60 seconds, rating Valence 1–9, Arousal 1–9, Confidence 1–5, then rest 20–30 seconds.
- Backend clock owns `rest_start`, `rest_end`, `stimulus_start`, `stimulus_end`, `rating_start`, and `rating_end` markers.
- Raw EEG files are local CSV files written atomically; MySQL stores only path, checksum, size, and metadata.
- Muse disconnect during an active baseline/Trial interrupts the active unit; it never marks it completed.
- Browser or Backend restart resumes only from committed state; an in-flight baseline/Trial becomes interrupted and must restart.
- All new Angular styles live in `.css` files; no inline `styles` metadata or style attributes.
- Preserve unrelated working-tree changes and stage only files named by each Task.

## File Structure

- Modify `backend/app/models/dataset_collection.py`: lifecycle enums and nullable in-progress Trial fields.
- Create `backend/alembic/versions/20260719_02_trial_runner.py`: lifecycle/schema migration after `20260717_01`.
- Create `backend/app/services/trial_scheduler.py`: balanced persisted schedule.
- Create `backend/app/services/raw_eeg_writer.py`: path-safe atomic CSV writer and checksum.
- Create `backend/app/services/collection_state_machine.py`: transition rules and recovery.
- Create `backend/app/services/muse_stream.py`: source protocol, LSL adapter, test fake.
- Create `backend/app/ws/collection_manager.py`: active collection runners and broadcast state.
- Modify `backend/app/schemas/dataset_collection.py`: preparation, baseline, Trial, artifact, rating and runner-state contracts.
- Modify `backend/app/routers/dataset_collection.py`: collection HTTP commands and WebSocket.
- Modify `backend/app/config.py`: collection timing/path/quality settings.
- Modify `frontend/src/app/core/services/dataset-collection.service.ts`: runner HTTP DTOs/methods.
- Create `frontend/src/app/core/services/dataset-collection-ws.service.ts`: collection WebSocket state.
- Create `frontend/src/app/features/dataset-collection-runner/`: Admin Trial Runner component/spec/CSS.
- Modify `frontend/src/app/app.routes.ts`: guarded runner route.
- Modify `frontend/src/app/features/dataset-collection/dataset-collection.component.ts`: Start/Resume link.

---

### Task 1: Persisted Collection Lifecycle Schema

**Files:**

- Modify: `backend/app/models/dataset_collection.py`
- Create: `backend/alembic/versions/20260719_02_trial_runner.py`
- Create: `backend/tests/test_trial_runner_models.py`

**Interfaces:**

- Produces `BaselineKind = eyes_open | eyes_closed`.
- Produces `TrialState = scheduled | rest | stimulus | rating | completed | interrupted | failed`.
- Extends `CollectionSession` with baseline clean/wall-clock seconds, active baseline, current Trial ID, interruption reason, and recovery timestamp.
- Extends `CollectionTrial` so schedule rows can exist before ratings/files and persist lifecycle/marker/QC data.

- [ ] **Step 1: Write failing metadata tests**

```python
def test_trial_can_be_scheduled_without_rating_or_file():
    assert CollectionTrial.__table__.c.valence_rating.nullable is True
    assert CollectionTrial.__table__.c.arousal_rating.nullable is True
    assert CollectionTrial.__table__.c.confidence.nullable is True
    assert CollectionTrial.__table__.c.eeg_file_path.nullable is True
    assert CollectionTrial.__table__.c.eeg_checksum.nullable is True


def test_trial_lifecycle_columns_exist():
    columns = CollectionTrial.__table__.columns
    assert columns["state"].nullable is False
    assert {"rest_started_at", "stimulus_started_at", "rating_started_at", "failure_reason", "raw_size_bytes"} <= set(columns.keys())
```

Assert exact enum values and session dual-baseline progress columns.

- [ ] **Step 2: Run RED**

```powershell
cd backend
& '.\.venv\Scripts\python.exe' -m pytest tests/test_trial_runner_models.py -q
```

Expected: missing enum/column failures.

- [ ] **Step 3: Implement lifecycle fields**

Required additions:

```python
class BaselineKind(str, enum.Enum):
    eyes_open = "eyes_open"
    eyes_closed = "eyes_closed"


class TrialState(str, enum.Enum):
    scheduled = "scheduled"
    rest = "rest"
    stimulus = "stimulus"
    rating = "rating"
    completed = "completed"
    interrupted = "interrupted"
    failed = "failed"
```

`CollectionTrial.valence_rating`, `arousal_rating`, `confidence`, `eeg_file_path`, and `eeg_checksum` become nullable. Add `state`, `rest_started_at`, `stimulus_started_at`, `rating_started_at`, `failure_reason`, `raw_size_bytes`, `accepted_clean_seconds`, and `wall_clock_seconds`. Keep rating check constraints: SQL permits NULL and validates present values.

- [ ] **Step 4: Implement migration `20260719_02`**

Set `down_revision = "20260717_01"`. Alter the five in-progress fields nullable and add the lifecycle/progress columns and indexes. `downgrade()` must fail with a clear guard if incomplete Trial rows contain NULL ratings/files; otherwise restore the original constraints.

- [ ] **Step 5: Verify tests and offline SQL**

Run model tests and `alembic upgrade head --sql`; assert the range upgrades `20260717_01 -> 20260719_02` and does not alter ordinary EEG tables.

- [ ] **Step 6: Commit**

```powershell
git add -- backend/app/models/dataset_collection.py backend/alembic/versions/20260719_02_trial_runner.py backend/tests/test_trial_runner_models.py
git commit -m "feat: add collection trial lifecycle"
```

---

### Task 2: Balanced Schedule Creation

**Files:**

- Create: `backend/app/services/trial_scheduler.py`
- Create: `backend/tests/test_trial_scheduler.py`
- Modify: `backend/app/services/dataset_collection_service.py`

**Interfaces:**

- Produces `create_trial_schedule(db: Session, session: CollectionSession, *, seed: int | None = None) -> list[CollectionTrial]`.
- Produces `ScheduleUnavailableError` with safe details.
- Consumes only approved stimuli and persists exactly 12 `scheduled` rows.

- [ ] **Step 1: Write failing scheduler tests**

Cover exactly three stimuli per quadrant, orders 1–12 without duplicates, deterministic order with explicit seed, different persisted sessions retaining their first schedule, rejection when a quadrant has fewer than three approved stimuli, retired/draft exclusion, and rollback on bulk insert failure.

- [ ] **Step 2: Run RED**

Expected: module import failure.

- [ ] **Step 3: Implement minimal scheduler**

```python
REQUIRED_PER_QUADRANT = 3
TOTAL_TRIALS = 12

def create_trial_schedule(db, session, *, seed=None):
    existing = list(db.scalars(select(CollectionTrial).where(CollectionTrial.session_id == session.id).order_by(CollectionTrial.randomized_order)))
    if existing:
        return existing
    rng = random.Random(seed) if seed is not None else secrets.SystemRandom()
    selected = []
    for quadrant in Quadrant:
        candidates = list(db.scalars(select(EmotionStimulus).where(
            EmotionStimulus.target_quadrant == quadrant,
            EmotionStimulus.approval_state == StimulusApprovalState.approved,
        )))
        if len(candidates) < REQUIRED_PER_QUADRANT:
            raise ScheduleUnavailableError(f"At least 3 approved stimuli required for {quadrant.value}")
        selected.extend(rng.sample(candidates, REQUIRED_PER_QUADRANT))
    rng.shuffle(selected)
    # persist order 1..12 and session.total_trials=12 in one transaction
```

- [ ] **Step 4: Integrate schedule creation with session service**

Session creation remains `preparation`; schedule generation is explicit after device selection so Admin can correct stimulus inventory before starting.

- [ ] **Step 5: Verify and commit**

Run focused and full backend tests, then commit the three files with `feat: create balanced trial schedules`.

---

### Task 3: Atomic Raw EEG Writer

**Files:**

- Create: `backend/app/services/raw_eeg_writer.py`
- Modify: `backend/app/config.py`
- Create: `backend/tests/test_raw_eeg_writer.py`

**Interfaces:**

- Produces `EEGSample(timestamp, tp9, af7, af8, tp10, tp9_quality, af7_quality, af8_quality, tp10_quality, marker)`.
- Produces `AtomicEEGWriter.start(path_parts)`, `append(sample)`, `mark(marker)`, `finalize() -> RawFileResult`, and `abort()`.
- `RawFileResult` contains relative path, SHA-256 checksum, byte size, row count, first/last timestamp.

- [ ] **Step 1: Write failing file-contract tests**

Use `tmp_path`. Assert exact header order, UTF-8/newline-stable CSV, monotonic timestamps, marker rows, SHA-256 equality, `.partial` during capture, atomic rename at finalize, partial deletion at abort, duplicate finalize rejection, and rejection of `..`, absolute paths, separators, participant names/emails, or paths escaping `collection_raw_dir`.

- [ ] **Step 2: Run RED**

Expected: writer import failure.

- [ ] **Step 3: Add collection settings**

```python
collection_raw_dir: str = "./collection_data"
collection_stimulus_dir: str = "./collection_stimuli"
collection_sampling_rate_hz: int = 256
collection_sampling_tolerance_hz: int = 8
collection_baseline_wall_seconds: int = 60
collection_baseline_min_clean_seconds: int = 30
collection_rest_min_seconds: int = 10
collection_rest_max_seconds: int = 15
```

- [ ] **Step 4: Implement writer**

Resolve the root and destination, verify `destination.is_relative_to(root)`, write only to `<name>.partial`, flush/fsync before `os.replace`, and compute checksum from finalized bytes. Backend time is injected for deterministic tests; the writer does not trust browser timestamps.

- [ ] **Step 5: Verify and commit**

Run focused writer tests and commit with `feat: write collection EEG atomically`.

---

### Task 4: Recoverable Collection State Machine

**Files:**

- Create: `backend/app/services/collection_state_machine.py`
- Create: `backend/tests/test_collection_state_machine.py`

**Interfaces:**

- Produces commands `select_device`, `start_baseline`, `accept_sample`, `finish_baseline`, `start_trial_rest`, `start_stimulus`, `mark_artifact`, `finish_stimulus`, `submit_rating`, `interrupt`, and `resume`.
- Produces `CollectionRunnerState` DTO independent from FastAPI/WebSocket.
- Consumes Task 2 scheduler, Task 3 writer, Task 1/2 ORM, and `derive_labels`.

- [ ] **Step 1: Write state-transition tests**

Test this exact happy path:

```text
preparation -> baseline(eyes_open) -> baseline(eyes_closed) -> ready
-> Trial 1 rest -> stimulus -> rating -> completed
-> Trial 2 rest
```

Also cover invalid transition rejection, four-sensor quality gate, accepted time pausing while poor/stale, Baseline requiring 60 wall seconds and at least 30 clean seconds, writer finalize before DB completion, artifact persistence, rating/derived-label persistence, six-Trial break flag, session completion after Trial 12, Muse disconnect interruption, restart recovery converting in-flight states to interrupted, and resuming at the same randomized order without regenerating schedule.

- [ ] **Step 2: Run RED**

Expected: state-machine import failure.

- [ ] **Step 3: Implement explicit transition table**

Use one transaction per boundary. Sample ingestion writes Raw rows and updates in-memory counters but does not commit per sample. Marker methods use injected Backend monotonic/wall clocks and persist marker times at phase boundaries.

- [ ] **Step 4: Implement failure ordering**

- Finalize Raw file first, then persist path/checksum/size and state.
- If DB commit fails after finalize, retain the file and mark recovery metadata; never claim completion to clients.
- If file finalize fails, rollback Trial completion and mark failed.
- `interrupt()` aborts partial writer and persists reason.

- [ ] **Step 5: Verify and commit**

Run focused/full backend tests and commit with `feat: orchestrate collection trial state`.

---

### Task 5: Muse Stream Adapter and Admin Collection WebSocket

**Files:**

- Create: `backend/app/services/muse_stream.py`
- Create: `backend/app/ws/collection_manager.py`
- Modify: `backend/app/schemas/dataset_collection.py`
- Modify: `backend/app/routers/dataset_collection.py`
- Create: `backend/tests/test_collection_runner_api.py`

**Interfaces:**

- Produces `MuseStreamSource` protocol: `discover()`, `connect(device_id)`, `samples()` async iterator, `disconnect()`.
- Produces `LSLMuseStreamSource` which maps LSL channel data exactly to TP9/AF7/AF8/TP10.
- Produces HTTP runner commands under `/api/v1/admin/dataset-collection/sessions/{id}`.
- Produces Admin-only stimulus media response `GET /api/v1/admin/dataset-collection/stimuli/{stimulus_id}/media`.
- Produces Admin-authenticated WebSocket `/api/v1/admin/dataset-collection/ws/{session_id}?token=...`.

- [ ] **Step 1: Write failing adapter/API/auth tests**

Use a fake stream. Cover channel mapping, discovery/connect failure, stale timestamps, command/state serialization, Admin JWT acceptance, missing token close code 4401, User token close code 4403, wrong/nonexistent session, session ownership not relevant because Admin-only, disconnect interruption, and no changes to the ordinary EEG WebSocket route.

Also test that stimulus media paths are resolved under `collection_stimulus_dir`, missing/checksum-mismatched files fail closed, traversal/absolute escape is rejected, User receives 403, and Admin receives the expected video content type without exposing the filesystem path in JSON.

- [ ] **Step 2: Run RED**

Expected: missing adapter/route failures.

- [ ] **Step 3: Add typed command schemas**

Requests:

- `POST /schedule`
- `POST /device` with `device_id`, `device_name`
- `POST /baseline/{eyes_open|eyes_closed}/start`
- `POST /trials/{trial_id}/rest/start`
- `POST /trials/{trial_id}/stimulus/start`
- `POST /trials/{trial_id}/artifacts`
- `POST /trials/{trial_id}/stimulus/finish`
- `POST /trials/{trial_id}/rating`
- `POST /interrupt`
- `POST /resume`
- `GET /runner-state`

Remove the unused Foundation `CollectionOverviewResponse` with `participant_count/stimulus_count/session_count`; retain the router/TypeScript runtime overview contract (`participants/sessions/trials/review_counts/quadrant_counts`) as the single definition.

Every HTTP handler uses `AdminUser`, validates that Trial belongs to Session, and delegates transitions to the state machine.

The stimulus media endpoint uses `FileResponse` only after root containment and SHA-256 verification against `EmotionStimulus.checksum`. It is fetched as an authenticated Blob by Angular; never place the local `file_path` directly in a browser `<video src>`.

- [ ] **Step 4: Implement WebSocket auth and lifecycle**

Decode query token with existing JWT settings, load the User, require active Admin role before `accept()`, then attach to `collection_manager`. Do not reuse or modify the ordinary `eeg_websocket` function.

- [ ] **Step 5: Implement local LSL adapter safely**

Move blocking LSL discovery/pull operations to `asyncio.to_thread`; expose cancellation and bounded timeouts. Tests never require physical Muse hardware.

- [ ] **Step 6: Verify and commit**

Run collection runner API/WebSocket tests, existing auth/role tests, and source check confirming ordinary WebSocket unchanged. Commit with `feat: stream Muse collection sessions`.

---

### Task 6: Angular Runner API and WebSocket Clients

**Files:**

- Modify: `frontend/src/app/core/services/dataset-collection.service.ts`
- Modify: `frontend/src/app/core/services/dataset-collection.service.spec.ts`
- Create: `frontend/src/app/core/services/dataset-collection-ws.service.ts`
- Create: `frontend/src/app/core/services/dataset-collection-ws.service.spec.ts`

**Interfaces:**

- Produces typed HTTP methods matching every Task 5 command.
- Produces `getStimulusMedia(stimulusId: number): Observable<Blob>` using authenticated `HttpClient`.
- Produces `DatasetCollectionWsService.connect(sessionId)`, `disconnect()`, `state`, `isConnected`, and no automatic command execution.
- Reconnects only when not explicitly disconnected and requests `runner-state` after reconnect.

- [ ] **Step 1: Write failing HTTP and WebSocket tests**

Assert exact URLs/methods/bodies, encoded JWT query, message parsing, invalid JSON rejection, sequence monotonicity, explicit disconnect cancelling reconnect, unexpected close scheduling one reconnect, and service destruction cleanup.

Assert media requests use `responseType: 'blob'`, emit the Blob unchanged, and do not expose the local stimulus path.

- [ ] **Step 2: Run RED**

Expected: missing methods/module failures.

- [ ] **Step 3: Implement DTOs and HTTP methods**

Types mirror Pydantic fields exactly. `RatingRequest` is `{ valence: number; arousal: number; confidence: number }`; browser sends no label or marker timestamp.

- [ ] **Step 4: Implement collection WebSocket client**

Follow the existing EEG WebSocket style but keep separate state and URL. Reject messages whose `sequence` is not greater than the latest accepted sequence.

- [ ] **Step 5: Verify and commit**

Run focused Karma with a committed Plan-2 spec config, TypeScript compilation, and commit with `feat: add collection runner clients`.

---

### Task 7: Admin Trial Runner UI

**Files:**

- Create: `frontend/src/app/features/dataset-collection-runner/dataset-collection-runner.component.ts`
- Create: `frontend/src/app/features/dataset-collection-runner/dataset-collection-runner.component.css`
- Create: `frontend/src/app/features/dataset-collection-runner/dataset-collection-runner.component.spec.ts`
- Modify: `frontend/src/app/app.routes.ts`
- Modify: `frontend/src/app/features/dataset-collection/dataset-collection.component.ts`
- Modify: `frontend/tsconfig.dataset-collection.spec.json`

**Interfaces:**

- Produces guarded route `/admin/dataset-collection/sessions/:id/run` with `[authGuard, adminGuard]`.
- Consumes Task 6 clients and shared `HorseshoeSensorComponent`.
- Renders stages `device`, `eyes_open`, `eyes_closed`, `ready`, `rest`, `stimulus`, `rating`, `break`, `completed`, `interrupted`, `failed`.

- [ ] **Step 1: Write failing component tests**

Cover:

- route Session ID loading and Admin guards;
- Creative Headset Setup sensor visualization and device selection;
- baseline order cannot be skipped and shows 60-second wall/30-second clean targets;
- authenticated media Blob becomes a revocable object URL; load error prevents stimulus start and teardown revokes the URL;
- stimulus playback emits start only after `playing`, finish once on `ended`, and never sends browser marker timestamps;
- artifact buttons send event type/note only during stimulus;
- rating inputs enforce 1–9/1–9/1–5 and exact request body;
- progress shows Trial N/12 and break after Trial 6;
- refresh renders persisted `runner-state`, never creates a new schedule;
- interrupted Trial offers restart of the same order;
- emergency stop requires confirmation and calls interrupt;
- non-medical entertainment notice visible;
- external CSS, 44px controls, focus-visible, responsive layout and accessible status/labels.

- [ ] **Step 2: Run RED**

Expected: component import failure.

- [ ] **Step 3: Implement state-driven template**

Use `@switch (runnerState().stage)` and no client-side phase advancement before successful Backend response/state message. Fetch the approved stimulus through `getStimulusMedia()`, create a temporary object URL for `<video src>`, and revoke it on Trial change/destroy. Show title/order but never expose the local `file_path` or target quadrant during collection to avoid path disclosure and operator bias.

- [ ] **Step 4: Add Start/Resume navigation from Foundation UI**

Session rows link to the runner. `preparation`, `baseline`, `ready`, `in_progress`, and `interrupted` show Start/Resume; completed sessions show View summary only.

- [ ] **Step 5: Implement external CSS and verify**

Run focused component/client Karma, source metadata check, app type-check, and development build.

- [ ] **Step 6: Commit**

Commit the six scoped files with `feat: add Admin EEG trial runner`.

---

### Task 8: Plan 2 End-to-End Verification and Review

**Files:** No planned production changes.

- [ ] **Step 1: Back up schema and apply migration**

Create a nonempty schema-only MySQL backup before `alembic upgrade head`. Confirm current revision becomes `20260719_02` and all lifecycle columns match ORM nullability/enums.

- [ ] **Step 2: Run backend suites**

Run all Plan-2 model/scheduler/writer/state/runner API tests plus existing collection/auth/role tests. Hardware-independent tests must pass without Muse connected.

- [ ] **Step 3: Run frontend suites and build**

Run the committed focused Karma config for Foundation + Runner clients/components, `tsc -p tsconfig.app.json --noEmit`, source metadata scans, and Angular development build.

- [ ] **Step 4: Run recovery contract checks**

Using fake Muse samples, exercise dual baseline, Trial 1 completion, interruption during Trial 2, process recreation, resume at Trial 2, and verify Trial 1 CSV checksum/path still match DB.

- [ ] **Step 5: Verify scope and privacy**

Confirm ordinary EEG/WebSocket files are unchanged, Raw paths contain no PII, target quadrant is not rendered in Runner, all collection endpoints/WS reject User accounts, and no BLOB columns/files enter MySQL.

- [ ] **Step 6: Broad review**

Review the complete Plan-2 diff against the approved design spec. Fix all Critical and Important findings with failing regression tests, then rerun the full verification set.
