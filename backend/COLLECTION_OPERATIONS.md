# Muse 2 Collection Operations

This collection workflow is for entertainment and research use only. It is not a medical device, diagnostic tool, or treatment system. Use an approved consent protocol and pseudonymous participant codes; never put participant names, email addresses, or device identifiers in filenames.

## One-time provisioning

1. Create the directories configured by `COLLECTION_RAW_DIR`, `COLLECTION_STIMULUS_DIR`, and `COLLECTION_LOCK_DIR`. Keep the Raw and lock directories writable only by the API account.
2. Copy approved video files beneath `COLLECTION_STIMULUS_DIR`. Store only relative paths in `emotion_stimuli.file_path`; absolute paths and `..` traversal are rejected.
3. Calculate every file's SHA-256 checksum, for example:

   ```powershell
   Get-FileHash -Algorithm SHA256 .\collection_stimuli\approved-clip.mp4
   ```

   Store that digest in `emotion_stimuli.checksum`. The Admin-only media route verifies the checksum and fails closed if the file is missing, outside the configured root, not a video, or changed.
4. Create `.venv`, install `requirements_backend.txt`, configure `.env`, and provision the database through the project's normal deployment process. Do not run migrations or seed commands during an active capture.

## Start a collection session

Run each command from `backend` unless noted otherwise.

1. Confirm Muse discovery and note the intended device address:

   ```powershell
   muselsl list
   ```

2. In a dedicated terminal, start the LSL bridge for that exact device:

   ```powershell
   muselsl stream --address 00:11:22:33:44:55
   ```

3. Before opening the runner, verify an EEG LSL stream is visible:

   ```powershell
   .\.venv\Scripts\python.exe -c "from pylsl import resolve_byprop; streams=resolve_byprop('type','EEG',timeout=5); print([s.name() for s in streams]); raise SystemExit(0 if streams else 1)"
   ```

4. Start the API with exactly one worker and reload disabled:

   ```powershell
   .\start_collection_backend.ps1
   ```

5. Log in as an Admin, select the verified device, and keep the runner WebSocket connected for the entire capture. Stop capture before restarting the API or LSL bridge.

The OS device lease prevents two sessions, API manager instances, or API processes from acquiring the same device concurrently. Its filename is a SHA-256 digest of the device ID, not the raw ID. The lease is released on normal completion, stream errors, WebSocket disconnect, cancellation, and process exit.

## Reload and worker warning

`start_backend.ps1` is the ordinary development launcher. It runs Uvicorn with `--reload`, so it is not safe during active collection: a source change can restart the process and interrupt capture. Likewise, do not use multiple Uvicorn workers for collection. Use `start_collection_backend.ps1`, which explicitly supplies `--workers 1` and never enables reload or opens a browser.

## Pre-capture check

- Consent and pseudonymous participant code are confirmed.
- Approved stimulus files exist under `COLLECTION_STIMULUS_DIR` and their database checksums match.
- `muselsl list` sees the intended headset; only its exact address is streamed.
- The LSL verification command returns an EEG stream.
- Disk space and write permission are available under `COLLECTION_RAW_DIR` and `COLLECTION_LOCK_DIR`.
- One no-reload API process is running, with no other collection worker active.
