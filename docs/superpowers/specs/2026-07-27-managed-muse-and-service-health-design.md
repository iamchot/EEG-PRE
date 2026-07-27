# Backend-Managed Muse and Truthful Service Health Design

**Date:** 2026-07-27  
**Status:** Approved in conversation; awaiting written-spec review  
**Product context:** Entertainment and prototype research only, not medical use

## Goal

Users and Admins can discover and connect a real Muse 2 entirely through the
application without manually running a terminal. Every device or service
status shown in the UI must come from a current Backend observation rather
than hard-coded text.

## Scope

This design covers:

- Real Muse discovery and managed `muselsl` process ownership on Windows.
- One shared Muse connection workflow for `/eeg-session` and the Admin
  Dataset Collection Runner.
- Explicit discovery and connection progress states.
- Removal of all Mock EEG device labels and indicators.
- Truthful Muse, ComfyUI, and Gemini status reporting.
- Semantic status colors and operator-facing failure messages.

It does not change EEG interpretation, emotion labeling, comic generation
logic, authentication roles, dataset schema, or the approved Creative Headset
Setup layout direction.

## Architecture

### Muse bridge manager

Add one Backend service responsible for the lifecycle of the local Muse
bridge. It has three separate responsibilities:

1. Scan Windows BLE devices and return Muse devices only.
2. Start one `muselsl stream` subprocess for the selected address.
3. Verify that the expected EEG LSL stream appears before declaring the device
   connected.

The service uses the existing SHA-256 device lease before launching a bridge.
One physical Muse cannot be owned by multiple sessions, Backend managers, or
bridge processes.

The subprocess uses the project virtual environment's `muselsl.exe`, an exact
BLE address, the Windows `bleak` backend, and LSL timestamps. It runs hidden
and must not open a terminal or browser.

### Shared connection workflow

Both User EEG Session and Admin Dataset Runner consume the same Backend device
API and connection-state contract. Neither page accepts a manually typed
device ID as the primary workflow.

The Admin runner keeps its stricter collection state machine, device lease,
signal-quality gates, and interruption behavior. The User EEG flow uses the
same physical bridge but retains its ordinary EEG WebSocket and session
behavior.

### Process ownership

The Backend owns each bridge process it starts:

- Keep the bridge alive while an active session still owns the device.
- Do not restart it when another client subscribes to the same owning session.
- Stop it when the session completes, fails, is cancelled/withdrawn, or the
  final owning client leaves outside active capture.
- On Backend shutdown, terminate owned bridge processes and release leases.
- Never terminate an unrelated `muselsl` process that the Backend did not
  start.

Process stdout/stderr is captured into a bounded in-memory diagnostic buffer.
The API exposes only safe, device-neutral messages.

## Muse API and state contract

### Discovery

An authenticated endpoint starts an asynchronous BLE scan and returns a
request identifier immediately. Status can be read through polling or the
existing relevant WebSocket.

Discovery states:

- `idle`
- `scanning`
- `found`
- `not_found`
- `failed`

The UI must remain in `scanning` for the real scan duration and must not show
`not_found` before the Backend scan completes or times out.
One scan lasts at most 30 seconds and aggregates advertisement updates for the
whole window, so a device whose name is absent in an early Windows BLE packet
can still be recognized when a later packet supplies `Muse-*`.

Each result contains only:

- Display name, such as `Muse-A9C7`
- BLE address/device identifier needed for connection
- Whether the device is already leased

### Connection

Selecting a discovered device starts the managed bridge and progresses through:

- `starting_bridge`
- `connecting_bluetooth`
- `waiting_for_lsl`
- `connected`
- `failed`
- `disconnecting`

`connected` is valid only when an EEG LSL stream with the selected Muse source
identifier is visible and reports the expected 256 Hz nominal rate. Sensor
contact quality remains a separate state and can still be unknown or poor
after transport connection succeeds.

The API returns a safe failure category and Thai operator message for:

- Bluetooth device disappeared
- Bluetooth device is already in use
- BLE connection timeout
- Bridge process exited
- LSL stream timeout
- Wrong stream rate or channel contract
- Unexpected local bridge failure

## User interface

### Search and connection feedback

Both Muse pages show a staged progress panel:

- Scanning: animated spinner and “กำลังค้นหา Muse ใกล้เครื่อง อาจใช้เวลา
  10–30 วินาที”
- Found: selectable real device card
- Connecting: progress text for Bluetooth and LSL stages
- Connected: device name, live 256 Hz transport status, then the four sensor
  contact states
- Failure: concise reason and “ลองอีกครั้ง”

Buttons are disabled only while the corresponding request is active.
Repeated clicks must not create concurrent scans or bridge processes.

### Removing Mock EEG

Remove `Mock EEG Headset` and every hard-coded connected indicator from the
sidebar, Dashboard, and session pages. When no real Muse status has been
checked, show no connected device or show the neutral text “ยังไม่ได้เชื่อม
Muse” depending on available space.

### Semantic colors

Colors express verified state only:

- Neutral gray: not checked, idle, or no device selected
- Blue/purple with motion: scanning, starting, connecting, or waiting
- Green: verified live service/transport
- Amber: available but not connected, degraded, or action required
- Red: completed check failed or connection was lost

Sensor colors remain independent from transport colors. A green Muse transport
does not turn TP9/AF7/AF8/TP10 green until their measured contact state is
good.

All styling remains in component `.css` files. No inline `styles` metadata or
`style` attributes are introduced.

## Truthful system health

Add one Backend health endpoint that reports independent observations for:

- API
- ComfyUI
- Gemini
- Muse bridge/LSL

Each service record contains:

- `state`: `unknown | checking | available | degraded | unavailable`
- Safe human-readable detail
- `checked_at`
- Optional latency in milliseconds

### ComfyUI

ComfyUI is `available` only after a short-timeout request to its local system
or queue health endpoint succeeds with a valid response. A configured URL or
existing output directory is not sufficient.

### Gemini

Gemini is `available` only after the Backend SDK verifies the configured API
key and requested model with a lightweight provider request. Merely having a
non-placeholder key is not sufficient. Checks are cached briefly to avoid
quota waste and repeated dashboard requests. A successful or failed provider
observation is cached for 30 seconds.

Authentication or model errors are `unavailable`; network/rate-limit
conditions are `degraded` with safe text. Secrets and provider response bodies
are never sent to the frontend.

### Muse

Muse health distinguishes:

- Bluetooth device discovered
- Bridge starting
- LSL transport connected
- Four-sensor contact readiness

The Dashboard must not display “connected” solely because a device ID is saved
in the database.

## Timeouts and recovery

- BLE discovery times out after 30 seconds.
- BLE connection times out after 45 seconds; matching LSL appearance receives
  a separate 10-second timeout after the bridge reports a BLE connection.
- ComfyUI health uses a 2-second timeout; Gemini health uses an 8-second
  timeout and the 30-second cache described above.
- Cancelling or navigating away during scanning cancels UI subscription but
  does not corrupt the Backend manager.
- A failed bridge is terminated, awaited, removed from the registry, and its
  lease is released.
- If the bridge exits during capture, the existing collection interruption
  path persists the interruption and aborts partial capture safely.
- A retry starts from clean manager state and never reuses a failed process.

## Security and privacy

- Muse discovery and User connection endpoints require an authenticated User;
  Admin collection connection retains Admin-only authorization.
- Backend commands use an executable path derived from the active project
  environment, not user-provided executable or arguments.
- Device addresses are used only for connection and lease identity. Raw EEG
  paths remain pseudonymous and do not gain device addresses.
- Health responses expose no API keys, local filesystem paths, command lines,
  stack traces, or raw provider responses.

## Testing

### Backend

- BLE scan progresses through scanning before found/not-found.
- The known Windows case where advertisement name is temporarily absent does
  not produce an immediate false negative.
- Only Muse-named devices are returned.
- Exact address launches one hidden bridge and waits for matching LSL.
- Connected is impossible before valid 256 Hz EEG LSL exists.
- Concurrent connect attempts respect the device lease.
- Timeout, process exit, cancellation, and shutdown release process and lease.
- User and Admin authorization boundaries remain separate.
- ComfyUI and Gemini health checks distinguish available, degraded,
  unavailable, and timeout without exposing secrets.

### Frontend

- Search shows loading state until the request completes.
- Not-found and failure messages appear only after completed Backend results.
- Connection stages and semantic colors map exactly to typed Backend states.
- Duplicate clicks do not create duplicate requests.
- Mock EEG text and hard-coded green service statuses no longer render.
- ComfyUI/Gemini green states require `available` from the Backend response.
- Sensor color remains independent from Muse transport connection.

### Verification

Focused Backend and Angular headless tests are required. Application build and
live browser opening remain excluded unless the user changes the project
instruction.

## Success criteria

- A powered, available Muse can be found and connected from either application
  flow without manually starting a terminal.
- The UI visibly spends the real scan/connect duration in a loading state.
- `connected` means a verified 256 Hz EEG LSL stream exists.
- No Mock EEG label remains.
- ComfyUI and Gemini green indicators reflect successful current Backend
  checks and include a check timestamp.
- Failures are recoverable through a visible retry without restarting the
  application.
