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

## Earlier Interfaces
Task 1 models/enums are in backend/app/models/dataset_collection.py at commit 49dc9b3. Task 2 label service is in backend/app/services/dataset_labels.py at commit 4dfdd72. Consume them; do not duplicate them.
## Report Contract
Write .superpowers/sdd/eeg-foundation-task-3-report.md with files changed, RED/GREEN evidence, commit hash, self-review, and concerns. Return only status, commit hash, one-line test summary, and concerns.

