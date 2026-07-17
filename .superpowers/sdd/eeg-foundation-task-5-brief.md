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

## Backend Contract
The API base is /api/v1/admin/dataset-collection. List endpoints accept skip and limit. Create contracts are defined in backend/app/schemas/dataset_collection.py at HEAD b2b8978. Match their JSON field names exactly.
## Report Contract
Write .superpowers/sdd/eeg-foundation-task-5-report.md with files changed, RED/GREEN evidence, route/source checks, commit hash, self-review, and concerns. Return only status, commit hash, one-line test/build summary, and concerns.

