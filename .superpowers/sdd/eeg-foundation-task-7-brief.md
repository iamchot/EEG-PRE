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

## Verification Context
Feature implementation range is 6b949cc..e8eb70b. Focused frontend test config is frontend/tsconfig.dataset-collection.spec.json. Back up MySQL schema to an untracked .superpowers/sdd artifact before applying the migration. Do not modify production files; report any failure instead.
## Report Contract
Write .superpowers/sdd/eeg-foundation-task-7-report.md with exact commands, exit codes, test counts, backup path, migration current revision, source-contract results, git diff/check results, and concerns. Return only status, one-line verification summary, and concerns.

