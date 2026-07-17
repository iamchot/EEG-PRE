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

## Earlier Interfaces
Use Task 1 models in backend/app/models/dataset_collection.py and Task 3 schemas/services in backend/app/schemas/dataset_collection.py and backend/app/services/dataset_collection_service.py at HEAD c87177e. Preserve the existing app middleware and role dependencies.
## Report Contract
Write .superpowers/sdd/eeg-foundation-task-4-report.md with files changed, RED/GREEN evidence, authorization/contract results, commit hash, self-review, and concerns. Return only status, commit hash, one-line test summary, and concerns.

