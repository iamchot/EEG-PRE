import { CommonModule } from '@angular/common';
import { Component, OnDestroy, OnInit, effect, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { Subscription } from 'rxjs';

import {
  ArtifactRequest,
  BaselineKind,
  CollectionRunnerState,
  DatasetCollectionService,
} from '../../core/services/dataset-collection.service';
import { DatasetCollectionWsService } from '../../core/services/dataset-collection-ws.service';
import { HorseshoeSensorComponent } from '../../shared/components/horseshoe-sensor/horseshoe-sensor.component';

type RunnerStage = 'device' | 'eyes_open' | 'eyes_closed' | 'ready' | 'rest' | 'stimulus' |
  'rating' | 'break' | 'completed' | 'interrupted' | 'failed';

@Component({
  selector: 'app-dataset-collection-runner',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink, HorseshoeSensorComponent],
  template: `
    <main class="runner-shell">
      <header class="runner-header">
        <div>
          <a routerLink="/admin/dataset-collection" class="back-link">← EEG Dataset Collection</a>
          <p class="eyebrow">Admin collection workspace</p>
          <h1>Creative Headset Setup</h1>
          <p>Session {{ sessionId }} · Trial {{ displayedTrialOrder() }} / 12</p>
        </div>
        <aside class="notice" data-testid="non-medical-notice">
          For entertainment and prototype research only — not medical diagnosis or treatment.
        </aside>
      </header>

      <div class="connection" role="status" aria-live="polite">
        <span [class.online]="ws.isConnected()"></span>
        {{ ws.isConnected() ? 'Live state connected' : 'Using persisted runner state' }}
      </div>
      @if (error()) { <div class="error" role="alert">{{ error() }}</div> }

      <section class="progress-card" aria-label="Collection progress">
        <div><span>Progress</span><strong>Trial {{ displayedTrialOrder() }} / 12</strong></div>
        <progress [value]="runnerState()?.completed_trials ?? 0" max="12">{{ runnerState()?.completed_trials ?? 0 }} of 12</progress>
      </section>

      @switch (stage()) {
        @case ('device') {
          <section class="workspace" data-stage="device">
            <app-horseshoe-sensor />
            <form class="action-card" (ngSubmit)="selectDevice()">
              <p class="step">Step 1</p><h2>ค้นหาและเลือก Muse</h2>
              <p>วาง Muse 2 ใกล้เครื่องคอมพิวเตอร์ เปิดอุปกรณ์ แล้วระบุอุปกรณ์สำหรับ Session นี้</p>
              <label for="device-id">Device ID<input id="device-id" name="deviceId" required [(ngModel)]="deviceId" placeholder="เช่น Muse-2-A1"></label>
              <label for="device-name">Device label<input id="device-name" name="deviceName" required [(ngModel)]="deviceName"></label>
              <button class="primary" type="submit" [disabled]="busy() || !deviceId.trim()">เลือกอุปกรณ์</button>
              <button type="button" (click)="startBaseline('eyes_open')" [disabled]="busy()">เริ่ม Baseline ลืมตา</button>
              <p class="hint">Baseline ลืมตาต้องมาก่อน Baseline หลับตาเสมอ</p>
            </form>
          </section>
        }
        @case ('eyes_open') {
          <app-horseshoe-sensor />
          <section class="focus-card" data-stage="eyes_open" aria-live="polite">
            <p class="step">Baseline 1 of 2</p><h2>ลืมตาและมองจุดกึ่งกลาง</h2>
            <div class="target-grid"><strong>60 วินาที</strong><span>เวลาบันทึกทั้งหมด</span><strong>30 วินาที</strong><span>สัญญาณสะอาดขั้นต่ำ</span></div>
            <p>{{ seconds(runnerState()?.wall_clock_seconds) }}s wall · {{ seconds(runnerState()?.accepted_clean_seconds) }}s clean</p>
          </section>
        }
        @case ('eyes_closed') {
          <app-horseshoe-sensor />
          <section class="focus-card" data-stage="eyes_closed" aria-live="polite">
            <p class="step">Baseline 2 of 2</p><h2>หลับตาและอยู่นิ่ง</h2>
            <div class="target-grid"><strong>60 วินาที</strong><span>เวลาบันทึกทั้งหมด</span><strong>30 วินาที</strong><span>สัญญาณสะอาดขั้นต่ำ</span></div>
            @if (runnerState()?.active_baseline === 'eyes_closed') {
              <p>{{ seconds(runnerState()?.wall_clock_seconds) }}s wall · {{ seconds(runnerState()?.accepted_clean_seconds) }}s clean</p>
            } @else {
              <button class="primary" type="button" (click)="startBaseline('eyes_closed')" [disabled]="busy()">เริ่ม Baseline หลับตา</button>
            }
          </section>
        }
        @case ('ready') {
          <section class="focus-card" data-stage="ready"><p class="step">พร้อมเก็บ Trial</p><h2>Trial {{ displayedTrialOrder() }} / 12</h2>
            <p>คลิปถัดไป: {{ runnerState()?.next_stimulus_title ?? 'รอข้อมูลคลิป' }}</p>
            <button class="primary" type="button" (click)="startNextTrial()" [disabled]="busy() || !runnerState()?.next_trial_id">เริ่มช่วงพักก่อนคลิป</button>
          </section>
        }
        @case ('rest') {
          <section class="media-layout" data-stage="rest">
            <div class="focus-card"><p class="step">Rest / Fixation</p><h2>มองจุดกึ่งกลางและอยู่นิ่ง</h2><div class="fixation" aria-label="Fixation point">+</div><p>เป้าหมาย 10–15 วินาที · Backend: {{ seconds(runnerState()?.wall_clock_seconds) }}s</p></div>
            <ng-container *ngTemplateOutlet="mediaPanel"></ng-container>
          </section>
        }
        @case ('stimulus') {
          <section class="media-layout" data-stage="stimulus"><ng-container *ngTemplateOutlet="mediaPanel"></ng-container>
            <aside class="artifact-card"><h2>Artifact marker</h2><label for="artifact-note">หมายเหตุ (ไม่บังคับ)<input id="artifact-note" [(ngModel)]="artifactNote"></label>
              <div class="artifact-grid">@for (item of artifacts; track item.type) { <button type="button" (click)="markArtifact(item.type)">{{ item.label }}</button> }</div>
            </aside>
          </section>
        }
        @case ('rating') {
          <form class="rating-card" data-stage="rating" (ngSubmit)="submitRating()">
            <p class="step">Self-rating</p><h2>บันทึกความรู้สึกของผู้เข้าร่วม</h2>
            <label for="valence">Valence (1–9)<input id="valence" name="valence" type="number" min="1" max="9" required [(ngModel)]="valence"></label>
            <label for="arousal">Arousal (1–9)<input id="arousal" name="arousal" type="number" min="1" max="9" required [(ngModel)]="arousal"></label>
            <label for="confidence">Confidence (1–5)<input id="confidence" name="confidence" type="number" min="1" max="5" required [(ngModel)]="confidence"></label>
            <button class="primary" type="submit" [disabled]="busy() || !ratingsValid()">บันทึกคะแนน</button>
          </form>
        }
        @case ('break') {
          <section class="focus-card" data-stage="break"><p class="step">พักกลาง Session</p><h2>ครบ Trial 6 แล้ว</h2><p>พัก 3–5 นาที ตรวจความสบายและตำแหน่ง Muse ก่อนทำ Trial 7 ต่อ</p>
            <button class="primary" type="button" (click)="startNextTrial()" [disabled]="busy()">เริ่ม Trial 7</button>
          </section>
        }
        @case ('completed') { <section class="focus-card success" data-stage="completed"><h2>เก็บข้อมูลครบ 12 Trial</h2><p>ข้อมูลที่ commit แล้วพร้อมสำหรับขั้นตอนตรวจสอบ Dataset</p><a routerLink="/admin/dataset-collection">กลับหน้าสรุป</a></section> }
        @case ('interrupted') { <section class="focus-card warning" data-stage="interrupted"><h2>Session ถูกขัดจังหวะ</h2><p>{{ runnerState()?.interruption_reason }}</p><p>เริ่ม Trial {{ displayedTrialOrder() }} ใหม่ในลำดับเดิม โดยไม่สุ่ม Schedule ใหม่</p><button class="primary" type="button" (click)="resume()" [disabled]="busy()">Resume same order</button></section> }
        @case ('failed') { <section class="focus-card danger" data-stage="failed"><h2>ไม่สามารถดำเนิน Session ต่อได้</h2><p>ตรวจอุปกรณ์และสถานะไฟล์ก่อนกลับมาลองใหม่</p></section> }
      }

      @if (canEmergencyStop()) { <button class="emergency" type="button" (click)="emergencyStop()" [disabled]="busy()">Emergency stop</button> }

      <ng-template #mediaPanel>
        <section class="media-card">
          <div><p class="step">Approved stimulus</p><h2>{{ runnerState()?.current_stimulus_title }}</h2></div>
          @if (mediaError()) { <div class="error" role="alert">โหลดคลิปไม่สำเร็จ — จะยังไม่เริ่มบันทึก stimulus</div> }
          @if (mediaUrl(); as source) { <video controls preload="auto" [src]="source" (playing)="onPlaying()" (ended)="onEnded()" (error)="onMediaError()" aria-label="Approved entertainment stimulus"></video> }
          @else if (!mediaError()) { <p role="status">กำลังโหลดคลิปที่ผ่านการอนุมัติ…</p> }
        </section>
      </ng-template>
    </main>
  `,
  styleUrl: './dataset-collection-runner.component.css',
})
export class DatasetCollectionRunnerComponent implements OnInit, OnDestroy {
  readonly runnerState = signal<CollectionRunnerState | null>(null);
  readonly stage = signal<RunnerStage>('device');
  readonly error = signal('');
  readonly busy = signal(false);
  readonly mediaUrl = signal<string | null>(null);
  readonly mediaReady = signal(false);
  readonly mediaError = signal(false);
  readonly artifacts = [
    { type: 'blink', label: 'กะพริบตาถี่' }, { type: 'cough', label: 'ไอ' },
    { type: 'talk', label: 'พูด' }, { type: 'head_movement', label: 'ขยับศีรษะ' },
    { type: 'touch_device', label: 'สัมผัสอุปกรณ์' }, { type: 'device_loss', label: 'อุปกรณ์หลุด' },
  ];
  readonly sessionId: number;
  deviceId = '';
  deviceName = 'Muse 2';
  artifactNote = '';
  valence = 5;
  arousal = 5;
  confidence = 3;
  private mediaStimulusId: number | null = null;
  private mediaSubscription?: Subscription;
  private actionSubscription?: Subscription;
  private playbackStarted = false;
  private playbackFinished = false;

  constructor(
    route: ActivatedRoute,
    private readonly api: DatasetCollectionService,
    readonly ws: DatasetCollectionWsService,
  ) {
    this.sessionId = Number(route.snapshot.paramMap.get('id'));
    effect(() => { const state = this.ws.state(); if (state) this.applyState(state); });
  }

  ngOnInit(): void {
    if (!Number.isSafeInteger(this.sessionId) || this.sessionId <= 0) { this.error.set('Session ID ไม่ถูกต้อง'); this.stage.set('failed'); return; }
    this.api.getRunnerState(this.sessionId).subscribe({ next: state => this.applyState(state), error: err => this.fail(err) });
    this.ws.connect(this.sessionId);
  }

  ngOnDestroy(): void { this.ws.disconnect(); this.actionSubscription?.unsubscribe(); this.releaseMedia(); }

  applyState(state: CollectionRunnerState): void {
    this.runnerState.set(state);
    this.stage.set(this.resolveStage(state));
    const stimulusId = state.current_stimulus_id;
    if (stimulusId && (state.trial_state === 'rest' || state.trial_state === 'stimulus')) this.loadMedia(stimulusId);
    else this.releaseMedia();
  }

  displayedTrialOrder(): number { return this.runnerState()?.current_trial_order ?? this.runnerState()?.next_trial_order ?? 12; }
  seconds(value?: number): string { return Math.max(0, value ?? 0).toFixed(1); }

  selectDevice(): void {
    if (!this.deviceId.trim()) return;
    this.run(this.api.selectDevice(this.sessionId, { device_id: this.deviceId.trim(), device_name: this.deviceName.trim() || 'Muse 2' }));
  }

  startBaseline(kind: BaselineKind): void {
    const state = this.runnerState();
    if (kind === 'eyes_closed' && state?.state !== 'baseline') return;
    this.run(this.api.startBaseline(this.sessionId, kind));
  }

  startNextTrial(): void {
    const trialId = this.runnerState()?.next_trial_id;
    if (trialId) this.run(this.api.startTrialRest(this.sessionId, trialId));
  }

  onPlaying(): void {
    const state = this.runnerState();
    if (!this.mediaReady() || this.mediaError() || this.playbackStarted || state?.trial_state !== 'rest' || !state.current_trial_id) return;
    this.playbackStarted = true;
    this.run(this.api.startStimulus(this.sessionId, state.current_trial_id), () => this.playbackStarted = false);
  }

  onEnded(): void {
    const state = this.runnerState();
    if (this.playbackFinished || state?.trial_state !== 'stimulus' || !state.current_trial_id) return;
    this.playbackFinished = true;
    this.run(this.api.finishStimulus(this.sessionId, state.current_trial_id), () => this.playbackFinished = false);
  }

  onMediaError(): void { this.mediaReady.set(false); this.mediaError.set(true); }

  markArtifact(eventType: string): void {
    const state = this.runnerState();
    if (state?.trial_state !== 'stimulus' || !state.current_trial_id) return;
    const body: ArtifactRequest = { event_type: eventType, note: this.artifactNote.trim() || null };
    this.run(this.api.markArtifact(this.sessionId, state.current_trial_id, body));
    this.artifactNote = '';
  }

  ratingsValid(): boolean { return this.inRange(this.valence, 1, 9) && this.inRange(this.arousal, 1, 9) && this.inRange(this.confidence, 1, 5); }

  submitRating(): void {
    const state = this.runnerState();
    if (state?.trial_state !== 'rating' || !state.current_trial_id || !this.ratingsValid()) return;
    this.run(this.api.submitRating(this.sessionId, state.current_trial_id, { valence: this.valence, arousal: this.arousal, confidence: this.confidence }));
  }

  resume(): void { if (this.runnerState()?.state === 'interrupted') this.run(this.api.resume(this.sessionId)); }

  emergencyStop(): void {
    if (!this.canEmergencyStop() || !window.confirm('ยืนยัน Emergency stop? Trial หรือ Baseline ปัจจุบันจะถูกขัดจังหวะ')) return;
    this.run(this.api.interrupt(this.sessionId, { reason: 'Emergency stop confirmed by Admin' }));
  }

  canEmergencyStop(): boolean { const state = this.runnerState(); return state?.state === 'baseline' || (state?.state === 'in_progress' && !!state.current_trial_id); }

  private resolveStage(state: CollectionRunnerState): RunnerStage {
    if (state.state === 'completed') return 'completed';
    if (state.state === 'interrupted') return 'interrupted';
    if (state.state === 'failed' || state.state === 'withdrawn' || state.file_recovery_required) return 'failed';
    if (state.active_baseline === 'eyes_open') return 'eyes_open';
    if (state.active_baseline === 'eyes_closed') return 'eyes_closed';
    if (state.state === 'preparation') return 'device';
    if (state.state === 'baseline') return 'eyes_closed';
    if (state.trial_state === 'rest') return 'rest';
    if (state.trial_state === 'stimulus') return 'stimulus';
    if (state.trial_state === 'rating') return 'rating';
    if (state.break_required) return 'break';
    return 'ready';
  }

  private loadMedia(stimulusId: number): void {
    if (this.mediaStimulusId === stimulusId && (this.mediaUrl() || this.mediaError())) return;
    this.releaseMedia();
    this.mediaStimulusId = stimulusId;
    this.mediaReady.set(false); this.mediaError.set(false); this.playbackStarted = false; this.playbackFinished = false;
    this.mediaSubscription = this.api.getStimulusMedia(stimulusId).subscribe({
      next: blob => { if (this.mediaStimulusId !== stimulusId) return; this.mediaUrl.set(URL.createObjectURL(blob)); this.mediaReady.set(true); },
      error: () => { if (this.mediaStimulusId === stimulusId) { this.mediaReady.set(false); this.mediaError.set(true); } },
    });
  }

  private releaseMedia(): void {
    this.mediaSubscription?.unsubscribe(); this.mediaSubscription = undefined;
    const url = this.mediaUrl(); if (url) URL.revokeObjectURL(url);
    this.mediaUrl.set(null); this.mediaReady.set(false); this.mediaError.set(false); this.mediaStimulusId = null;
    this.playbackStarted = false; this.playbackFinished = false;
  }

  private run(request: ReturnType<DatasetCollectionService['getRunnerState']>, reset?: () => void): void {
    if (this.busy()) return;
    this.busy.set(true); this.error.set('');
    this.actionSubscription = request.subscribe({
      next: state => { this.busy.set(false); this.applyState(state); },
      error: err => { this.busy.set(false); reset?.(); this.fail(err); },
    });
  }

  private inRange(value: number, min: number, max: number): boolean { return Number.isInteger(value) && value >= min && value <= max; }
  private fail(err: unknown): void { const value = err as { error?: { detail?: string }; message?: string }; this.error.set(value.error?.detail ?? value.message ?? 'ไม่สามารถดำเนินการได้'); }
}
