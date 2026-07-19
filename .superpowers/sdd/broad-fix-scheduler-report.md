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
  tests/test_trial_schedule_migration.py -q
```

Result:

```text
23 passed
```

Coverage includes deterministic seed/idempotency, inventory shortage, draft and
retired stimulus exclusions, rollback safety, partial-schedule rejection,
`FOR UPDATE` ordering, unique-race winner reload, a deterministic two-worker
row-lock simulation, ORM constraint metadata, Alembic revision/operation
metadata, downgrade behavior, and emitted PostgreSQL/MySQL upgrade and
downgrade SQL.

## MySQL Review Evidence

The review follow-up added a real MySQL 8.0 integration race. It creates a
uniquely named `eegpre_scheduler_test_<uuid>` database, uses independent
engines, connections, and sessions (verified with distinct MySQL
`CONNECTION_ID()` values), starts two workers together without a Python lock,
and asserts both callers return the same persisted 12-row schedule. The test
passed locally.

The online migration integration creates a separate
`eegpre_migration_test_<uuid>` database and runs the actual Alembic revision
chain through `20260719_02` on an explicitly bound connection. After inserting
duplicate `(session_id, randomized_order)` rows, upgrading to `20260719_03`
fails as intended. The test verifies `alembic_version` remains
`20260719_02`, the unique constraint is absent, both legacy rows remain, and no
partial DDL side effect occurred. This test also passed locally.

Both fixtures require database-creation privileges and otherwise skip with an
explicit reason. Local verification supplied a test-only administrative URL
through `EEGPRE_MYSQL_TEST_ADMIN_URL`; the configured application account is
correctly restricted to the live application database. Database names are
validated against strict test-only patterns before both creation and cleanup,
and cleanup only drops the generated test database.

## Full Backend Suite

After the concurrent signal work settled, the full backend command completed:

```text
181 passed, 1 skipped, 1 warning
```

The single skip is an existing unrelated conditional test. Both new MySQL
integrations ran and passed in this full-suite invocation.

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
