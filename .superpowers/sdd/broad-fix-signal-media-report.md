# Broad Review Fix: Signal Integrity and Media Synchronization

## Scope

Implemented findings 1 and 2 from the broad review at base `b4ae8ff`. The change is limited to the Muse collection adapter, collection runner state/manager/schema/API, runner Angular DTO/WS/component, and their tests. It does not alter scheduler, migrations, device leases, ordinary EEG/comic behavior, or the live database.

## Signal integrity

- Muse LSL has no native four-contact quality stream in this adapter. Quality is explicitly reported as `derived_eeg_window`.
- Each channel uses a bounded rolling window (default: the configured expected sample count, 256 samples) and the existing `signal_processor.estimate_sensor_state` amplitude/flatline/artifact thresholds.
- Raw CSV quality columns contain those derived per-channel scores. The adapter no longer assigns `100`.
- Raw EEG and sensor freshness DTOs retain validated LSL source timestamps. Receipt time is used only to validate source age; it is not written as the channel timestamp.
- Observed sampling rate is deterministic: `(sample_count - 1) / (last_source_timestamp - first_source_timestamp)` after 16 samples. The configured `collection_sampling_rate_hz=256` and `collection_sampling_tolerance_hz=8` are supplied to the live adapter.
- Unknown warm-up or out-of-tolerance rate remains in Raw EEG for audit but fails clean accounting. Non-increasing timestamps, stale source samples, and stopped-stream stale observations are not written.
- A sample pulled before a newly committed phase marker is skipped against the marker watermark, preventing a valid capture from being interrupted without fabricating or rewriting its source timestamp.
- Quality is observed and broadcast outside active capture so pre-baseline readiness can become true without writing Raw EEG.
- Baseline API start requires a live source, all four backend-derived sensors good, and rate in tolerance. The 60 wall / 30 all-four-clean completion contract remains unchanged.

## Stimulus accounting and QC

- Rest clean counters are discarded at `stimulus_start`; stimulus wall time and accepted all-four-clean time start at zero together.
- `CollectionTrial.wall_clock_seconds` and `accepted_clean_seconds` are stimulus-only.
- `qc_summary_json` records derived quality provenance, configured sampling contract, all-four clean coverage, four per-channel good coverages, and `valid_signal`.
- `valid_signal` requires at least 80% all-four clean stimulus coverage and at least 80% good coverage independently for AF7 and AF8.

## Runner and media synchronization

- Runner REST/WS DTO includes the four measured sensor objects, observed rate, rate status, live readiness, stimulus-start readiness, and quality provenance.
- Angular WS parsing validates the exact four-sensor map and all new fields before accepting state.
- Horseshoe renders backend-derived sensor states/scores. Admin contact checkboxes remain separately labeled confirmations and never create measured quality.
- Baseline UI requires device persistence, prepared schedule, live WS, all four manual confirmations, and backend live-sensor readiness.
- During rest, video controls are hidden behind a blocking overlay until backend `stimulus_start_ready` is true (valid 10–15 second rest window plus live sensors/rate).
- Any allowed `playing` event is immediately paused and rewound to `currentTime=0`; playback resumes only after Backend returns the committed `stimulus` state. Early events and rejections stay rewound, and rejection exposes retry. A media error also pauses and rewinds. Duplicate/buffering `playing` and `ended` events remain idempotent, and failed finish retains the existing retry path.

## TDD evidence

New regressions were observed failing before implementation for:

- fabricated quality/source receipt timestamps;
- deterministic 240 Hz rejection against 256 ± 8;
- stale emission when samples stop;
- out-of-tolerance clean-time rejection;
- stimulus-only counter reset and persisted 80% QC;
- source/Backend clock-domain-safe readiness;
- measured horseshoe/manual separation;
- early/rejected media playback pause, rewind, and retry.

Verification:

- Backend full: `python -m pytest -q` -> `180 passed, 3 skipped`.
- Angular focused runner/WS/service: `49 SUCCESS`.
- Angular production build: successful; existing CSS budget warnings remain.
- The repository's full/spec TypeScript compile is independently blocked by two pre-existing stale assertions in `app.component.spec.ts` (`AppComponent.title` and obsolete `Hello, frontend` scaffold). Those assertions were temporarily excluded only to run focused tests and were restored unchanged.

## Operational notes

- No hardware is required by any regression.
- No database migration is needed; QC uses the existing `qc_summary_json` column.
- No live database command was run.
