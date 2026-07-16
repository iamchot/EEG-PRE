# Creative Headset Setup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the Muse 2 connection and sensor-check experience as a restrained, entertainment-focused Creative Headset Setup while preserving the existing EEG workflow and backend contracts.

**Architecture:** Keep `EegSessionComponent` responsible for workflow, device actions, page copy, and responsive layout. Keep `HorseshoeSensorComponent` as a presentation component that maps the four existing `SensorStatus` inputs into an accessible headset illustration, state rows, readiness summary, and contextual tip. No backend, service, route, or state-machine changes are required.

**Tech Stack:** Angular 19 standalone components, Angular Signals, inline Angular templates and CSS, Jasmine/Karma, TypeScript 5.7.

## Global Constraints

- Preserve the existing `DISCOVERING -> DEVICE_CONFIRMATION -> CONNECTING -> PREPARATION -> FITTING -> BASELINE` behavior and existing HTTP/WebSocket commands.
- Baseline remains enabled only when TP9, AF7, AF8, and TP10 are all `good`.
- Use dark Navy surfaces and restrained purple accents consistent with the approved PDF direction.
- Do not use medical symbols, diagnostic language, health scores, patient terminology, or mental-health accuracy claims.
- Use Thai as the primary UI language; retain `Muse 2`, `TP9`, `AF7`, `AF8`, and `TP10`.
- Sensor status must use icon plus text plus color.
- Interactive targets must be at least 44 by 44 pixels and keyboard focus must be visible.
- Do not add new runtime dependencies or change backend APIs.
- Preserve unrelated working-tree changes and stage only files named in each task.

## File Structure

- Create `frontend/src/app/shared/components/horseshoe-sensor/horseshoe-sensor.component.spec.ts`: focused rendering and state-summary tests for the sensor visualization.
- Modify `frontend/src/app/shared/components/horseshoe-sensor/horseshoe-sensor.component.ts`: accessible Muse-style illustration, Thai state labels, readiness summary, contextual tip, and restrained styling.
- Create `frontend/src/app/features/eeg-session/eeg-session.component.spec.ts`: workflow-copy, progress, device-state, entertainment-note, and Baseline-gating tests with mocked dependencies.
- Modify `frontend/src/app/features/eeg-session/eeg-session.component.ts`: compact header, four-step progress, unified main card, device scan states, fitting guidance, entertainment note, responsive layout, and retryable scan error.

---

### Task 1: Accessible Headset Sensor Visualization

**Files:**

- Create: `frontend/src/app/shared/components/horseshoe-sensor/horseshoe-sensor.component.spec.ts`
- Modify: `frontend/src/app/shared/components/horseshoe-sensor/horseshoe-sensor.component.ts:1-106`

**Interfaces:**

- Consumes: four Angular signal inputs named `tp9`, `af7`, `af8`, and `tp10`, each typed as `SensorStatus`.
- Produces: `stateLabel(key: SensorKey): string`, `stateIcon(key: SensorKey): string`, `attentionCount(): number`, `readinessLabel(): string`, `allUnknown(): boolean`, `allGood(): boolean`, and `currentTip(): string`.
- Preserves: selector `app-horseshoe-sensor` and the current four input names so `EegSessionComponent` requires no data-binding change.

- [ ] **Step 1: Write failing rendering and state tests**

Create `horseshoe-sensor.component.spec.ts`:

```ts
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { HorseshoeSensorComponent } from './horseshoe-sensor.component';
import { SensorState, SensorStatus } from '../../../core/services/eeg-ws.service';

const sensor = (state: SensorState): SensorStatus => ({
  state,
  quality_score: state === 'good' ? 100 : 0,
  timestamp: 0,
  sequence: 0,
});

describe('HorseshoeSensorComponent', () => {
  let fixture: ComponentFixture<HorseshoeSensorComponent>;
  let component: HorseshoeSensorComponent;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [HorseshoeSensorComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(HorseshoeSensorComponent);
    component = fixture.componentInstance;
  });

  function setStates(states: [SensorState, SensorState, SensorState, SensorState]) {
    fixture.componentRef.setInput('tp9', sensor(states[0]));
    fixture.componentRef.setInput('af7', sensor(states[1]));
    fixture.componentRef.setInput('af8', sensor(states[2]));
    fixture.componentRef.setInput('tp10', sensor(states[3]));
    fixture.detectChanges();
  }

  it('renders all four sensor identifiers and Thai locations', () => {
    setStates(['unknown', 'unknown', 'unknown', 'unknown']);
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';

    expect(text).toContain('TP9');
    expect(text).toContain('หลังหูซ้าย');
    expect(text).toContain('AF7');
    expect(text).toContain('หน้าผากซ้าย');
    expect(text).toContain('AF8');
    expect(text).toContain('หน้าผากขวา');
    expect(text).toContain('TP10');
    expect(text).toContain('หลังหูขวา');
  });

  it('uses Thai text and an icon for each sensor state', () => {
    setStates(['unknown', 'poor', 'good', 'stale']);
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';

    expect(text).toContain('รอสัญญาณ');
    expect(text).toContain('ปรับตำแหน่ง');
    expect(text).toContain('พร้อม');
    expect(text).toContain('ขาดการเชื่อมต่อ');
    expect(text).toContain('…');
    expect(text).toContain('!');
    expect(text).toContain('✓');
    expect(text).toContain('×');
  });

  it('summarizes unknown, attention, and ready states without a quality percentage', () => {
    setStates(['unknown', 'unknown', 'unknown', 'unknown']);
    expect(component.readinessLabel()).toBe('กำลังรอสัญญาณ');

    setStates(['good', 'poor', 'good', 'stale']);
    expect(component.readinessLabel()).toBe('ปรับเซนเซอร์อีก 2 จุด');

    setStates(['good', 'good', 'good', 'good']);
    expect(component.readinessLabel()).toBe('พร้อมเริ่ม');
    expect((fixture.nativeElement as HTMLElement).textContent).not.toContain('%');
  });

  it('uses an accessible headset figure label', () => {
    setStates(['good', 'good', 'good', 'good']);
    const figure = (fixture.nativeElement as HTMLElement).querySelector('[role="img"]');
    expect(figure?.getAttribute('aria-label')).toContain('ตำแหน่งเซนเซอร์ Muse 2');
  });
});
```

- [ ] **Step 2: Run the sensor tests and verify they fail**

Run:

```powershell
cd frontend
npx ng test --watch=false --include="src/app/shared/components/horseshoe-sensor/horseshoe-sensor.component.spec.ts"
```

Expected: FAIL because `readinessLabel`, Thai state labels, visible state icons, and the no-percentage presentation are not implemented.

- [ ] **Step 3: Implement state mapping and computed summaries**

In `horseshoe-sensor.component.ts`, remove `DecimalPipe`, export a narrow key type, and replace the English mapping and average score:

```ts
import { Component, computed, input } from '@angular/core';
import { SensorStatus, SensorState } from '../../../core/services/eeg-ws.service';

export type SensorKey = 'tp9' | 'af7' | 'af8' | 'tp10';

interface SensorPoint {
  key: SensorKey;
  label: string;
  location: string;
}

const STATE_LABEL: Record<SensorState, string> = {
  unknown: 'รอสัญญาณ',
  poor: 'ปรับตำแหน่ง',
  good: 'พร้อม',
  stale: 'ขาดการเชื่อมต่อ',
};

const STATE_ICON: Record<SensorState, string> = {
  unknown: '…',
  poor: '!',
  good: '✓',
  stale: '×',
};
```

Add these methods and computed values to the component class:

```ts
getSensorData(key: SensorKey): SensorStatus {
  return {
    tp9: this.tp9(),
    af7: this.af7(),
    af8: this.af8(),
    tp10: this.tp10(),
  }[key];
}

stateLabel(key: SensorKey): string {
  return STATE_LABEL[this.getSensorData(key).state];
}

stateIcon(key: SensorKey): string {
  return STATE_ICON[this.getSensorData(key).state];
}

allGood = computed(() =>
  this.sensorPoints.every(({ key }) => this.getSensorData(key).state === 'good')
);

allUnknown = computed(() =>
  this.sensorPoints.every(({ key }) => this.getSensorData(key).state === 'unknown')
);

attentionCount = computed(() =>
  this.sensorPoints.filter(({ key }) =>
    ['poor', 'stale'].includes(this.getSensorData(key).state)
  ).length
);

readinessLabel = computed(() => {
  if (this.allGood()) return 'พร้อมเริ่ม';
  if (this.allUnknown()) return 'กำลังรอสัญญาณ';
  const count = this.attentionCount();
  return count > 0 ? `ปรับเซนเซอร์อีก ${count} จุด` : 'กำลังตรวจสัญญาณ';
});
```

- [ ] **Step 4: Replace the sensor template**

Use one quiet illustration area, a readiness summary, four compact rows, and one contextual tip:

```html
<section class="sensor-panel" aria-labelledby="sensor-title">
  <header class="sensor-heading">
    <p class="section-kicker">สถานะการสวมใส่</p>
    <h2 id="sensor-title">Muse 2 ของคุณ</h2>
    <p>ตรวจให้เซนเซอร์ทั้ง 4 จุดแนบสนิทก่อนเริ่มบันทึก</p>
  </header>

  <div class="headset-figure" role="img" aria-label="ตำแหน่งเซนเซอร์ Muse 2 ได้แก่ TP9 AF7 AF8 และ TP10">
    <svg viewBox="0 0 360 220" aria-hidden="true" focusable="false">
      <path class="head-outline" d="M116 170 C118 92 145 54 180 54 C215 54 242 92 244 170" />
      <path class="headband" d="M64 160 C80 47 280 47 296 160" />
      @for (pt of sensorPoints; track pt.key) {
        <g [attr.class]="'sensor-node node-' + getSensorData(pt.key).state">
          <circle
            [attr.cx]="pt.key === 'tp9' ? 64 : pt.key === 'af7' ? 139 : pt.key === 'af8' ? 221 : 296"
            [attr.cy]="pt.key === 'tp9' || pt.key === 'tp10' ? 160 : 68"
            r="18"
          />
          <text
            [attr.x]="pt.key === 'tp9' ? 64 : pt.key === 'af7' ? 139 : pt.key === 'af8' ? 221 : 296"
            [attr.y]="pt.key === 'tp9' || pt.key === 'tp10' ? 165 : 73"
          >{{ stateIcon(pt.key) }}</text>
        </g>
      }
    </svg>
  </div>

  <div class="readiness" [class.ready]="allGood()" aria-live="polite">
    <span class="readiness-icon">{{ allGood() ? '✓' : '•' }}</span>
    <div>
      <strong>{{ readinessLabel() }}</strong>
      <span>{{ allGood() ? 'เซนเซอร์ครบทั้ง 4 จุด' : 'ขยับสายคาดตามตำแหน่งด้านล่าง' }}</span>
    </div>
  </div>

  <div class="sensor-list">
    @for (pt of sensorPoints; track pt.key) {
      <div class="sensor-row" [attr.data-state]="getSensorData(pt.key).state">
        <span class="state-mark" aria-hidden="true">{{ stateIcon(pt.key) }}</span>
        <div class="sensor-name">
          <strong>{{ pt.label }}</strong>
          <span>{{ pt.location }}</span>
        </div>
        <span class="state-label">{{ stateLabel(pt.key) }}</span>
      </div>
    }
  </div>

  @if (!allGood()) {
    <div class="signal-tip" role="status">
      <strong>ลองปรับแบบนี้</strong>
      <p>{{ currentTip() }}</p>
    </div>
  }
</section>
```

- [ ] **Step 5: Add restrained component styling**

Replace the current inline styles with:

```css
.sensor-panel { display:grid; gap:20px; min-width:0; }
.sensor-heading { display:grid; gap:5px; }
.section-kicker { margin:0; color:var(--color-secondary); font-size:.78rem; font-weight:700; letter-spacing:.08em; text-transform:uppercase; }
.sensor-heading h2 { margin:0; font-size:1.45rem; }
.sensor-heading p:last-child { margin:0; font-size:.9rem; line-height:1.55; }
.headset-figure { min-height:250px; display:grid; place-items:center; border-block:1px solid var(--color-border); }
.headset-figure svg { display:block; width:min(100%, 390px); height:auto; }
.head-outline { fill:none; stroke:rgba(148,163,184,.22); stroke-width:2; }
.headband { fill:none; stroke:#536078; stroke-width:14; stroke-linecap:round; }
.sensor-node circle { stroke:#111827; stroke-width:5; }
.sensor-node text { fill:#fff; font:700 13px var(--font-en); text-anchor:middle; }
.node-unknown circle { fill:var(--color-neutral); }
.node-poor circle { fill:var(--color-warning); }
.node-good circle { fill:var(--color-success); }
.node-stale circle { fill:var(--color-error); }
.readiness { display:flex; align-items:center; gap:12px; padding:14px 0; border-bottom:1px solid var(--color-border); }
.readiness-icon { width:32px; height:32px; display:grid; place-items:center; border-radius:50%; color:#E2E8F0; background:#334155; }
.readiness.ready .readiness-icon { color:#052E16; background:var(--color-success); }
.readiness strong,.readiness span { display:block; }
.readiness span { margin-top:2px; color:var(--color-text-muted); font-size:.8rem; }
.sensor-list { display:grid; gap:8px; }
.sensor-row { min-height:52px; display:grid; grid-template-columns:28px 1fr auto; align-items:center; gap:10px; padding:9px 10px; border-radius:10px; border:1px solid transparent; }
.sensor-row[data-state="poor"] { border-color:rgba(245,158,11,.34); }
.sensor-row[data-state="stale"] { border-color:rgba(239,68,68,.34); }
.state-mark { width:24px; height:24px; display:grid; place-items:center; border-radius:50%; background:#334155; font-weight:800; }
[data-state="good"] .state-mark { color:#052E16; background:var(--color-success); }
[data-state="poor"] .state-mark { color:#422006; background:var(--color-warning); }
[data-state="stale"] .state-mark { color:#450A0A; background:var(--color-error); }
.sensor-name strong,.sensor-name span { display:block; }
.sensor-name span,.state-label { color:var(--color-text-muted); font-size:.78rem; }
.state-label { text-align:right; }
.signal-tip { padding:14px 16px; border-left:3px solid var(--color-secondary); background:rgba(167,139,250,.06); }
.signal-tip p { margin:4px 0 0; font-size:.86rem; line-height:1.55; }
```

- [ ] **Step 6: Run the sensor tests**

Run:

```powershell
cd frontend
npx ng test --watch=false --include="src/app/shared/components/horseshoe-sensor/horseshoe-sensor.component.spec.ts"
```

Expected: `4 specs, 0 failures`.

- [ ] **Step 7: Commit the sensor component**

```powershell
git add -- frontend/src/app/shared/components/horseshoe-sensor/horseshoe-sensor.component.ts frontend/src/app/shared/components/horseshoe-sensor/horseshoe-sensor.component.spec.ts
git commit -m "feat: simplify Muse sensor visualization"
```

---

### Task 2: Creative Headset Connection Flow

**Files:**

- Create: `frontend/src/app/features/eeg-session/eeg-session.component.spec.ts`
- Modify: `frontend/src/app/features/eeg-session/eeg-session.component.ts:1-278`

**Interfaces:**

- Consumes: existing `EegWsService` signals and methods, `PersonaService.getAll()`, `ComicService.generate()`, Angular `HttpClient`, and `Router`.
- Produces: `steps` with keys `connect`, `signal`, `emotion`, and `comic`; `scanError` signal; `activeStepKey()`; `stepDone(key: string)`; unchanged public action methods `scanDevices()`, `selectDevice()`, `confirmDevice()`, and `startBaseline()`.
- Preserves: all existing HTTP URLs, WebSocket commands, later EEG phases, story fields, comic generation, and routing.

- [ ] **Step 1: Write failing page-shell and device-state tests**

Create `eeg-session.component.spec.ts` with explicit service doubles:

```ts
import { signal, computed } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting, HttpTestingController } from '@angular/common/http/testing';
import { Router } from '@angular/router';
import { of } from 'rxjs';
import { EegSessionComponent } from './eeg-session.component';
import { EegWsService, EEGMessage, SensorStatus } from '../../core/services/eeg-ws.service';
import { PersonaService } from '../../core/services/persona.service';
import { ComicService } from '../../core/services/comic.service';
import { environment } from '../../../environments/environment';

const unknown: SensorStatus = { state: 'unknown', quality_score: 0, timestamp: 0, sequence: 0 };

class EegWsStub {
  latestMessage = signal<EEGMessage | null>(null);
  phase = computed(() => this.latestMessage()?.phase ?? 'DISCOVERING');
  sensors = computed(() => ({
    tp9: this.latestMessage()?.tp9 ?? unknown,
    af7: this.latestMessage()?.af7 ?? unknown,
    af8: this.latestMessage()?.af8 ?? unknown,
    tp10: this.latestMessage()?.tp10 ?? unknown,
  }));
  allSensorsGood = computed(() => Object.values(this.sensors()).every(sensor => sensor.state === 'good'));
  acceptedSeconds = computed(() => 0);
  baselineSeconds = computed(() => 0);
  wallClockSeconds = computed(() => 0);
  isConnected = signal(true);
  connect = jasmine.createSpy('connect');
  disconnect = jasmine.createSpy('disconnect');
  sendCommand = jasmine.createSpy('sendCommand');
}

describe('EegSessionComponent', () => {
  let fixture: ComponentFixture<EegSessionComponent>;
  let component: EegSessionComponent;
  let http: HttpTestingController;
  let eegWs: EegWsStub;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [EegSessionComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: EegWsService, useClass: EegWsStub },
        { provide: PersonaService, useValue: { getAll: () => of([]) } },
        { provide: ComicService, useValue: { generate: () => of({ id: 1 }) } },
        { provide: Router, useValue: { navigate: jasmine.createSpy('navigate') } },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(EegSessionComponent);
    component = fixture.componentInstance;
    eegWs = TestBed.inject(EegWsService) as unknown as EegWsStub;
    http = TestBed.inject(HttpTestingController);
    fixture.detectChanges();

    http.expectOne(`${environment.apiUrl}/sessions`).flush({ id: 7 });
    fixture.detectChanges();
  });

  afterEach(() => http.verify());

  it('presents a four-step entertainment-focused setup', () => {
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    const steps = (fixture.nativeElement as HTMLElement).querySelectorAll('.step');

    expect(steps.length).toBe(4);
    expect(text).toContain('เชื่อมต่อ Muse 2');
    expect(text).toContain('เตรียมอุปกรณ์ให้พร้อมก่อนเริ่มสร้างเรื่องราว');
    expect(text).toContain('ข้อมูลอารมณ์ใช้เพื่อสร้างสรรค์คอมิกและความบันเทิง');
    expect(text).not.toContain('Dream Lab');
    expect(text).not.toContain('WebSocket');
  });

  it('shows a selected device and keeps connect disabled until selection', () => {
    component.discoveredDevices.set([{ name: 'Muse-A9C7', address: 'AA:BB' }]);
    fixture.detectChanges();
    const button = (fixture.nativeElement as HTMLElement).querySelector<HTMLButtonElement>('#btn-connect');

    expect(button?.disabled).toBeTrue();
    component.selectDevice({ name: 'Muse-A9C7', address: 'AA:BB' });
    fixture.detectChanges();
    expect(button?.disabled).toBeFalse();
  });

  it('shows a retryable message when no device is found', () => {
    component.scanDevices();
    http.expectOne(`${environment.apiUrl}/sessions/scan`).flush({ devices: [] });
    fixture.detectChanges();

    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain('ยังไม่พบ Muse 2');
    expect(text).toContain('ค้นหาอีกครั้ง');
  });

  it('uses plain user-facing local service status text', () => {
    eegWs.isConnected.set(false);
    fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('ยังไม่เชื่อมต่อ');

    eegWs.isConnected.set(true);
    fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('ระบบพร้อม');
  });
});
```

- [ ] **Step 2: Run the page tests and verify they fail**

Run:

```powershell
cd frontend
npx ng test --watch=false --include="src/app/features/eeg-session/eeg-session.component.spec.ts"
```

Expected: FAIL because the current page has six steps, developer-facing copy, no entertainment note, no `#btn-connect`, and no empty-result state.

- [ ] **Step 3: Add four-step mapping and scan error state**

Replace `steps`, `activeStepKey`, and `stepDone`, and add `scanError`:

```ts
scanError = signal('');

readonly steps = [
  { key: 'connect', label: 'เชื่อมต่อ' },
  { key: 'signal', label: 'ตรวจสัญญาณ' },
  { key: 'emotion', label: 'บันทึกอารมณ์' },
  { key: 'comic', label: 'สร้างคอมิก' },
];

activeStepKey = computed(() => ({
  device: 'connect',
  prepare: 'signal',
  baseline: 'signal',
  ready: 'emotion',
  record: 'emotion',
  emotion: 'emotion',
  generate: 'comic',
  fallback: 'connect',
}[this.stage()] ?? 'connect'));

stepDone(key: string) {
  return this.steps.findIndex(step => step.key === key)
    < this.steps.findIndex(step => step.key === this.activeStepKey());
}
```

Update `scanDevices()` without changing its endpoint or command:

```ts
scanDevices() {
  this.scanning.set(true);
  this.scanError.set('');
  this.discoveredDevices.set([]);
  this.selectedDevice.set(null);

  this.http.get<{ devices: { name: string; address: string }[] }>(
    `${environment.apiUrl}/sessions/scan`
  ).subscribe({
    next: ({ devices }) => {
      this.discoveredDevices.set(devices);
      this.scanning.set(false);
      if (devices.length === 0) {
        this.scanError.set('ยังไม่พบ Muse 2 ลองตรวจสอบว่าอุปกรณ์เปิดอยู่และ Bluetooth พร้อมใช้งาน');
        return;
      }
      this.eegWs.sendCommand('phase_transition', { phase: 'DEVICE_CONFIRMATION' });
    },
    error: () => {
      this.scanning.set(false);
      this.scanError.set('ค้นหาอุปกรณ์ไม่สำเร็จ ตรวจสอบการเชื่อมต่อในเครื่องแล้วลองอีกครั้ง');
    },
  });
}
```

- [ ] **Step 4: Replace the header, progress, connection card, and fitting copy**

Use this structure at the top of the template and retain the existing later-phase switch cases below the `prepare` case:

```html
<main class="session-shell">
  <header class="session-header">
    <div>
      <p class="section-kicker">Create Dream</p>
      <h1>เชื่อมต่อ Muse 2</h1>
      <p>เตรียมอุปกรณ์ให้พร้อมก่อนเริ่มสร้างเรื่องราว</p>
    </div>
    <div class="service-status" [class.online]="eegWs.isConnected()" role="status">
      <span class="status-dot" aria-hidden="true"></span>
      {{ eegWs.isConnected() ? 'ระบบพร้อม' : 'ยังไม่เชื่อมต่อ' }}
    </div>
  </header>

  <nav class="stepper" aria-label="ขั้นตอนการสร้างคอมิก">
    @for (step of steps; track step.key; let i = $index) {
      <div class="step" [class.active]="activeStepKey() === step.key" [class.done]="stepDone(step.key)">
        <span class="step-index">{{ stepDone(step.key) ? '✓' : i + 1 }}</span>
        <strong>{{ step.label }}</strong>
      </div>
    }
  </nav>

  <section class="setup-card">
    <app-horseshoe-sensor
      [tp9]="eegWs.sensors().tp9"
      [af7]="eegWs.sensors().af7"
      [af8]="eegWs.sensors().af8"
      [tp10]="eegWs.sensors().tp10"
    />

    <article class="stage-panel" aria-live="polite">
      @switch (stage()) {
        @case ('device') {
          <p class="section-kicker">ขั้นตอนที่ 1</p>
          <h2>ค้นหาอุปกรณ์ใกล้เคียง</h2>
          <p>เปิด Muse 2 และ Bluetooth จากนั้นค้นหาอุปกรณ์ที่อยู่ใกล้คอมพิวเตอร์เครื่องนี้</p>

          @if (!eegWs.isConnected()) {
            <div class="inline-message warning">
              เปิดบริการเชื่อมต่อในเครื่องให้พร้อมก่อนค้นหา Muse 2
            </div>
          }

          @if (discoveredDevices().length > 0) {
            <div class="device-list" role="radiogroup" aria-label="อุปกรณ์ Muse 2 ที่ค้นพบ">
              @for (device of discoveredDevices(); track device.address) {
                <button
                  type="button"
                  class="device-option"
                  role="radio"
                  [attr.aria-checked]="selectedDevice()?.address === device.address"
                  [class.selected]="selectedDevice()?.address === device.address"
                  (click)="selectDevice(device)"
                >
                  <span class="device-mark" aria-hidden="true">{{ selectedDevice()?.address === device.address ? '✓' : '' }}</span>
                  <span><strong>{{ device.name }}</strong><small>{{ device.address }}</small></span>
                </button>
              }
            </div>
            <button id="btn-connect" class="btn primary-action" [disabled]="!selectedDevice()" (click)="confirmDevice()">
              เชื่อมต่ออุปกรณ์
            </button>
          } @else {
            @if (scanError()) {
              <div class="inline-message" role="alert">{{ scanError() }}</div>
            }
            <button id="btn-scan" class="btn primary-action" (click)="scanDevices()" [disabled]="scanning()">
              @if (scanning()) { <span class="spinner" aria-hidden="true"></span> กำลังค้นหา… }
              @else { {{ scanError() ? 'ค้นหาอีกครั้ง' : 'ค้นหา Muse 2' }} }
            </button>
          }
        }

        @case ('prepare') {
          <p class="section-kicker">ขั้นตอนที่ 2</p>
          <h2>ปรับสายคาดให้พอดี</h2>
          <p>ใช้สถานะทางซ้ายเป็นแนวทาง แล้วปรับ Muse 2 ให้เซนเซอร์ครบทั้ง 4 จุด</p>
          <ol class="fitting-list">
            <li><span>1</span>เปิดบริเวณหน้าผากและหลังหูไม่ให้เส้นผมบัง</li>
            <li><span>2</span>วางสายคาดให้กระชับแต่ไม่แน่นเกินไป</li>
            <li><span>3</span>นั่งนิ่งและผ่อนคลายใบหน้าเมื่อเริ่มตรวจสัญญาณ</li>
          </ol>
          <button class="btn primary-action" (click)="startBaseline()" [disabled]="!eegWs.allSensorsGood()">
            {{ eegWs.allSensorsGood() ? 'เริ่มบันทึกค่าพื้นฐาน' : 'รอสัญญาณให้พร้อมครบ 4 จุด' }}
          </button>
        }

      }
    </article>
  </section>

  <p class="entertainment-note">
    ข้อมูลอารมณ์ใช้เพื่อสร้างสรรค์คอมิกและความบันเทิง ไม่ใช่การวินิจฉัยทางการแพทย์
  </p>
</main>
```

Treat the code above as bounded replacements for the current header, stepper, `session-grid` wrapper, `device` case, and `prepare` case. Leave the existing `baseline`, `ready`, `record`, `emotion`, `generate`, and `default` case bodies at current source lines 89-148 in place between the end of the new `prepare` case and the closing `@switch`; this task does not modify their markup, methods, or API calls.

- [ ] **Step 5: Replace the page layout styles**

Replace the shell, header, stepper, setup, device, and responsive rules while retaining styles used by later phases:

```css
.session-shell { width:min(1120px, calc(100% - 40px)); margin:0 auto; padding:40px 0 56px; display:grid; gap:24px; }
.session-header { display:flex; align-items:flex-start; justify-content:space-between; gap:24px; }
.session-header h1 { margin:4px 0 8px; font-size:clamp(2rem, 4vw, 3rem); }
.session-header p:last-child { margin:0; }
.section-kicker { margin:0; color:var(--color-secondary); font-size:.78rem; font-weight:700; letter-spacing:.08em; text-transform:uppercase; }
.service-status { min-height:36px; display:flex; align-items:center; gap:9px; padding:7px 12px; border:1px solid var(--color-border); border-radius:999px; color:var(--color-text-muted); white-space:nowrap; }
.status-dot { width:8px; height:8px; border-radius:50%; background:var(--color-warning); }
.service-status.online { color:#BBF7D0; }
.service-status.online .status-dot { background:var(--color-success); }
.stepper { display:grid; grid-template-columns:repeat(4,1fr); border-block:1px solid var(--color-border); }
.step { min-height:64px; display:flex; align-items:center; justify-content:center; gap:10px; color:var(--color-text-muted); }
.step-index { width:28px; height:28px; display:grid; place-items:center; border-radius:50%; background:#253047; font:700 .78rem var(--font-en); }
.step.active { color:#fff; }
.step.active .step-index { background:var(--color-primary); }
.step.done { color:#BBF7D0; }
.step.done .step-index { color:#052E16; background:var(--color-success); }
.setup-card { display:grid; grid-template-columns:minmax(0, 42%) minmax(0, 58%); overflow:hidden; border:1px solid var(--color-border); border-radius:16px; background:var(--color-surface); box-shadow:0 18px 48px rgba(2,6,23,.22); }
app-horseshoe-sensor { min-width:0; padding:30px; border-right:1px solid var(--color-border); background:#0E1628; }
.stage-panel { min-width:0; min-height:590px; display:flex; flex-direction:column; gap:18px; padding:42px; }
.stage-panel h2 { margin:0; }
.stage-panel > p:not(.section-kicker) { margin:0; }
.device-list { display:grid; gap:10px; margin-top:6px; }
.device-option { min-height:64px; width:100%; display:grid; grid-template-columns:30px 1fr; align-items:center; gap:12px; padding:11px 14px; text-align:left; color:var(--color-text-primary); border:1px solid var(--color-border); border-radius:10px; background:#141E32; cursor:pointer; }
.device-option:hover,.device-option:focus-visible { border-color:var(--color-border-strong); }
.device-option:focus-visible { outline:3px solid rgba(196,181,253,.35); outline-offset:2px; }
.device-option.selected { border-color:var(--color-primary); background:rgba(124,58,237,.09); }
.device-mark { width:22px; height:22px; display:grid; place-items:center; border:1px solid #64748B; border-radius:50%; }
.device-option.selected .device-mark { border-color:var(--color-primary); background:var(--color-primary); }
.device-option strong,.device-option small { display:block; }
.device-option small { margin-top:3px; color:var(--color-text-muted); }
.inline-message { padding:13px 15px; border-left:3px solid var(--color-secondary); background:rgba(167,139,250,.06); color:var(--color-text-secondary); }
.inline-message.warning { border-left-color:var(--color-warning); background:rgba(245,158,11,.06); }
.primary-action { width:100%; min-height:50px; margin-top:auto; color:#fff; background:var(--color-primary); border-radius:10px; }
.primary-action:hover:not(:disabled) { background:var(--color-primary-hover); }
.fitting-list { display:grid; gap:14px; margin:4px 0; padding:0; list-style:none; }
.fitting-list li { display:grid; grid-template-columns:30px 1fr; align-items:center; gap:12px; color:var(--color-text-secondary); }
.fitting-list li span { width:28px; height:28px; display:grid; place-items:center; border:1px solid var(--color-border-strong); border-radius:50%; color:var(--color-secondary); font-weight:700; }
.entertainment-note { margin:0; text-align:center; color:var(--color-text-muted); font-size:.78rem; }
@media (max-width:900px) {
  .setup-card { grid-template-columns:1fr; }
  app-horseshoe-sensor { border-right:0; border-bottom:1px solid var(--color-border); }
  .stage-panel { min-height:unset; }
}
@media (max-width:620px) {
  .session-shell { width:min(100% - 24px, 1120px); padding-top:24px; }
  .session-header { flex-direction:column; }
  .stepper { overflow-x:auto; grid-template-columns:repeat(4, minmax(110px, 1fr)); }
  app-horseshoe-sensor,.stage-panel { padding:22px; }
  .primary-action { min-height:52px; }
}
```

- [ ] **Step 6: Run the page and sensor tests**

Run:

```powershell
cd frontend
npx ng test --watch=false --include="src/app/features/eeg-session/eeg-session.component.spec.ts" --include="src/app/shared/components/horseshoe-sensor/horseshoe-sensor.component.spec.ts"
```

Expected: `8 specs, 0 failures`.

- [ ] **Step 7: Commit the connection flow**

```powershell
git add -- frontend/src/app/features/eeg-session/eeg-session.component.ts frontend/src/app/features/eeg-session/eeg-session.component.spec.ts
git commit -m "feat: redesign creative headset setup"
```

---

### Task 3: Regression, Accessibility, and Visual Verification

**Files:**

- Modify only if verification exposes a defect:
  - `frontend/src/app/features/eeg-session/eeg-session.component.ts`
  - `frontend/src/app/features/eeg-session/eeg-session.component.spec.ts`
  - `frontend/src/app/shared/components/horseshoe-sensor/horseshoe-sensor.component.ts`
  - `frontend/src/app/shared/components/horseshoe-sensor/horseshoe-sensor.component.spec.ts`

**Interfaces:**

- Consumes: completed components from Tasks 1 and 2.
- Produces: production-build evidence, passing focused tests, and visual confirmation at desktop/mobile widths.

- [ ] **Step 1: Run focused tests from a clean command**

Run:

```powershell
cd frontend
npx ng test --watch=false --include="src/app/features/eeg-session/eeg-session.component.spec.ts" --include="src/app/shared/components/horseshoe-sensor/horseshoe-sensor.component.spec.ts"
```

Expected: `8 specs, 0 failures`.

- [ ] **Step 2: Run the Angular production build**

Run:

```powershell
cd frontend
npm run build
```

Expected: exit code `0`, Angular reports application bundle generation complete, and no template/type errors.

- [ ] **Step 3: Start the frontend for browser inspection**

Run:

```powershell
cd frontend
npm start
```

Expected: Angular development server is available at `http://localhost:4200`.

- [ ] **Step 4: Inspect the device-connection state at desktop width**

At approximately 1440 by 900:

- Confirm the page has one primary two-column card.
- Confirm the Muse illustration occupies roughly 42 percent of the card.
- Confirm the right column shows the scan action without nested decorative cards.
- Confirm purple appears only on the current step, selection, focus, and primary action.
- Confirm no `Dream Lab`, `WebSocket`, quality percentage, medical icon, or diagnostic wording appears.
- Confirm the entertainment-use note is visible below the main card.

- [ ] **Step 5: Inspect state changes**

Exercise or simulate:

- Scanning: stable layout with `กำลังค้นหา…`.
- Empty result: inline explanation plus `ค้นหาอีกครั้ง`.
- Device found: selectable row and disabled connect action before selection.
- Device selected: purple border and enabled `เชื่อมต่ออุปกรณ์`.
- Fitting: three instructions and disabled Baseline action until all four sensors are good.
- Sensor states: each of unknown, poor, good, and stale has a distinct icon, Thai label, and color.

- [ ] **Step 6: Inspect responsive and keyboard behavior**

At approximately 390 by 844 and at 200 percent browser zoom:

- Confirm the headset appears above the controls.
- Confirm no horizontal clipping occurs in the main card.
- Confirm the current progress step remains visible.
- Confirm primary actions are full width and at least 44 pixels high.
- Tab through scan, device choices, and connect/Baseline actions; confirm a visible focus ring and logical order.

- [ ] **Step 7: Fix only observed defects and re-run verification**

For each observed defect, first add or tighten the closest Jasmine expectation, run it to see the failure, make the smallest component/CSS correction, then repeat Steps 1 and 2. Do not refactor unrelated screens or change global design tokens.

- [ ] **Step 8: Commit verification fixes if any**

If files changed during verification:

```powershell
git add -- frontend/src/app/features/eeg-session/eeg-session.component.ts frontend/src/app/features/eeg-session/eeg-session.component.spec.ts frontend/src/app/shared/components/horseshoe-sensor/horseshoe-sensor.component.ts frontend/src/app/shared/components/horseshoe-sensor/horseshoe-sensor.component.spec.ts
git commit -m "fix: polish creative headset setup"
```

If no files changed, do not create an empty commit.
