# Managed Muse and Truthful Health Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let User and Admin flows discover and connect a real Muse 2 without a manual terminal, remove Mock EEG UI, and show only Backend-verified Muse, ComfyUI, and Gemini statuses.

**Architecture:** A process-wide `ManagedMuseBridgeManager` scans Windows BLE, owns one hidden `muselsl` subprocess and device lease per physical Muse, and declares success only after a matching 256 Hz EEG LSL stream appears. Role-specific HTTP endpoints share that manager while the ordinary User EEG and Admin collection pipelines retain their separate state machines and WebSockets. A separate cached health service verifies ComfyUI and Gemini and feeds typed Angular status components.

**Tech Stack:** FastAPI, asyncio, Bleak, muselsl, pylsl, filelock, Pydantic, httpx, google-generativeai, Angular 19 standalone components, Signals, RxJS, Jasmine/Karma.

## Global Constraints

- This is an entertainment and prototype-research workflow, not medical diagnosis or treatment.
- Preserve all existing user and uncommitted changes; stage only files named by the active Task.
- Do not apply Alembic `20260719_03` or change the live database in this plan.
- Do not run application build commands.
- Do not open a browser; ChromeHeadless tests are allowed.
- Use RED → GREEN TDD for every behavior change.
- Keep User EEG and Admin Dataset Collection authorization and WebSocket routes separate.
- A Muse transport is `connected` only after matching EEG LSL exists at 256 Hz.
- Sensor contact colors remain independent from transport connection state.
- All Angular styles changed by this plan live in external `.css` files; no inline `styles` metadata or `style` attributes.
- Never commit `backend/.env`, database dumps, temporary Karma configs, or `.superpowers/sdd` artifacts.

## File Structure

- Create `backend/app/services/muse_ble.py`: Windows BLE scan abstraction and Muse advertisement aggregation.
- Create `backend/app/services/muse_device_lease.py`: reusable SHA-256 device lease extracted from the collection manager.
- Create `backend/app/services/muse_bridge_manager.py`: scan jobs, hidden bridge process ownership, LSL verification, cleanup, and status state machine.
- Create `backend/app/services/eeg_stream_runner.py`: ordinary User-session Muse sample pump.
- Create `backend/app/schemas/muse.py`: shared scan/connection DTOs.
- Create `backend/app/routers/muse.py`: authenticated scan and User-session connection endpoints.
- Modify `backend/app/ws/collection_manager.py`: consume the managed bridge instead of independently owning Bluetooth.
- Modify `backend/app/routers/dataset_collection.py`: Admin connection/status/disconnect endpoints using the same bridge manager.
- Modify `backend/app/routers/eeg_session.py`: User-session connection lifecycle and sample pump.
- Modify `backend/app/main.py`: router registration and owned-process shutdown.
- Modify `backend/app/config.py`, `backend/.env.example`, `backend/requirements_backend.txt`: exact timeouts, executable override, and direct Bleak dependency.
- Create `backend/app/services/system_health.py`, `backend/app/schemas/system_health.py`, and `backend/app/routers/system_health.py`: cached truthful health checks.
- Create `frontend/src/app/core/services/muse-device.service.ts`: shared scan/connect polling and global Muse state.
- Create `frontend/src/app/core/services/system-health.service.ts`: typed health endpoint client.
- Modify both Muse pages to use the shared device service.
- Modify root shell and Dashboard to remove Mock/hard-coded statuses.
- Create `frontend/src/app/app.component.css` and `frontend/src/app/features/dashboard/dashboard.component.css`: externalized styles.

---

### Task 1: Windows BLE Muse Discovery

**Files:**

- Create: `backend/app/services/muse_ble.py`
- Create: `backend/tests/test_muse_ble.py`
- Modify: `backend/app/config.py`
- Modify: `backend/.env.example`
- Modify: `backend/requirements_backend.txt`

**Interfaces:**

- Produces `MuseBleDevice(address: str, name: str)`.
- Produces `MuseBleScanner.scan(*, timeout: float) -> list[MuseBleDevice]`.
- Adds `muse_scan_timeout_seconds=30.0`, `muse_connect_timeout_seconds=45.0`, and `muse_lsl_timeout_seconds=10.0`.

- [ ] **Step 1: Write failing advertisement-aggregation tests**

```python
async def test_scan_waits_for_later_named_advertisement():
    scanner = MuseBleScanner(scanner_factory=fake_scanner([
        advertisement("00:55:DA:B7:A9:C7", local_name=None, at=0.1),
        advertisement("00:55:DA:B7:A9:C7", local_name="Muse-A9C7", at=1.0),
    ]))
    assert await scanner.scan(timeout=2) == [
        MuseBleDevice(address="00:55:DA:B7:A9:C7", name="Muse-A9C7")
    ]


async def test_scan_excludes_non_muse_and_deduplicates_address():
    scanner = MuseBleScanner(scanner_factory=fake_scanner([
        advertisement("AA", local_name="Petkit_CTW2", at=0.1),
        advertisement("BB", local_name="Muse-B123", at=0.2),
        advertisement("BB", local_name="Muse-B123", at=0.3),
    ]))
    assert await scanner.scan(timeout=1) == [
        MuseBleDevice(address="BB", name="Muse-B123")
    ]
```

Also cover scanner exception → `MuseBleError("Bluetooth scan failed")` with no platform detail.

- [ ] **Step 2: Run RED**

```powershell
cd backend
& '.\.venv\Scripts\python.exe' -m pytest tests/test_muse_ble.py -q -p no:cacheprovider
```

Expected: import failure because `muse_ble.py` does not exist.

- [ ] **Step 3: Implement the bounded scanner**

```python
@dataclass(frozen=True, slots=True)
class MuseBleDevice:
    address: str
    name: str


class MuseBleScanner:
    def __init__(self, scanner_factory=BleakScanner):
        self._scanner_factory = scanner_factory

    async def scan(self, *, timeout: float) -> list[MuseBleDevice]:
        observed: dict[str, str] = {}

        def on_advertisement(device, advertisement) -> None:
            name = (advertisement.local_name or device.name or "").strip()
            if name.casefold().startswith("muse-"):
                observed[device.address] = name

        scanner = self._scanner_factory(detection_callback=on_advertisement)
        try:
            async with scanner:
                await asyncio.sleep(timeout)
        except Exception as exc:
            raise MuseBleError("Bluetooth scan failed") from exc
        return [
            MuseBleDevice(address=address, name=name)
            for address, name in sorted(observed.items())
        ]
```

Add direct `bleak>=0.22,<4` dependency and the three timeout settings/environment examples.

- [ ] **Step 4: Run GREEN and configuration tests**

```powershell
& '.\.venv\Scripts\python.exe' -m pytest tests/test_muse_ble.py tests/test_collection_runner_api.py -q -p no:cacheprovider
```

Expected: all selected tests pass.

- [ ] **Step 5: Commit**

```powershell
git add -- backend/app/services/muse_ble.py backend/tests/test_muse_ble.py backend/app/config.py backend/.env.example backend/requirements_backend.txt
git commit -m "feat: discover Muse devices over BLE"
```

---

### Task 2: Managed Muse Bridge Lifecycle

**Files:**

- Create: `backend/app/services/muse_device_lease.py`
- Create: `backend/app/services/muse_bridge_manager.py`
- Create: `backend/app/schemas/muse.py`
- Create: `backend/tests/test_muse_bridge_manager.py`
- Modify: `backend/app/ws/collection_manager.py`

**Interfaces:**

- Moves `DeviceLease` and `DeviceLeaseUnavailableError` unchanged into `muse_device_lease.py`.
- Produces `MuseBridgeState = idle | scanning | found | not_found | starting_bridge | connecting_bluetooth | waiting_for_lsl | connected | failed | disconnecting`.
- Produces `MuseOwner(kind: Literal["user", "collection"], session_id: int)`.
- Produces `MuseScanStatus` and `MuseConnectionStatus` Pydantic DTOs.
- Produces singleton `managed_muse_bridge_manager`.
- Produces async methods `start_scan(actor_id)`, `get_scan(actor_id, scan_id)`, `connect(owner, device)`, `status(owner)`, `release(owner)`, and `shutdown()`.

- [ ] **Step 1: Write failing state/process tests**

```python
async def test_scan_returns_immediately_in_scanning_state():
    manager = manager_with(scan_gate=asyncio.Event())
    started = await manager.start_scan(actor_id=7)
    assert started.state == "scanning"
    assert started.devices == []


async def test_connect_is_not_green_until_matching_256hz_lsl_exists():
    manager = manager_with(
        process=fake_process(lines=["[28.6s] BLE connected."]),
        lsl_results=[[], [fake_stream(source_id="MuseAA", rate=128)], [fake_stream(source_id="MuseAA", rate=256)]],
    )
    task = asyncio.create_task(manager.connect(MuseOwner("user", 4), MuseBleDevice("AA", "Muse-AA")))
    await manager.wait_for_state("waiting_for_lsl")
    assert manager.status(MuseOwner("user", 4)).state == "waiting_for_lsl"
    assert (await task).state == "connected"
```

Also cover exact hidden command arguments, one process per address, lease conflict, early process exit, BLE timeout, LSL timeout, cancellation, owned-process cleanup, external pre-existing valid LSL adoption, and never terminating an unowned process.

- [ ] **Step 2: Run RED**

```powershell
& '.\.venv\Scripts\python.exe' -m pytest tests/test_muse_bridge_manager.py -q -p no:cacheprovider
```

Expected: missing bridge manager/types.

- [ ] **Step 3: Extract the device lease and implement the status machine**

The subprocess command must be constructed internally:

```python
command = [
    str(Path(sys.executable).with_name("muselsl.exe")),
    "stream",
    "--address", device.address,
    "--backend", "bleak",
    "--lsltime",
]
creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
```

The manager must set `PYTHONUNBUFFERED=1`, read bounded output, recognize the
exact BLE-connected line, and resolve only the selected source ID:

```python
expected_source_id = f"Muse{device.address}"
if stream.source_id() == expected_source_id and stream.nominal_srate() == 256:
    state = MuseBridgeState.connected
```

Store no more than 100 diagnostic lines per bridge. Public `detail` values
come from a fixed safe-message map.

- [ ] **Step 4: Make the collection manager consume the shared lease owner**

Replace its local lease class with imports from `muse_device_lease.py`. Inject
the bridge manager and require a connected bridge for
`MuseOwner("collection", session_id)` before opening the LSL inlet. Remove the
second lease acquisition from `_pump`; the bridge manager owns it until
`stop_source()` releases that owner.

- [ ] **Step 5: Run GREEN plus existing contention/recovery tests**

```powershell
& '.\.venv\Scripts\python.exe' -m pytest tests/test_muse_bridge_manager.py tests/test_collection_runner_api.py tests/test_collection_recovery_integration.py -q -p no:cacheprovider
```

Expected: all hardware-independent tests pass and no subprocess survives a test.

- [ ] **Step 6: Commit**

```powershell
git add -- backend/app/services/muse_device_lease.py backend/app/services/muse_bridge_manager.py backend/app/schemas/muse.py backend/tests/test_muse_bridge_manager.py backend/app/ws/collection_manager.py backend/tests/test_collection_runner_api.py
git commit -m "feat: manage Muse bridge lifecycle"
```

---

### Task 3: Authenticated User and Admin Muse APIs

**Files:**

- Create: `backend/app/routers/muse.py`
- Create: `backend/app/services/eeg_stream_runner.py`
- Create: `backend/tests/test_muse_api.py`
- Modify: `backend/app/routers/eeg_session.py`
- Modify: `backend/app/routers/dataset_collection.py`
- Modify: `backend/app/main.py`
- Modify: `backend/tests/test_collection_runner_api.py`

**Interfaces:**

- User scan: `POST /api/v1/muse/scans`, `GET /api/v1/muse/scans/{scan_id}`.
- User connection: `POST|GET|DELETE /api/v1/sessions/{session_id}/muse`.
- Admin connection: `POST|GET|DELETE /api/v1/admin/dataset-collection/sessions/{session_id}/muse`.
- Produces `UserEEGStreamRunner.start(session_id, machine, bridge_status)` and `stop(session_id)`.

- [ ] **Step 1: Write failing authorization and progress-contract tests**

```python
def test_scan_returns_202_before_ble_scan_finishes(client, user_headers, scan_gate):
    response = client.post("/api/v1/muse/scans", headers=user_headers)
    assert response.status_code == 202
    assert response.json()["state"] == "scanning"


def test_user_cannot_connect_another_users_session(client, user_headers, other_session):
    response = client.post(
        f"/api/v1/sessions/{other_session.id}/muse",
        headers=user_headers,
        json={"address": "00:55:DA:B7:A9:C7", "name": "Muse-A9C7"},
    )
    assert response.status_code == 404


def test_admin_collection_connection_reports_waiting_for_lsl_before_connected(
    client, admin_headers, collection_session, fake_bridge
):
    fake_bridge.set_status(
        MuseOwner("collection", collection_session.id),
        MuseBridgeState.waiting_for_lsl,
    )
    response = client.get(
        f"/api/v1/admin/dataset-collection/sessions/{collection_session.id}/muse",
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["state"] == "waiting_for_lsl"
```

Cover scan ownership, expired/unknown scan IDs, User/Admin role boundaries,
duplicate connect idempotency, disconnect, terminal collection summary not
starting a bridge, and safe failure details.

- [ ] **Step 2: Write failing ordinary EEG pump tests**

```python
async def test_user_runner_ingests_real_four_channel_muse_sample():
    sample = muse_sample(tp9=1, af7=2, af8=3, tp10=4, timestamp=10.0)
    await runner.pump_one(sample)
    np.testing.assert_array_equal(machine.last_samples, [[1, 2, 3, 4]])
    np.testing.assert_array_equal(machine.last_timestamps, [10.0])
```

Also cover bridge disconnect → ordinary session `DISCONNECTED`, WebSocket
broadcast, stop on cancellation/completion, and no changes to the Admin sample
pipeline.

- [ ] **Step 3: Run RED**

```powershell
& '.\.venv\Scripts\python.exe' -m pytest tests/test_muse_api.py tests/test_collection_runner_api.py -q -p no:cacheprovider
```

Expected: routes and runner are missing.

- [ ] **Step 4: Implement role-specific endpoints over the shared manager**

Every User route uses `StandardUser` and verifies `EEGSession.user_id`.
Every Admin collection route uses `AdminUser` and verifies the collection
session exists. The scan job records `actor_id`; only that actor can poll it.

When a bridge reaches `connected`:

```python
machine.confirm_device(status.device_name, status.device_address)
await user_eeg_stream_runner.start(session_id, machine, status)
```

Do not declare the state-machine device connected when bridge state is
`starting_bridge`, `connecting_bluetooth`, or `waiting_for_lsl`.

- [ ] **Step 5: Register lifecycle cleanup**

Register `muse.router`. In FastAPI lifespan shutdown:

```python
await user_eeg_stream_runner.shutdown()
await managed_muse_bridge_manager.shutdown()
```

Cancellation/completion endpoints stop the User runner. Admin
`collection_manager.stop_source()` releases the collection bridge owner.

- [ ] **Step 6: Run GREEN and auth/source-isolation suites**

```powershell
& '.\.venv\Scripts\python.exe' -m pytest tests/test_muse_api.py tests/test_auth_role_boundaries.py tests/test_role_dependencies.py tests/test_collection_runner_api.py tests/test_collection_recovery_integration.py -q -p no:cacheprovider
```

Expected: all selected tests pass; ordinary and collection WebSocket paths
remain distinct.

- [ ] **Step 7: Commit**

```powershell
git add -- backend/app/routers/muse.py backend/app/services/eeg_stream_runner.py backend/tests/test_muse_api.py backend/app/routers/eeg_session.py backend/app/routers/dataset_collection.py backend/app/main.py backend/tests/test_collection_runner_api.py
git commit -m "feat: connect Muse from User and Admin sessions"
```

---

### Task 4: Shared Angular Muse Client and User Loading Flow

**Files:**

- Create: `frontend/src/app/core/services/muse-device.service.ts`
- Create: `frontend/src/app/core/services/muse-device.service.spec.ts`
- Modify: `frontend/src/app/features/eeg-session/eeg-session.component.ts`
- Modify: `frontend/src/app/features/eeg-session/eeg-session.component.css`
- Modify: `frontend/src/app/features/eeg-session/eeg-session.component.spec.ts`
- Modify: `frontend/tsconfig.dataset-collection.spec.json`

**Interfaces:**

- Produces `MuseScanState`, `MuseConnectionState`, `MuseDevice`, `MuseScanStatus`, and `MuseConnectionStatus`.
- Produces root signals `scanStatus`, `connectionStatus`, and `connectedDevice`.
- Produces `scan()`, `connectUser(sessionId, device)`, `connectCollection(sessionId, device)`, `disconnectUser(sessionId)`, and `disconnectCollection(sessionId)`.

- [ ] **Step 1: Write failing service polling tests**

```typescript
it('keeps scanning until the backend returns a terminal scan state', fakeAsync(() => {
  service.scan();
  http.expectOne(`${api}/muse/scans`).flush({ scan_id: 's1', state: 'scanning', devices: [] });
  expect(service.scanStatus().state).toBe('scanning');

  tick(500);
  http.expectOne(`${api}/muse/scans/s1`).flush({
    scan_id: 's1', state: 'found',
    devices: [{ address: '00:55:DA:B7:A9:C7', name: 'Muse-A9C7', leased: false }],
  });
  expect(service.scanStatus().state).toBe('found');
}));
```

Cover one active poll, explicit cancellation, typed failure, User/Admin URL
selection, connection polling through every stage, and green state only for
`connected`.

- [ ] **Step 2: Write failing User UI tests**

Assert:

- Clicking scan immediately renders the spinner and 10–30 second copy.
- No not-found message appears while `state === "scanning"`.
- Found devices are selectable.
- Connect renders Bluetooth then LSL waiting copy.
- Only verified `connected` advances to sensor fitting.
- Retry clears prior errors.
- Transport green does not force sensor components green.

- [ ] **Step 3: Run RED**

```powershell
cd frontend
npx ng test --watch=false --browsers=ChromeHeadless --include='src/app/core/services/muse-device.service.spec.ts' --include='src/app/features/eeg-session/eeg-session.component.spec.ts' --ts-config=tsconfig.dataset-collection.spec.json
```

Expected: missing service and old immediate-error behavior.

- [ ] **Step 4: Implement the shared client and replace direct HttpClient scan**

Use RxJS `timer(500, 500)`, `switchMap`,
`takeWhile(status => !terminalScanStates.has(status.state), true)`, and
`finalize` for bounded polling. The component must derive button/notice states
from typed service signals, not `eegWs.isConnected()`:

```typescript
readonly scanning = computed(() => this.muse.scanStatus()?.state === 'scanning');
readonly connecting = computed(() =>
  ['starting_bridge', 'connecting_bluetooth', 'waiting_for_lsl']
    .includes(this.muse.connectionStatus()?.state ?? '')
);
```

Retain keyboard/radiogroup accessibility and the Creative Headset Setup sensor
layout. Replace the two existing dynamic `[style.width.%]` progress bars in
this edited component with native `<progress>` elements so the component
contains no style attributes or style-property bindings.

- [ ] **Step 5: Add external semantic-state CSS**

Add `.status--idle`, `.status--busy`, `.status--available`,
`.status--connected`, and `.status--failed`. Busy state has motion and
respects `prefers-reduced-motion`. Do not use a style attribute.

- [ ] **Step 6: Run GREEN**

Run the same focused command. Expected: all selected specs pass with no
temporary config committed.

- [ ] **Step 7: Commit**

```powershell
git add -- frontend/src/app/core/services/muse-device.service.ts frontend/src/app/core/services/muse-device.service.spec.ts frontend/src/app/features/eeg-session/eeg-session.component.ts frontend/src/app/features/eeg-session/eeg-session.component.css frontend/src/app/features/eeg-session/eeg-session.component.spec.ts frontend/tsconfig.dataset-collection.spec.json
git commit -m "feat: show real Muse connection progress"
```

---

### Task 5: Admin Runner Integration and Mock EEG Removal

**Files:**

- Modify: `frontend/src/app/features/dataset-collection-runner/dataset-collection-runner.component.ts`
- Modify: `frontend/src/app/features/dataset-collection-runner/dataset-collection-runner.component.css`
- Modify: `frontend/src/app/features/dataset-collection-runner/dataset-collection-runner.component.spec.ts`
- Modify: `frontend/src/app/app.component.ts`
- Create: `frontend/src/app/app.component.css`
- Modify: `frontend/src/app/app.component.spec.ts`

**Interfaces:**

- Consumes `MuseDeviceService` from Task 4.
- Root shell displays a real connected device only when
  `connectionStatus.state === "connected"`.

- [ ] **Step 1: Write failing Admin flow tests**

```typescript
it('discovers and connects a real Muse before persisting it to the collection session', () => {
  muse.scanStatus.set(foundScan);
  component.selectDiscoveredDevice(foundScan.devices[0]);
  component.connectSelectedDevice();
  muse.connectionStatus.set(waitingForLsl);
  expect(api.selectDevice).not.toHaveBeenCalled();

  muse.connectionStatus.set(connectedMuse);
  fixture.detectChanges();
  expect(api.selectDevice).toHaveBeenCalledOnceWith(13, {
    device_id: '00:55:DA:B7:A9:C7',
    device_name: 'Muse-A9C7',
  });
});
```

Also verify manual ID fields are no longer the primary UI, progress stages
render, and an existing persisted/resumed session does not launch a duplicate
bridge.

- [ ] **Step 2: Write failing root-shell tests**

```typescript
it('never renders Mock EEG and only shows a verified real Muse', () => {
  expect(fixture.nativeElement.textContent).not.toContain('Mock EEG');
  expect(fixture.nativeElement.textContent).toContain('ยังไม่ได้เชื่อม Muse');
  muse.connectionStatus.set(connectedMuse);
  fixture.detectChanges();
  expect(fixture.nativeElement.textContent).toContain('Muse-A9C7');
});
```

- [ ] **Step 3: Run RED**

```powershell
npx ng test --watch=false --browsers=ChromeHeadless --include='src/app/app.component.spec.ts' --include='src/app/features/dataset-collection-runner/dataset-collection-runner.component.spec.ts' --ts-config=tsconfig.dataset-collection.spec.json
```

Expected: hard-coded Mock EEG/manual Admin fields remain.

- [ ] **Step 4: Integrate the Admin runner**

Use the same scan and connection states as the User page. Call
`DatasetCollectionService.selectDevice()` only after the managed connection
status is `connected`. Keep schedule preparation as a separate explicit Admin
action.

- [ ] **Step 5: Remove Mock EEG and externalize root styles**

Move the existing root inline component stylesheet content verbatim into
`app.component.css`, set `styleUrl: './app.component.css'`, remove the inline
`style="flex:1"` spacer, and replace it with `.sidebar-spacer`.

Show:

- Neutral: `ยังไม่ได้เชื่อม Muse`
- Busy: current stage text
- Connected: actual `device_name`
- Failed/lost: safe failure text, never a green dot

- [ ] **Step 6: Run GREEN and inline-style source checks**

```powershell
npx ng test --watch=false --browsers=ChromeHeadless --include='src/app/app.component.spec.ts' --include='src/app/features/dataset-collection-runner/dataset-collection-runner.component.spec.ts' --ts-config=tsconfig.dataset-collection.spec.json
Select-String -Path 'src/app/app.component.ts','src/app/features/dataset-collection-runner/dataset-collection-runner.component.ts' -Pattern 'styles\s*:|style='
```

Expected: tests pass and source scan returns no matches.

- [ ] **Step 7: Commit**

```powershell
git add -- frontend/src/app/features/dataset-collection-runner/dataset-collection-runner.component.ts frontend/src/app/features/dataset-collection-runner/dataset-collection-runner.component.css frontend/src/app/features/dataset-collection-runner/dataset-collection-runner.component.spec.ts frontend/src/app/app.component.ts frontend/src/app/app.component.css frontend/src/app/app.component.spec.ts
git commit -m "feat: unify Muse setup across roles"
```

---

### Task 6: Truthful Backend Service Health

**Files:**

- Create: `backend/app/services/system_health.py`
- Create: `backend/app/schemas/system_health.py`
- Create: `backend/app/routers/system_health.py`
- Create: `backend/tests/test_system_health.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/config.py`
- Modify: `backend/.env.example`

**Interfaces:**

- Produces `HealthState = unknown | checking | available | degraded | unavailable`.
- Produces `ServiceHealth(state, detail, checked_at, latency_ms)`.
- Produces `SystemHealthResponse(api, comfyui, gemini, muse)`.
- Produces authenticated `GET /api/v1/system/health`.
- Adds exact settings: ComfyUI timeout 2 seconds, Gemini timeout 8 seconds,
  cache TTL 30 seconds.

- [ ] **Step 1: Write failing ComfyUI health tests**

```python
async def test_comfyui_is_available_only_for_valid_live_response():
    client = fake_http_get("/system_stats", status=200, json={"system": {"os": "nt"}})
    result = await service.check_comfyui()
    assert result.state == HealthState.available


async def test_configured_url_without_live_service_is_unavailable():
    client = fake_http_timeout()
    result = await service.check_comfyui()
    assert result.state == HealthState.unavailable
```

- [ ] **Step 2: Write failing Gemini/cache/privacy tests**

Use an injected model lookup:

```python
async def test_gemini_requires_verified_configured_model():
    lookup = fake_model_lookup(model="models/gemini-1.5-flash")
    assert (await service.check_gemini()).state == HealthState.available


async def test_health_cache_avoids_duplicate_provider_calls():
    await service.status()
    await service.status()
    assert lookup.call_count == 1
```

Cover placeholder key → unavailable without network call, authentication/model
error → unavailable, rate limit/network error → degraded, 30-second expiry,
safe response text with no key/path/provider body, and authenticated endpoint.

- [ ] **Step 3: Run RED**

```powershell
& '.\.venv\Scripts\python.exe' -m pytest tests/test_system_health.py -q -p no:cacheprovider
```

Expected: missing service/router.

- [ ] **Step 4: Implement independent checks and cache**

Use injected monotonic and wall clocks. Protect cache mutation with an
`asyncio.Lock`; execute ComfyUI and Gemini checks concurrently with
`asyncio.gather`.

```python
async with httpx.AsyncClient(timeout=settings.comfyui_health_timeout_seconds) as client:
    response = await client.get(f"{settings.comfyui_url}/system_stats")
    response.raise_for_status()
    if not isinstance(response.json().get("system"), dict):
        raise ValueError("invalid health response")
```

Gemini uses `asyncio.to_thread(genai.get_model, normalized_model_name)` after
rejecting known placeholder keys. Return fixed Thai-safe details only.

Muse health reads the managed bridge snapshot; a saved database device ID is
not evidence of connection.

- [ ] **Step 5: Register endpoint and run GREEN**

```powershell
& '.\.venv\Scripts\python.exe' -m pytest tests/test_system_health.py tests/test_auth_role_boundaries.py -q -p no:cacheprovider
```

Expected: all selected tests pass.

- [ ] **Step 6: Commit**

```powershell
git add -- backend/app/services/system_health.py backend/app/schemas/system_health.py backend/app/routers/system_health.py backend/tests/test_system_health.py backend/app/main.py backend/app/config.py backend/.env.example
git commit -m "feat: report verified service health"
```

---

### Task 7: Dashboard Health and Semantic Colors

**Files:**

- Create: `frontend/src/app/core/services/system-health.service.ts`
- Create: `frontend/src/app/core/services/system-health.service.spec.ts`
- Modify: `frontend/src/app/features/dashboard/dashboard.component.ts`
- Create: `frontend/src/app/features/dashboard/dashboard.component.css`
- Create: `frontend/src/app/features/dashboard/dashboard.component.spec.ts`
- Modify: `frontend/tsconfig.dataset-collection.spec.json`

**Interfaces:**

- Consumes `GET /api/v1/system/health`.
- Produces signals `loading`, `health`, and `error`.
- Maps Backend states directly to CSS classes; it never promotes
  `unknown/degraded/unavailable` to green.

- [ ] **Step 1: Write failing health-client tests**

```typescript
it('starts unknown/loading and preserves backend states and timestamps', () => {
  service.refresh();
  expect(service.loading()).toBeTrue();
  http.expectOne(`${api}/system/health`).flush(systemHealth({
    comfyui: { state: 'unavailable', detail: 'ComfyUI ไม่ตอบสนอง', checked_at: checkedAt },
  }));
  expect(service.health()?.comfyui.state).toBe('unavailable');
  expect(service.health()?.comfyui.checked_at).toBe(checkedAt);
});
```

- [ ] **Step 2: Write failing Dashboard truthfulness tests**

Assert initial gray/checking state, green only for `available`, amber for
`degraded`, red for `unavailable`, timestamp rendering, no hard-coded “Ready
for comic panels” or “Prompt pipeline enabled,” and Muse state from the
Backend response.

- [ ] **Step 3: Run RED**

```powershell
npx ng test --watch=false --browsers=ChromeHeadless --include='src/app/core/services/system-health.service.spec.ts' --include='src/app/features/dashboard/dashboard.component.spec.ts' --ts-config=tsconfig.dataset-collection.spec.json
```

Expected: missing client/spec and hard-coded green status.

- [ ] **Step 4: Implement the client and replace hard-coded arrays**

Dashboard calls `health.refresh()` on init. Render API, ComfyUI, Muse, and
Gemini from the response. On request failure render `unknown`/“ตรวจสถานะไม่ได้”
rather than retaining a prior green state.

- [ ] **Step 5: Externalize Dashboard CSS**

Move the existing inline stylesheet into
`dashboard.component.css`, set
`styleUrl: './dashboard.component.css'`, and add semantic classes:

```css
.dot--unknown { background: var(--color-neutral); }
.dot--checking { background: var(--color-primary); animation: status-pulse 1.2s ease-in-out infinite; }
.dot--available { background: var(--color-success); }
.dot--degraded { background: var(--color-warning); }
.dot--unavailable { background: var(--color-danger); }
@media (prefers-reduced-motion: reduce) { .dot--checking { animation: none; } }
```

- [ ] **Step 6: Run GREEN and source scan**

```powershell
npx ng test --watch=false --browsers=ChromeHeadless --include='src/app/core/services/system-health.service.spec.ts' --include='src/app/features/dashboard/dashboard.component.spec.ts' --ts-config=tsconfig.dataset-collection.spec.json
Select-String -Path 'src/app/features/dashboard/dashboard.component.ts' -Pattern 'styles\s*:|Ready for comic panels|Prompt pipeline enabled'
```

Expected: all tests pass and scan returns no matches.

- [ ] **Step 7: Commit**

```powershell
git add -- frontend/src/app/core/services/system-health.service.ts frontend/src/app/core/services/system-health.service.spec.ts frontend/src/app/features/dashboard/dashboard.component.ts frontend/src/app/features/dashboard/dashboard.component.css frontend/src/app/features/dashboard/dashboard.component.spec.ts frontend/tsconfig.dataset-collection.spec.json
git commit -m "feat: show verified system health"
```

---

### Task 8: Non-Build End-to-End Verification and Broad Review

**Files:** No planned production changes.

- [ ] **Step 1: Run complete focused Backend coverage**

```powershell
cd backend
& '.\.venv\Scripts\python.exe' -m pytest tests/test_muse_ble.py tests/test_muse_bridge_manager.py tests/test_muse_api.py tests/test_system_health.py tests/test_collection_runner_api.py tests/test_collection_state_machine.py tests/test_collection_recovery_integration.py tests/test_auth_role_boundaries.py tests/test_role_dependencies.py -q -p no:cacheprovider
```

Expected: hardware-independent tests pass; MySQL-only skips must be explicitly
reported rather than treated as coverage.

- [ ] **Step 2: Run complete focused Angular coverage**

```powershell
cd frontend
npx ng test --watch=false --browsers=ChromeHeadless --include='src/app/app.component.spec.ts' --include='src/app/core/services/muse-device.service.spec.ts' --include='src/app/core/services/system-health.service.spec.ts' --include='src/app/features/eeg-session/eeg-session.component.spec.ts' --include='src/app/features/dataset-collection-runner/dataset-collection-runner.component.spec.ts' --include='src/app/features/dashboard/dashboard.component.spec.ts' --ts-config=tsconfig.dataset-collection.spec.json
```

Expected: all selected specs pass. A temporary GPU-safe launcher may be used
when required by the environment but must be removed before scope review.

- [ ] **Step 3: Verify no Mock/status lies or inline styling remain**

```powershell
Select-String -Path `
  'src/app/app.component.ts',`
  'src/app/features/eeg-session/eeg-session.component.ts',`
  'src/app/features/dataset-collection-runner/dataset-collection-runner.component.ts',`
  'src/app/features/dashboard/dashboard.component.ts' `
  -Pattern 'Mock EEG Headset|Ready for comic panels|Prompt pipeline enabled|styles\s*:|style=|\[style\.'
```

Expected: no Mock/hard-coded service text and no inline styling in files
changed by this plan. Pre-existing unrelated matches must be listed, not
silently rewritten.

- [ ] **Step 4: Run a real local Muse smoke check without opening a browser**

With Muse powered and no other application owning it, call the scan endpoint,
poll through `scanning → found`, request connection, poll through the bridge
states, and verify Backend health reports:

```text
muse.state = available
muse.detail identifies verified LSL transport
LSL type = EEG
nominal_srate = 256
```

Then disconnect through the API and verify the owned subprocess exits and the
device lease can be reacquired. Do not place the device address in Raw EEG
paths or committed reports.

- [ ] **Step 5: Verify service health behavior**

Check three explicit environments:

1. ComfyUI stopped → unavailable/red.
2. Gemini placeholder key → unavailable/red without provider call.
3. Available provider → green with fresh `checked_at`.

Never print or record the Gemini key.

- [ ] **Step 6: Verify repository scope**

```powershell
git diff --check
git status --short
git diff --name-only <PLAN_BASE>..HEAD
```

Confirm no database migration, `.env`, dump, temporary launcher, browser
artifact, Mock source, or unrelated dirty file entered the plan commits.

- [ ] **Step 7: Run independent broad review**

Review the complete plan diff for:

- Process/lease races and leaked subprocesses.
- User/Admin authorization and IDOR.
- False green health states.
- LSL source/rate validation.
- User and collection WebSocket isolation.
- External CSS compliance and truthful colors.

Fix every Critical/Important issue with RED regressions, rerun the focused
verification, and mark the plan complete only after SPEC PASS / QUALITY
APPROVED / CODE READY.
