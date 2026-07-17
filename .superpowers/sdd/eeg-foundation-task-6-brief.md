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

## Earlier Interfaces
Use DatasetCollectionService and DTOs at frontend/src/app/core/services/dataset-collection.service.ts from commit 611431e. The route already lazily imports this exact component path/class. Do not change the API client unless a verified contract defect blocks the UI.
## Report Contract
Write .superpowers/sdd/eeg-foundation-task-6-report.md with files changed, RED/GREEN evidence, exact type-check/build commands, UI/source checks, commit hash, self-review, and concerns. Return only status, commit hash, one-line test/build summary, and concerns.

