# Task Brief

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

## Report Contract
Write .superpowers/sdd/eeg-foundation-task-1-report.md with files changed, RED/GREEN evidence, migration SQL safety checks, commit hash, self-review, and concerns. Return only status, commit hash, one-line test summary, and concerns.

