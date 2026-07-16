import { DecimalPipe } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { Component, OnDestroy, OnInit, computed, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { environment } from '../../../environments/environment';
import { EegWsService } from '../../core/services/eeg-ws.service';
import { ComicService } from '../../core/services/comic.service';
import { Persona, PersonaService } from '../../core/services/persona.service';
import { HorseshoeSensorComponent } from '../../shared/components/horseshoe-sensor/horseshoe-sensor.component';

@Component({
  selector: 'app-eeg-session',
  standalone: true,
  imports: [FormsModule, DecimalPipe, HorseshoeSensorComponent],
  template: `
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
                  @if (scanning()) {
                    <span class="spinner" aria-hidden="true"></span> กำลังค้นหา…
                  } @else {
                    {{ scanError() ? 'ค้นหาอีกครั้ง' : 'ค้นหา Muse 2' }}
                  }
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
              <button id="btn-baseline" class="btn primary-action" (click)="startBaseline()" [disabled]="!eegWs.allSensorsGood()">
                {{ eegWs.allSensorsGood() ? 'เริ่มบันทึกค่าพื้นฐาน' : 'รอสัญญาณให้พร้อมครบ 4 จุด' }}
              </button>
            }

            @case ('baseline') {
              <span class="eyebrow">Baseline Calibration</span>
              <h2>20 seconds neutral state</h2>
              <p>นั่งนิ่ง ๆ ผ่อนคลายใบหน้า และลืมตาตามธรรมชาติ ระบบจะ reset baseline หากสัญญาณหลุด</p>
              <div class="timer-block"><strong>{{ 20 - eegWs.baselineSeconds() | number:'1.0-0' }}</strong><span>seconds left</span></div>
              <div class="progress-track"><div class="progress-fill" [style.width.%]="(eegWs.baselineSeconds() / 20) * 100"></div></div>
              @if (!eegWs.allSensorsGood()) { <div class="alert alert-warning">Signal lost. Restarting baseline. สัญญาณหลุด ระบบจะเริ่มนับใหม่</div> }
            }

            @case ('ready') {
              <span class="eyebrow">Story Setup</span>
              <h2>Ready to record emotion</h2>
              <p>ใส่โครงเรื่องสั้น ๆ และเลือก persona ก่อนบันทึก EEG 30 วินาที</p>
              <div class="form-group">
                <label class="form-label" for="input-story">Story seed</label>
                <textarea id="input-story" class="form-textarea" [(ngModel)]="inputStory" placeholder="เช่น เด็กหญิงพบหนังสือเรืองแสงและถูกพาเข้าสู่โลกความฝัน"></textarea>
              </div>
              <div class="form-group">
                <label class="form-label" for="persona-select">Persona</label>
                <select id="persona-select" class="form-select" [(ngModel)]="selectedPersonaId">
                  <option [ngValue]="null">No persona selected</option>
                  @for (p of personas(); track p.id) { <option [ngValue]="p.id">{{ p.persona_name }} · {{ p.art_style }}</option> }
                </select>
              </div>
              <button class="btn btn-primary btn-lg" (click)="startRecording()" [disabled]="!inputStory.trim()">Start Recording</button>
            }

            @case ('record') {
              <span class="eyebrow">Emotion Recording</span>
              <h2>{{ currentPhase() === 'PAUSED_SIGNAL_QUALITY' ? 'Paused by signal quality' : 'Recording clean EEG' }}</h2>
              <p>ระบบจะนับเฉพาะช่วงที่สัญญาณ Good ครบทั้ง 4 จุด ช่วง poor/stale จะถูกตัดทิ้งและหยุดเวลาไว้</p>
              <div class="record-meter">
                <strong>{{ eegWs.acceptedSeconds() | number:'1.0-0' }} / 30 sec</strong>
                <div class="progress-track"><div class="progress-fill" [class.paused]="currentPhase() === 'PAUSED_SIGNAL_QUALITY'" [style.width.%]="(eegWs.acceptedSeconds() / 30) * 100"></div></div>
                <small>Wall clock {{ eegWs.wallClockSeconds() | number:'1.0-0' }} / 120 sec</small>
              </div>
              @if (currentPhase() === 'PAUSED_SIGNAL_QUALITY') { <div class="alert alert-warning">Paused at {{ eegWs.acceptedSeconds() | number:'1.0-0' }} sec — ปรับสายคาดและรอให้ Good ครบ 4 จุด</div> }
              <button class="btn btn-destructive btn-sm" (click)="cancelSession()">Cancel Session</button>
            }

            @case ('emotion') {
              <span class="eyebrow">EEG Result</span>
              <h2>Confirm emotion</h2>
              <div class="emotion-card"><span>{{ emotionEmoji(detectedEmotion()) }}</span><strong>{{ detectedEmotion() || 'Analyzed emotion' }}</strong><small>ยืนยันผลเพื่อสร้างคอมิกจากอารมณ์นี้</small></div>
              <div class="inline-actions"><button class="btn btn-primary btn-lg" (click)="confirmEmotion()">Generate Comic</button><button class="btn btn-secondary" (click)="remeasure()">Remeasure</button></div>
            }

            @case ('generate') {
              <span class="eyebrow">Generating Comic</span>
              <h2>Creating your Dream Comic</h2>
              <div class="timeline"><span class="done">Analyze EEG Emotion</span><span class="done">Create Story with Gemini</span><span>Generate Comic Panels</span><span>Save Result</span></div>
              <div class="alert alert-info"><span class="spinner"></span> กำลังสร้างคอมิก 4 ช่องผ่าน ComfyUI local</div>
            }

            @default {
              <span class="eyebrow">Session</span>
              <h2>{{ currentPhase() }}</h2>
              <p>{{ eegWs.latestMessage()?.reason || 'ระบบกำลังรอสถานะจาก backend' }}</p>
              <button class="btn btn-secondary" (click)="restart()">Restart Session</button>
            }
          }
        </article>
      </section>

      <p class="entertainment-note">
        ข้อมูลอารมณ์ใช้เพื่อสร้างสรรค์คอมิกและความบันเทิง ไม่ใช่การวินิจฉัยทางการแพทย์
      </p>
    </main>
  `,
  styles: [`
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
    .step.active { color:#fff; } .step.active .step-index { background:var(--color-primary); }
    .step.done { color:#BBF7D0; } .step.done .step-index { color:#052E16; background:var(--color-success); }
    .setup-card { display:grid; grid-template-columns:minmax(0, 42%) minmax(0, 58%); overflow:hidden; border:1px solid var(--color-border); border-radius:16px; background:var(--color-surface); box-shadow:0 18px 48px rgba(2,6,23,.22); }
    app-horseshoe-sensor { min-width:0; padding:30px; border-right:1px solid var(--color-border); background:#0E1628; }
    .stage-panel { min-width:0; min-height:590px; display:flex; flex-direction:column; gap:18px; padding:42px; }
    .stage-panel h2,.stage-panel > p:not(.section-kicker) { margin:0; }
    .device-list,.timeline { display:grid; gap:10px; margin-top:6px; }
    .device-option { min-height:64px; width:100%; display:grid; grid-template-columns:30px 1fr; align-items:center; gap:12px; padding:11px 14px; text-align:left; color:var(--color-text-primary); border:1px solid var(--color-border); border-radius:10px; background:#141E32; cursor:pointer; }
    .device-option:hover,.device-option:focus-visible { border-color:var(--color-border-strong); }
    .device-option:focus-visible,.primary-action:focus-visible { outline:3px solid rgba(196,181,253,.35); outline-offset:2px; }
    .device-option.selected { border-color:var(--color-primary); background:rgba(124,58,237,.09); }
    .device-mark { width:22px; height:22px; display:grid; place-items:center; border:1px solid #64748B; border-radius:50%; }
    .device-option.selected .device-mark { border-color:var(--color-primary); background:var(--color-primary); }
    .device-option strong,.device-option small { display:block; } .device-option small { margin-top:3px; color:var(--color-text-muted); }
    .inline-message { padding:13px 15px; border-left:3px solid var(--color-secondary); background:rgba(167,139,250,.06); color:var(--color-text-secondary); }
    .inline-message.warning { border-left-color:var(--color-warning); background:rgba(245,158,11,.06); }
    .primary-action { width:100%; min-height:50px; margin-top:auto; color:#fff; background:var(--color-primary); border-radius:10px; }
    .primary-action:hover:not(:disabled) { background:var(--color-primary-hover); }
    .fitting-list { display:grid; gap:14px; margin:4px 0; padding:0; list-style:none; }
    .fitting-list li { display:grid; grid-template-columns:30px 1fr; align-items:center; gap:12px; color:var(--color-text-secondary); }
    .fitting-list li span { width:28px; height:28px; display:grid; place-items:center; border:1px solid var(--color-border-strong); border-radius:50%; color:var(--color-secondary); font-weight:700; }
    .entertainment-note { margin:0; text-align:center; color:var(--color-text-muted); font-size:.78rem; }
    .timer-block { display:grid; place-items:center; padding:28px; border-radius:22px; background:rgba(244,114,182,.09); border:1px solid rgba(244,114,182,.2); }
    .timer-block strong { font:800 4rem var(--font-en); line-height:1; }
    .record-meter { display:grid; gap:10px; padding:18px; border:1px solid var(--color-border); border-radius:18px; background:rgba(15,23,42,.55); }
    .record-meter strong { font:800 1.45rem var(--font-en); } .record-meter small { color:var(--color-text-muted); font-size:.82rem; }
    .emotion-card { display:grid; place-items:center; gap:8px; padding:32px; border:1px solid var(--color-border); border-radius:22px; background:rgba(11,16,32,.45); text-align:center; }
    .emotion-card span { font-size:4rem; } .emotion-card strong { font:800 1.5rem var(--font-en); } .emotion-card small { color:var(--color-text-muted); }
    .inline-actions { display:flex; gap:12px; flex-wrap:wrap; }
    .timeline span { padding:12px 14px; border:1px solid var(--color-border); border-radius:14px; color:var(--color-text-muted); background:rgba(15,23,42,.48); }
    .timeline span.done { color:#BBF7D0; border-color:rgba(34,197,94,.35); }
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
  `],
})
export class EegSessionComponent implements OnInit, OnDestroy {
  currentPhase = computed(() => this.eegWs.phase());
  scanning = signal(false);
  scanError = signal('');
  generating = signal(false);
  discoveredDevices = signal<{ name: string; address: string }[]>([]);
  selectedDevice = signal<{ name: string; address: string } | null>(null);
  personas = signal<Persona[]>([]);
  detectedEmotion = signal('');
  selectedPersonaId: number | null = null;
  inputStory = '';
  hairType: 'short' | 'long' = 'short';
  sessionId = signal<string | null>(null);
  dbSessionId = signal<number | null>(null);

  readonly steps = [
    { key: 'connect', label: 'เชื่อมต่อ' },
    { key: 'signal', label: 'ตรวจสัญญาณ' },
    { key: 'emotion', label: 'บันทึกอารมณ์' },
    { key: 'comic', label: 'สร้างคอมิก' },
  ];

  constructor(readonly eegWs: EegWsService, private http: HttpClient, private personaService: PersonaService, private comicService: ComicService, private router: Router) {}
  ngOnInit() { this.personaService.getAll().subscribe((p) => this.personas.set(p)); this.createSession(); }
  ngOnDestroy() { this.eegWs.disconnect(); }

  stage = computed(() => {
    if (this.generating()) return 'generate';
    const p = this.currentPhase();
    if (p === 'DISCOVERING' || p === 'DEVICE_CONFIRMATION' || p === 'CONNECTING') return 'device';
    if (p === 'PREPARATION' || p === 'FITTING') return 'prepare';
    if (p === 'BASELINE') return 'baseline';
    if (p === 'READY') return 'ready';
    if (p === 'RECORDING' || p === 'PAUSED_SIGNAL_QUALITY') return 'record';
    if (p === 'EMOTION_CONFIRMATION' || p === 'COMPLETED') return 'emotion';
    return 'fallback';
  });
  activeStepKey = computed(() => ({ device: 'connect', prepare: 'signal', baseline: 'signal', ready: 'emotion', record: 'emotion', emotion: 'emotion', generate: 'comic', fallback: 'connect' }[this.stage()] ?? 'connect'));
  stepDone(key: string) { return this.steps.findIndex((s) => s.key === key) < this.steps.findIndex((s) => s.key === this.activeStepKey()); }

  private createSession() {
    this.http.post<{ id: number }>(`${environment.apiUrl}/sessions`, {}).subscribe({
      next: (s) => { this.dbSessionId.set(s.id); this.sessionId.set(String(s.id)); this.eegWs.connect(String(s.id)); },
      error: () => { this.sessionId.set('local-dev'); },
    });
  }
  scanDevices() {
    this.scanning.set(true);
    this.scanError.set('');
    this.discoveredDevices.set([]);
    this.selectedDevice.set(null);
    this.http.get<{ devices: { name: string; address: string }[] }>(`${environment.apiUrl}/sessions/scan`).subscribe({
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
  selectDevice(d: { name: string; address: string }) { this.selectedDevice.set(d); }
  confirmDevice() {
    const d = this.selectedDevice(); if (!d) return;
    if (this.sessionId()) this.http.post(`${environment.apiUrl}/sessions/${this.sessionId()}/confirm-device`, null, { params: { device_name: d.name, device_id: d.address } }).subscribe();
    this.eegWs.sendCommand('confirm_device', { device_name: d.name, device_id: d.address });
  }
  startBaseline() { if (this.sessionId()) this.http.post(`${environment.apiUrl}/sessions/${this.sessionId()}/start-baseline`, {}).subscribe(); this.eegWs.sendCommand('start_baseline'); }
  startRecording() { if (this.sessionId()) this.http.post(`${environment.apiUrl}/sessions/${this.sessionId()}/start-recording`, {}).subscribe(); this.eegWs.sendCommand('start_recording'); }
  cancelSession() { if (this.sessionId()) this.http.post(`${environment.apiUrl}/sessions/${this.sessionId()}/cancel`, {}).subscribe(); this.eegWs.disconnect(); this.router.navigate(['/dashboard']); }
  confirmEmotion() {
    if (!this.sessionId()) return;
    this.http.post<{ final_emotion?: string }>(`${environment.apiUrl}/sessions/${this.sessionId()}/confirm-emotion`, {}).subscribe({
      next: (result) => { this.detectedEmotion.set(result.final_emotion ?? 'excited'); this.generateComic(); },
      error: () => { this.detectedEmotion.set('excited'); this.generateComic(); },
    });
  }
  remeasure() { this.eegWs.sendCommand('remeasure'); }
  restart() { this.eegWs.disconnect(); this.createSession(); }
  private generateComic() {
    const sessionId = this.dbSessionId(); if (!sessionId) return;
    this.generating.set(true);
    this.comicService.generate({ session_id: sessionId, persona_id: this.selectedPersonaId ?? undefined, input_story: this.inputStory, art_style: this.selectedPersonaForStyle() }).subscribe({
      next: (comic) => { this.generating.set(false); this.router.navigate(['/comic', comic.id]); },
      error: () => this.generating.set(false),
    });
  }
  private selectedPersonaForStyle(): string { const p = this.personas().find((x) => x.id === this.selectedPersonaId); return p?.art_style ?? 'Manga'; }
  emotionEmoji(e: string) { return ({ happy: '😊', sad: '😢', stressed: '⚡', excited: '✨' } as Record<string, string>)[e] ?? '🧠'; }
}
