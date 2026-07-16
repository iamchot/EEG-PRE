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
                  @for (device of discoveredDevices(); track device.address; let i = $index) {
                    <button
                      type="button"
                      class="device-option"
                      role="radio"
                      [attr.aria-checked]="selectedDevice()?.address === device.address"
                      [attr.tabindex]="selectedDevice() ? (selectedDevice()?.address === device.address ? 0 : -1) : (i === 0 ? 0 : -1)"
                      [class.selected]="selectedDevice()?.address === device.address"
                      (click)="selectDevice(device)"
                      (keydown)="onDeviceKeydown($event, i)"
                    >
                      <span class="device-mark" aria-hidden="true">{{ selectedDevice()?.address === device.address ? '✓' : '' }}</span>
                      <span><strong>{{ device.name }}</strong><small>{{ device.address }}</small></span>
                    </button>
                  }
                </div>
                <button id="btn-connect" class="btn primary-action" [disabled]="!selectedDevice()" (click)="confirmDevice()">
                  เชื่อมต่ออุปกรณ์
                </button>
                @if (connectionError()) {
                  <div class="inline-message" role="alert">{{ connectionError() }}</div>
                }
              } @else {
                @if (scanError()) {
                  <div class="inline-message" role="alert">{{ scanError() }}</div>
                }
                <button id="btn-scan" class="btn primary-action" (click)="scanDevices()" [disabled]="scanning() || !eegWs.isConnected()">
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
  styleUrl: './eeg-session.component.css',
})
export class EegSessionComponent implements OnInit, OnDestroy {
  currentPhase = computed(() => this.eegWs.phase());
  scanning = signal(false);
  scanError = signal('');
  connectionError = signal('');
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
    if (!this.eegWs.isConnected()) {
      this.scanning.set(false);
      return;
    }
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
  selectDevice(d: { name: string; address: string }) {
    this.selectedDevice.set(d);
    this.connectionError.set('');
  }
  onDeviceKeydown(event: KeyboardEvent, index: number) {
    const direction = ['ArrowDown', 'ArrowRight'].includes(event.key)
      ? 1
      : ['ArrowUp', 'ArrowLeft'].includes(event.key)
        ? -1
        : 0;
    if (!direction) return;

    event.preventDefault();
    const devices = this.discoveredDevices();
    if (!devices.length) return;
    const nextIndex = (index + direction + devices.length) % devices.length;
    this.selectDevice(devices[nextIndex]);
    const options = (event.currentTarget as HTMLElement)
      .closest('[role="radiogroup"]')
      ?.querySelectorAll<HTMLButtonElement>('[role="radio"]');
    options?.[nextIndex]?.focus();
  }
  confirmDevice() {
    const d = this.selectedDevice(); if (!d) return;
    this.connectionError.set('');
    const sendConfirmation = () => this.eegWs.sendCommand('confirm_device', {
      device_name: d.name,
      device_id: d.address,
    });
    if (!this.sessionId()) {
      sendConfirmation();
      return;
    }
    this.http.post(
      `${environment.apiUrl}/sessions/${this.sessionId()}/confirm-device`,
      null,
      { params: { device_name: d.name, device_id: d.address } },
    ).subscribe({
      next: sendConfirmation,
      error: () => this.connectionError.set(
        `เชื่อมต่อ ${d.name} ไม่สำเร็จ ตรวจสอบว่าอุปกรณ์ยังเปิดอยู่แล้วลองอีกครั้ง`,
      ),
    });
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
