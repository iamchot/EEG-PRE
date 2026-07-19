# Broad Review Fix 3: Cross-Process Scheduler Idempotency

## Outcome

- Serializes schedule creation by selecting the `CollectionSession` row with
  `FOR UPDATE` before checking for existing trials.
- Persists `session.total_trials = 12` and all 12 trial rows in the same
  transaction.
- Rejects partial or malformed existing schedules with the safe
  `ScheduleUnavailableError` message.
- Recovers from an `IntegrityError` race by rolling back and returning the
  committed winner only when it has exactly 12 unique stimuli in orders 1-12
  and the session records `total_trials = 12`.
- Adds database-enforced uniqueness for
  `(session_id, randomized_order)` through ORM metadata and Alembic revision
  `20260719_03` (`down_revision = 20260719_02`). Downgrade only drops the
  constraint. No live database was migrated.

The optional `(session_id, stimulus_id)` database constraint was not retained:
an existing runner contract permits reusing a stimulus across trial records.
The scheduler still enforces 12 distinct stimulus IDs before accepting any
existing or race-winner schedule, while the order constraint is sufficient to
prevent concurrent workers from persisting 24 scheduler rows.

## TDD Evidence

Initial focused RED run:

```text
6 failed, 12 passed
```

The failures demonstrated missing ORM uniqueness, missing migration, acceptance
of a one-row partial schedule, absence of the session row lock, and failure to
reload a valid unique-race winner.

Final focused verification command:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest \
  tests/test_dataset_collection_models.py \
  tests/test_trial_scheduler.py \
  tests/test_trial_schedule_migration.py \
  tests/test_collection_runner_api.py::test_rest_start_rejects_a_non_next_trial_before_transition -q
```

Result:

```text
21 passed, 1 warning
```

Coverage includes deterministic seed/idempotency, inventory shortage, draft and
retired stimulus exclusions, rollback safety, partial-schedule rejection,
`FOR UPDATE` ordering, unique-race winner reload, a deterministic two-worker
row-lock simulation, ORM constraint metadata, Alembic revision/operation
metadata, downgrade behavior, and emitted PostgreSQL constraint SQL.

## Full Backend Suite Interference

A full backend run after the scoped changes reached:

```text
173 passed, 1 skipped, 3 failed, 1 warning
```

The three failures were runner-state fake objects missing newly added signal
quality fields while another agent was editing signal/manager files in the
shared workspace. They are outside this fix and none of those files were
modified or staged here. The root agent will rerun the full suite after the
concurrent signal-integrity work is committed.

## Files

- `backend/app/services/trial_scheduler.py`
- `backend/app/models/dataset_collection.py`
- `backend/alembic/versions/20260719_03_trial_schedule_uniqueness.py`
- `backend/tests/test_trial_scheduler.py`
- `backend/tests/test_dataset_collection_models.py`
- `backend/tests/test_trial_schedule_migration.py`
- `.superpowers/sdd/broad-fix-scheduler-report.md`

## Deployment Concern

Alembic upgrade will fail safely if production already contains duplicate
`(session_id, randomized_order)` rows. Task 8 must inspect/backup the live data
before applying revision `20260719_03`; this task intentionally did not mutate
the live database.
