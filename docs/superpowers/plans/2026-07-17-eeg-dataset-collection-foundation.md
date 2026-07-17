# EEG Dataset Collection Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first independently usable increment of the EEG dataset system: versioned database tables, label/QC domain rules, Admin APIs, and Admin screens for dataset overview, stimuli, participants, and collection-session creation.

**Architecture:** Collection data lives in new SQLAlchemy models separate from ordinary comic-generation `EEGSession` records. A dedicated `/admin/dataset-collection` router exposes typed Admin-only APIs; Angular consumes them through a focused service and lazy-loaded feature. Muse streaming, Trial playback, Raw EEG writing, QC review/export, model training, and comic integration are intentionally reserved for later plans.

**Tech Stack:** FastAPI, SQLAlchemy 2, Alembic, MySQL 8, Pydantic 2, pytest, Angular 19 standalone components, Signals, RxJS, Jasmine/Karma.

## Global Constraints

- This system is for entertainment and prototype research, not medical diagnosis or treatment.
- Supported participant identifiers are pseudonymous codes such as `P001`; do not store names, email addresses, or phone numbers in collection tables.
- Supported quadrants are exactly `positive_low`, `positive_high`, `negative_low`, and `negative_high`.
- Valence/Arousal scores are integers from 1 through 9; Confidence is an integer from 1 through 5.
- Score 5 is ambiguous for its axis. Confidence below 3 invalidates both training labels.
- Collection, review, export, and stimulus administration remain Admin-only.
- Do not modify ordinary User EEG/comic endpoints or the EEG WebSocket contract.
- Raw EEG and stimulus media are file references with checksums; never store binary data in MySQL.
- All new Angular component CSS must be in `.css` files, not inline `styles` metadata.
- Preserve unrelated working-tree changes and stage only the files named by each task.

## Delivery Roadmap

This plan is Plan 1 of 4:

1. **Collection Foundation (this plan):** schema, domain rules, Admin APIs, overview/participant/stimulus UI
2. **Muse and Trial Runner:** device quality, dual baseline, randomized Trial state machine, markers, Raw EEG writer, self-rating
3. **QC Review and Export:** artifact review, accept/reject, withdrawal, immutable dataset manifests, CSV/Parquet export
4. **ML and Comic Integration:** preprocessing, grouped evaluation, model registry, inference, rule-based fallback

## File Structure

- Create `backend/app/models/dataset_collection.py`: collection enums and ORM entities.
- Modify `backend/app/models/__init__.py`: import collection models for metadata discovery.
- Create `backend/alembic.ini`, `backend/alembic/env.py`, `backend/alembic/script.py.mako`: migration runtime.
- Create `backend/alembic/versions/20260717_01_collection_foundation.py`: new tables and indexes only.
- Create `backend/app/services/dataset_labels.py`: pure label derivation.
- Create `backend/app/services/dataset_collection_service.py`: participant-code allocation and session/stimulus operations.
- Create `backend/app/schemas/dataset_collection.py`: request/response contracts.
- Create `backend/app/routers/dataset_collection.py`: Admin-only endpoints.
- Modify `backend/app/main.py`: register the collection router.
- Create focused backend tests under `backend/tests/`.
- Create `frontend/src/app/core/services/dataset-collection.service.ts`: typed API client.
- Create `frontend/src/app/features/dataset-collection/` components/specs/styles.
- Modify `frontend/src/app/app.routes.ts`: Admin-only lazy route.
- Modify `frontend/src/app/features/admin/admin.component.ts`: link to the new feature, not duplicate its UI.

---

### Task 1: Collection ORM and Versioned Migration

**Files:**

- Create: `backend/app/models/dataset_collection.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/script.py.mako`
- Create: `backend/alembic/versions/20260717_01_collection_foundation.py`
- Create: `backend/tests/test_dataset_collection_models.py`

**Interfaces:**

- Produces enums `Quadrant`, `ParticipantState`, `StimulusApprovalState`, `CollectionSessionState`, and `ReviewState`.
- Produces models `DatasetParticipant`, `EmotionStimulus`, `CollectionSession`, `CollectionTrial`, `ArtifactEvent`, `DatasetVersion`, and `ModelVersion`.
- Preserves all existing `EEGSession`, `MLTrainingSample`, and comic-generation tables.

- [ ] **Step 1: Write failing ORM metadata tests**

Create tests that import the seven models, assert their exact table names, assert `DatasetParticipant.participant_code` and `EmotionStimulus.checksum` are unique, and assert collection tables contain no columns named `name`, `email`, `phone`, or `password`.

```python
from app.models.dataset_collection import DatasetParticipant, EmotionStimulus


def test_collection_identity_is_pseudonymous():
    columns = set(DatasetParticipant.__table__.columns.keys())
    assert "participant_code" in columns
    assert {"name", "email", "phone", "password"}.isdisjoint(columns)
    assert DatasetParticipant.__table__.c.participant_code.unique is True


def test_stimulus_checksum_is_unique():
    assert EmotionStimulus.__table__.c.checksum.unique is True
```

- [ ] **Step 2: Run the tests and verify RED**

Run from `backend`:

```powershell
& '.\.venv\Scripts\python.exe' -m pytest tests/test_dataset_collection_models.py -q
```

Expected: collection fails because `app.models.dataset_collection` does not exist.

- [ ] **Step 3: Implement collection enums and models**

Use SQLAlchemy 2 `Mapped` fields. Required minimum fields:

```python
class Quadrant(str, enum.Enum):
    positive_low = "positive_low"
    positive_high = "positive_high"
    negative_low = "negative_low"
    negative_high = "negative_high"


class ParticipantState(str, enum.Enum):
    active = "active"
    withdrawn = "withdrawn"


class StimulusApprovalState(str, enum.Enum):
    draft = "draft"
    approved = "approved"
    retired = "retired"


class CollectionSessionState(str, enum.Enum):
    preparation = "preparation"
    baseline = "baseline"
    ready = "ready"
    in_progress = "in_progress"
    completed = "completed"
    interrupted = "interrupted"
    withdrawn = "withdrawn"
    failed = "failed"


class ReviewState(str, enum.Enum):
    pending = "pending"
    accepted = "accepted"
    rejected = "rejected"


class DatasetParticipant(Base):
    __tablename__ = "dataset_participants"
    id: Mapped[int] = mapped_column(primary_key=True)
    participant_code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    consent_confirmed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    state: Mapped[ParticipantState] = mapped_column(Enum(ParticipantState), default=ParticipantState.active)
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class EmotionStimulus(Base):
    __tablename__ = "emotion_stimuli"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(150))
    file_path: Mapped[str] = mapped_column(String(500))
    checksum: Mapped[str] = mapped_column(String(64), unique=True)
    duration_seconds: Mapped[float] = mapped_column(Float)
    target_quadrant: Mapped[Quadrant] = mapped_column(Enum(Quadrant), index=True)
    approval_state: Mapped[StimulusApprovalState] = mapped_column(Enum(StimulusApprovalState))
    stimulus_set_version: Mapped[str] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
```

`CollectionSession` references a participant and stores device identity, two baseline paths/checksums, progress, state, and timestamps. `CollectionTrial` references session/stimulus and stores randomized order, ratings, derived labels, validity flags, QC summary, file path/checksum, and review state. `ArtifactEvent` references a Trial. `DatasetVersion` and `ModelVersion` store immutable manifest/artifact metadata as JSON text plus checksums and versions.

- [ ] **Step 4: Add Alembic runtime and migration**

Configure Alembic to read `get_settings().database_url` and import `Base.metadata`. Migration `upgrade()` creates only the seven collection tables and their foreign-key/index constraints. `downgrade()` drops them in reverse dependency order. Do not include existing tables in the migration.

- [ ] **Step 5: Verify models, migration SQL, and existing metadata**

```powershell
& '.\.venv\Scripts\python.exe' -m pytest tests/test_dataset_collection_models.py -q
& '.\.venv\Scripts\alembic.exe' upgrade head --sql | Select-String 'dataset_participants|emotion_stimuli|collection_sessions|collection_trials'
```

Expected: tests pass and offline SQL contains the four core tables without `DROP TABLE users` or changes to existing EEG tables.

- [ ] **Step 6: Commit the schema foundation**

```powershell
git add -- backend/app/models/dataset_collection.py backend/app/models/__init__.py backend/alembic.ini backend/alembic/env.py backend/alembic/script.py.mako backend/alembic/versions/20260717_01_collection_foundation.py backend/tests/test_dataset_collection_models.py
git commit -m "feat: add EEG collection schema"
```

---

### Task 2: Label Derivation and Foundation Validation

**Files:**

- Create: `backend/app/services/dataset_labels.py`
- Create: `backend/tests/test_dataset_labels.py`

**Interfaces:**

- Produces `AxisLabel = Literal["negative", "positive", "low", "high"]`.
- Produces immutable `DerivedLabels` with `valence_label`, `arousal_label`, `valid_valence_label`, `valid_arousal_label`.
- Produces `derive_labels(valence: int, arousal: int, confidence: int) -> DerivedLabels`.

- [ ] **Step 1: Write the label boundary tests**

```python
import pytest
from pydantic import ValidationError

from app.services.dataset_labels import derive_labels


@pytest.mark.parametrize("score,label", [(1, "negative"), (4, "negative"), (6, "positive"), (9, "positive")])
def test_valence_boundaries(score, label):
    result = derive_labels(score, 6, 5)
    assert result.valence_label == label
    assert result.valid_valence_label is True


def test_score_five_invalidates_only_its_axis():
    result = derive_labels(5, 8, 5)
    assert result.valence_label is None
    assert result.valid_valence_label is False
    assert result.arousal_label == "high"
    assert result.valid_arousal_label is True


def test_low_confidence_invalidates_both_axes():
    result = derive_labels(8, 8, 2)
    assert result.valid_valence_label is False
    assert result.valid_arousal_label is False
```

Add parameterized rejection tests for scores outside 1–9 and Confidence outside 1–5.

- [ ] **Step 2: Run tests and verify RED**

Expected: import failure for `dataset_labels`.

- [ ] **Step 3: Implement the pure label service**

Use a frozen Pydantic model so invalid ranges fail consistently:

```python
class RatingInput(BaseModel):
    valence: int = Field(ge=1, le=9)
    arousal: int = Field(ge=1, le=9)
    confidence: int = Field(ge=1, le=5)


def derive_labels(valence: int, arousal: int, confidence: int) -> DerivedLabels:
    rating = RatingInput(valence=valence, arousal=arousal, confidence=confidence)
    confident = rating.confidence >= 3
    return DerivedLabels(
        valence_label=None if rating.valence == 5 else ("negative" if rating.valence <= 4 else "positive"),
        arousal_label=None if rating.arousal == 5 else ("low" if rating.arousal <= 4 else "high"),
        valid_valence_label=confident and rating.valence != 5,
        valid_arousal_label=confident and rating.arousal != 5,
    )
```

- [ ] **Step 4: Run focused tests and commit**

```powershell
& '.\.venv\Scripts\python.exe' -m pytest tests/test_dataset_labels.py -q
git add -- backend/app/services/dataset_labels.py backend/tests/test_dataset_labels.py
git commit -m "feat: define EEG dataset label rules"
```

---

### Task 3: Admin Collection Schemas and Service Layer

**Files:**

- Create: `backend/app/schemas/dataset_collection.py`
- Create: `backend/app/services/dataset_collection_service.py`
- Create: `backend/tests/test_dataset_collection_service.py`

**Interfaces:**

- Produces `allocate_participant_code(db: Session) -> str` using `P` plus a zero-padded integer.
- Produces `create_participant(db, consent_confirmed_at) -> DatasetParticipant` with retry on unique collision.
- Produces `create_stimulus(db, body: StimulusCreate) -> EmotionStimulus`.
- Produces `create_collection_session(db, participant_id: int, device_id: str | None, device_name: str | None) -> CollectionSession`.
- Produces Pydantic contracts for overview, participant, stimulus, and session create/list responses.

- [ ] **Step 1: Write service tests against an isolated SQLite database**

Cover:

- first participant is `P001`, next is `P002`;
- participant creation stores no identifying fields;
- duplicate stimulus checksum raises a domain conflict;
- stimulus duration below 45 or above 60 fails schema validation;
- collection session rejects withdrawn participant;
- collection session begins at `preparation` with progress zero.

- [ ] **Step 2: Verify RED**

Expected: service/schema import failures.

- [ ] **Step 3: Implement typed schemas**

Use `ConfigDict(from_attributes=True)` for response models. `StimulusCreate.duration_seconds` is `Field(ge=45, le=60)`. `CollectionSessionCreate` accepts `participant_id`, optional `device_id`, and optional `device_name`. No participant request contains PII fields.

- [ ] **Step 4: Implement service transactions**

Participant allocation queries the largest numeric suffix, then inserts inside a transaction. Translate `IntegrityError` for participant-code/checksum conflicts to domain exceptions; never expose SQL strings to the router.

- [ ] **Step 5: Run service tests and commit**

```powershell
& '.\.venv\Scripts\python.exe' -m pytest tests/test_dataset_collection_service.py -q
git add -- backend/app/schemas/dataset_collection.py backend/app/services/dataset_collection_service.py backend/tests/test_dataset_collection_service.py
git commit -m "feat: add collection domain services"
```

---

### Task 4: Admin Dataset Collection API

**Files:**

- Create: `backend/app/routers/dataset_collection.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_dataset_collection_api.py`

**Interfaces:**

- Produces Admin-only endpoints under `/api/v1/admin/dataset-collection`:
  - `GET /overview`
  - `GET|POST /participants`
  - `GET|POST /stimuli`
  - `GET /sessions`
  - `POST /sessions`
- Consumes Task 3 schemas/services and existing `AdminUser` dependency.

- [ ] **Step 1: Write failing API authorization and contract tests**

Override `get_db` and `require_admin` in a FastAPI test app. Assert:

- unauthenticated requests return 401;
- User-role requests return 403;
- Admin can create/list participants without PII in JSON;
- Admin can create/list 45–60 second stimuli;
- duplicate checksum returns 409;
- overview returns participant/session/trial/review/quadrant counts with zero defaults;
- Admin can create a preparation session for an active participant.

- [ ] **Step 2: Run tests and verify RED**

Expected: router import or 404 failures.

- [ ] **Step 3: Implement the focused router**

Every handler receives `admin: AdminUser`. Convert domain not-found to 404 and conflicts to 409. Use response models; never return ORM `__dict__`.

Overview response shape:

```json
{
  "participants": 0,
  "sessions": 0,
  "trials": 0,
  "review_counts": {"pending": 0, "accepted": 0, "rejected": 0},
  "quadrant_counts": {"positive_low": 0, "positive_high": 0, "negative_low": 0, "negative_high": 0}
}
```

- [ ] **Step 4: Register the router and verify API tests**

```python
app.include_router(dataset_collection.router, prefix="/api/v1")
```

Run the focused tests and existing role tests.

- [ ] **Step 5: Commit the API**

```powershell
git add -- backend/app/routers/dataset_collection.py backend/app/main.py backend/tests/test_dataset_collection_api.py
git commit -m "feat: expose admin collection APIs"
```

---

### Task 5: Angular Collection API Client and Admin Route

**Files:**

- Create: `frontend/src/app/core/services/dataset-collection.service.ts`
- Create: `frontend/src/app/core/services/dataset-collection.service.spec.ts`
- Modify: `frontend/src/app/app.routes.ts`
- Modify: `frontend/src/app/features/admin/admin.component.ts`

**Interfaces:**

- Produces TypeScript types `CollectionOverview`, `DatasetParticipant`, `EmotionStimulus`, `CollectionSession`.
- Produces service methods `getOverview`, `listParticipants`, `createParticipant`, `listStimuli`, `createStimulus`, `listSessions`, `createSession`.
- Produces Admin-only route `/admin/dataset-collection` using `[authGuard, adminGuard]`.

- [ ] **Step 1: Write failing HTTP client tests**

Use `HttpTestingController` to assert exact URLs, methods, and request bodies. Participant creation sends only `consent_confirmed_at`; stimulus creation sends title, file path, checksum, duration, quadrant, approval state, and version.

- [ ] **Step 2: Verify RED and implement the client**

Use a single base URL:

```ts
private readonly baseUrl = `${environment.apiUrl}/admin/dataset-collection`;
```

Return typed `Observable` values without subscribing inside the service.

- [ ] **Step 3: Add the lazy Admin route and navigation link**

```ts
{
  path: 'admin/dataset-collection',
  canActivate: [authGuard, adminGuard],
  loadComponent: () => import('./features/dataset-collection/dataset-collection.component')
    .then(m => m.DatasetCollectionComponent),
}
```

Replace the old Admin Dataset tab's direct sample table entry point with a clear link button to `/admin/dataset-collection`; keep existing stats/users behavior unchanged.

- [ ] **Step 4: Run focused compilation and commit**

Run the service spec if Karma compiles; otherwise record the known `app.component.spec.ts:20` blocker and run focused TypeScript compilation. Commit only the four scoped files.

---

### Task 6: Dataset Collection Foundation UI

**Files:**

- Create: `frontend/src/app/features/dataset-collection/dataset-collection.component.ts`
- Create: `frontend/src/app/features/dataset-collection/dataset-collection.component.css`
- Create: `frontend/src/app/features/dataset-collection/dataset-collection.component.spec.ts`

**Interfaces:**

- Consumes Task 5 `DatasetCollectionService`.
- Provides tabs `overview`, `participants`, `stimuli`, and `sessions` inside the feature.
- Provides participant registration, stimulus registration, and collection-session creation; no Muse or Trial recording controls yet.

- [ ] **Step 1: Write failing component tests**

Assert:

- overview loads and renders counts;
- participant form contains no name/email/phone fields;
- consent is required before submit;
- stimulus duration validation accepts 45 and 60, rejects 44 and 61;
- four exact quadrant options render;
- start-session action requires an active participant;
- entertainment/non-medical notice is visible;
- every component style comes from `styleUrl`.

- [ ] **Step 2: Verify RED**

Expected: component import failure.

- [ ] **Step 3: Implement the standalone feature**

Use `CommonModule`, `FormsModule`, `RouterLink`, Signals, and the API client. Keep the visual language consistent with the existing dark navy/purple Admin product. Forms show server errors and disable duplicate submissions. Display `P001`-style code only; do not ask for PII.

- [ ] **Step 4: Implement external responsive CSS**

Use a maximum content width of 1200px, responsive stat cards, accessible labels, `:focus-visible`, 44px minimum controls, and no inline styles or Angular `styles` array.

- [ ] **Step 5: Run focused checks and commit**

Run component/service specs where Karma permits, focused spec compilation, app type-check, and Angular development build. Commit the three component files plus any Task 5 files not already committed.

---

### Task 7: Foundation Verification and Review

**Files:** No planned production changes.

- [ ] **Step 1: Run backend suites**

```powershell
cd backend
& '.\.venv\Scripts\python.exe' -m pytest tests/test_dataset_collection_models.py tests/test_dataset_labels.py tests/test_dataset_collection_service.py tests/test_dataset_collection_api.py tests/test_role_dependencies.py -q
```

- [ ] **Step 2: Verify migration safety**

Generate offline SQL and confirm it creates only collection tables. Run the migration against the development MySQL after taking a schema backup, then use `alembic current` to confirm `20260717_01`.

- [ ] **Step 3: Run Angular checks**

Run focused specs, `tsc -p tsconfig.app.json --noEmit`, and Angular development build with the bundled Node runtime. Report Karma's pre-existing `app.component.spec.ts:20` failure separately if still present.

- [ ] **Step 4: Verify source contracts**

Confirm the route is Admin-only, no collection schema contains PII columns, four quadrants are exact, all new component styles are external, and no ordinary EEG/WebSocket files changed.

- [ ] **Step 5: Conduct broad code review**

Review the complete range against `docs/superpowers/specs/2026-07-17-subject-independent-eeg-dataset-collection-design.md`. Fix Critical and Important findings with a failing regression test before implementation changes.
