import { CommonModule } from '@angular/common';
import { Component, OnDestroy, OnInit, Optional, effect, signal } from '@angular/core';
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
import { SensorStatus } from '../../core/services/eeg-ws.service';
import { HorseshoeSensorComponent, SensorKey } from '../../shared/components/horseshoe-sensor/horseshoe-sensor.component';
import { EegWaveformComponent } from '../../shared/components/eeg-waveform/eeg-waveform.component';
import { MuseDevice, MuseDeviceService, MuseConnectionStatus } from '../../core/services/muse-device.service';

import { TranslatePipe } from '../../core/pipes/translate.pipe';
import { LanguageService, toThaiError } from '../../core/services/language.service';
import { MuseWebBluetoothService } from '../../core/services/muse-web-bluetooth.service';

type RunnerStage = 'device' | 'eyes_open' | 'eyes_closed' | 'ready' | 'rest' | 'stimulus' |
  'rating' | 'break' | 'completed' | 'interrupted' | 'failed';

@Component({
  selector: 'app-dataset-collection-runner',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink, TranslatePipe, HorseshoeSensorComponent, EegWaveformComponent],
  templateUrl: './dataset-collection-runner.component.html',
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
  readonly finishRetryAvailable = signal(false);
  readonly autoplayBlocked = signal(false);
  readonly devicePersisted = signal(false);
  readonly contacts = signal<Record<SensorKey, boolean>>({ tp9: false, af7: false, af8: false, tp10: false });
  readonly sensorKeys: SensorKey[] = ['tp9', 'af7', 'af8', 'tp10'];
  readonly artifacts = [
    { type: 'blink', label: 'กะพริบตาถี่' }, { type: 'cough', label: 'ไอ' },
    { type: 'talk', label: 'พูด' }, { type: 'head_movement', label: 'ขยับศีรษะ' },
    { type: 'touch_device', label: 'สัมผัสอุปกรณ์' }, { type: 'device_loss', label: 'อุปกรณ์หลุด' },
  ];
  readonly sessionId: number;
  artifactNote = '';
  valence = 5;
  arousal = 5;
  confidence = 3;
  private mediaStimulusId: number | null = null;
  private mediaSubscription?: Subscription;
  private initialSubscription?: Subscription;
  private actionSubscription?: Subscription;
  private safetyInterruptSubscription?: Subscription;
  private playbackStarted = false;
  private playbackFinished = false;
  private pendingEnded = false;
  private playbackFailureHandled = false;
  private stimulusStarting = false;
  private destroyed = false;
  private activeVideo: HTMLVideoElement | null = null;
  private selectedMuse: MuseDevice | null = null;

  constructor(
    route: ActivatedRoute,
    private readonly api: DatasetCollectionService,
    readonly ws: DatasetCollectionWsService,
    readonly museBt: MuseWebBluetoothService,
    readonly lang: LanguageService,
    @Optional() readonly muse?: MuseDeviceService,
  ) {
    this.sessionId = Number(route.snapshot.paramMap.get('id'));
    effect(() => {
      const state = this.ws.state();
      if (state && !this.destroyed) {
        this.initialSubscription?.unsubscribe();
        this.initialSubscription = undefined;
        this.applyState(state);
      }
    });
    effect(() => {
      const connection = this.muse?.connectionStatus?.();
      const selected = this.selectedMuse;
      if (!this.destroyed && selected && !this.busy() && !this.devicePersisted()
        && connection?.owner?.kind === 'collection' && connection?.owner?.sessionId === this.sessionId
        && connection?.state === 'connected') {
        this.persistConnectedMuse(selected);
      }
    });
  }

  ngOnInit(): void {
    if (!Number.isSafeInteger(this.sessionId) || this.sessionId <= 0) { this.error.set('Session ID ไม่ถูกต้อง'); this.stage.set('failed'); return; }
    // If Muse 2 is already streaming via Web Bluetooth, route samples immediately to this session's WS
    if (this.museBt.state() === 'streaming') {
      this.museBt.setOnSample(sample => this.ws.sendEegSample(sample));
      this.devicePersisted.set(true);
    }
    this.initialSubscription = this.api.getRunnerState(this.sessionId).subscribe({
      next: state => { if (!this.destroyed && !this.ws.state()) this.applyState(state); },
      error: err => { if (!this.destroyed && !this.ws.state()) this.fail(err); },
    });
    this.ws.connect(this.sessionId);
  }

  ngOnDestroy(): void { this.destroyed = true; this.ws.disconnect(); this.initialSubscription?.unsubscribe(); this.actionSubscription?.unsubscribe(); this.safetyInterruptSubscription?.unsubscribe(); this.releaseMedia(); }

  applyState(state: CollectionRunnerState): void {
    if (state.state !== 'preparation' || (state.total_trials ?? 0) > 0 || state.eyes_open_complete) {
      this.devicePersisted.set(true);
    }
    if (state.eyes_open_complete) {
      this.contacts.set({ tp9: true, af7: true, af8: true, tp10: true });
    }
    this.runnerState.set(state);
    const newStage = this.resolveStage(state);
    this.stage.set(newStage);
    const stimulusId = state.current_stimulus_id;
    if (stimulusId && (state.trial_state === 'rest' || state.trial_state === 'stimulus')) {
      this.loadMedia(stimulusId);
    } else {
      this.releaseMedia();
    }
    if (state.trial_state === 'rest' && state.stimulus_start_ready && !this.busy() && !this.stimulusStarting && this.activeVideo) {
      this.triggerStimulusStart(this.activeVideo);
    }
    if (newStage === 'stimulus') {
      queueMicrotask(() => this.playStimulusVideo());
    }
  }

  displayedTrialOrder(): number { return this.runnerState()?.current_trial_order ?? this.runnerState()?.next_trial_order ?? 12; }
  trialProgressLabel(): string { return (this.runnerState()?.total_trials ?? 0) === 0 ? this.lang.t('runner.schedule_not_prepared') : `Trial ${this.displayedTrialOrder()} / 12`; }
  seconds(value?: number): string { return Math.max(0, value ?? 0).toFixed(1); }
  samplingRateLabel(): string {
    const rate = this.runnerState()?.sampling_rate_hz;
    return rate == null ? 'rate pending' : `${rate.toFixed(1)} Hz`;
  }

  sensorStatus(key: SensorKey): SensorStatus {
    return this.runnerState()?.sensors[key] ?? { state: 'unknown', quality_score: 0, timestamp: 0, sequence: 0 };
  }

  sensorQualityTone(key: SensorKey): 'good' | 'fair' | 'poor' | 'unknown' {
    const s = this.sensorStatus(key);
    if (!s || s.state === 'unknown' || s.timestamp === 0) return 'unknown';
    if (s.state === 'good' && s.quality_score >= 60) return 'good';
    if (s.quality_score >= 35) return 'fair';
    return 'poor';
  }

  sensorQualityScore(key: SensorKey): string {
    const s = this.sensorStatus(key);
    if (!s || s.state === 'unknown' || s.timestamp === 0) return 'รอสัญญาณ';
    return `${Math.round(s.quality_score)}%`;
  }

  sensorQualityLabel(key: SensorKey): string {
    const tone = this.sensorQualityTone(key);
    switch (tone) {
      case 'good': return 'สัญญาณดี';
      case 'fair': return 'สัญญาณปานกลาง';
      case 'poor': return 'แตะไม่สนิท';
      default: return 'รอสัญญาณ';
    }
  }

  setContact(key: SensorKey, confirmed: boolean): void { this.contacts.update(value => ({ ...value, [key]: confirmed })); }
  confirmAllContacts(): void { this.contacts.set({ tp9: true, af7: true, af8: true, tp10: true }); }
  isDeviceReady(): boolean { return this.devicePersisted() || this.museBt.state() === 'streaming'; }
  canStartBaseline(): boolean {
    // Admin manually confirms all 4 sensors are touching skin via checkboxes.
    // live_sensor_ready is NOT required here — EEG quality is checked during
    // baseline accumulation itself, not as a gate for starting it.
    const allContactsConfirmed = this.sensorKeys.every(key => this.contacts()[key]);
    const hasTrials = (this.runnerState()?.total_trials ?? 0) > 0;
    return this.isDeviceReady() && hasTrials
      && this.ws.isConnected() && allContactsConfirmed;
  }

  scanMuse(): void {
    if (this.muse && !this.museBt.isSupported) {
      this.muse.scan();
      return;
    }
    const sessionId = this.sessionId;
    this.busy.set(true);
    this.error.set('');
    this.museBt.connect((sample) => {
      // Stream EEG to Admin runner WS — backend routes into collection state machine
      this.ws.sendEegSample(sample);
    }).then((deviceName) => {
      this.busy.set(false);
      this.devicePersisted.set(true);
      if (this.runnerState()?.state === 'preparation') {
        // Persist connected device via API only in preparation stage
        this.run(
          this.api.selectDevice(sessionId, { device_id: deviceName, device_name: deviceName }),
          undefined,
          () => this.devicePersisted.set(true),
        );
      }
    }).catch((err: Error) => {
      this.busy.set(false);
      this.error.set(err.message ?? 'ไม่สามารถเชื่อมต่อ Muse 2 ได้');
    });
  }

  museConnectionLabel(): string {
    if (this.muse?.connectionStatus) {
      const status = this.muse.connectionStatus();
      if (status && status.state !== 'idle') return this.connectionStageLabel(status);
    }
    const st = this.museBt.state();
    const labels: Record<string, string> = {
      idle: 'No Muse connected',
      requesting: 'Opening Bluetooth picker…',
      connecting: 'Connecting to Muse 2…',
      streaming: `Muse connected · ${this.museBt.deviceName() ?? ''}`,
      failed: 'Muse connection unavailable',
    };
    return labels[st] ?? 'No Muse connected';
  }

  private connectionStageLabel(status: MuseConnectionStatus): string {
    switch (status.state) {
      case 'starting_bridge': return 'Starting Muse bridge';
      case 'connecting_bluetooth': return 'Connecting Bluetooth';
      case 'waiting_for_lsl': return 'Waiting for LSL';
      case 'connected': return 'Muse connected';
      case 'failed': return 'Muse connection unavailable';
      case 'disconnecting': return 'Disconnecting Muse';
      default: return 'No Muse connected';
    }
  }

  onVideoReady(video: HTMLVideoElement): void {
    this.activeVideo = video;
    this.mediaReady.set(true);
    if (this.runnerState()?.trial_state === 'stimulus') {
      this.resumeAfterBackendStart(video);
    } else if (this.runnerState()?.trial_state === 'rest' && this.runnerState()?.stimulus_start_ready && !this.busy() && !this.stimulusStarting) {
      this.triggerStimulusStart(video);
    }
  }

  triggerStimulusStart(video?: HTMLVideoElement): void {
    const target = video ?? this.activeVideo;
    if (target) this.activeVideo = target;
    const state = this.runnerState();
    if (this.busy() || this.stimulusStarting) return;
    if (state?.trial_state === 'rest' && state.current_trial_id) {
      this.stimulusStarting = true;
      this.stopAllMedia(target ?? undefined);
      this.playbackStarted = true;
      this.run(
        this.api.startStimulus(this.sessionId, state.current_trial_id),
        () => {
          this.stimulusStarting = false;
          this.playbackStarted = false;
        },
        () => {
          this.stimulusStarting = false;
          this.resumeAfterBackendStart(target ?? this.activeVideo);
        },
      );
    } else {
      const active = target ?? (typeof document !== 'undefined' ? document.querySelector<HTMLVideoElement>('.video-shell video') : null);
      if (active) {
        this.stopAllMedia(active);
        void active.play().catch(() => this.handlePostStartPlaybackFailure(active));
      }
    }
  }

  restartRest(): void {
    if (this.busy() || this.runnerState()?.trial_state !== 'rest') return;
    this.run(
      this.api.interrupt(this.sessionId, { reason: 'Pre-stimulus rest timeout restart' }),
      undefined,
      () => {
        this.run(this.api.resume(this.sessionId));
      },
    );
  }

  connectMuse(device: unknown): void {
    const dev = device as MuseDevice | undefined;
    this.selectedMuse = dev ?? null;
    this.contacts.set({ tp9: false, af7: false, af8: false, tp10: false });
    this.devicePersisted.set(false);
    const current = this.runnerState();
    if (current) {
      const unknownSensors = Object.fromEntries(
        this.sensorKeys.map(k => [k, { state: 'unknown' as const, quality_score: 0, timestamp: 0, sequence: 0 }])
      ) as unknown as CollectionRunnerState['sensors'];
      this.runnerState.set({ ...current, sensors: unknownSensors });
    }
    if (dev && this.muse?.connectAdmin) {
      this.busy.set(true);
      this.error.set('');
      this.actionSubscription = this.muse.connectAdmin(this.sessionId, dev).subscribe({
        next: status => {
          this.busy.set(false);
          if (status.state === 'connected') {
            this.persistConnectedMuse(dev);
          } else if (status.state === 'failed') {
            this.error.set('ไม่สามารถเชื่อมต่ออุปกรณ์ Muse ได้ (กรุณาตรวจการเปิดเครื่องและบลูทูธ)');
          }
        },
        error: err => { this.busy.set(false); this.fail(err); },
      });
    }
  }

  private persistConnectedMuse(device: MuseDevice): void {
    this.run(
      this.api.selectDevice(this.sessionId, { device_id: device.address, device_name: device.name }),
      undefined,
      () => this.devicePersisted.set(true),
    );
  }

  prepareSchedule(): void {
    if (!this.isDeviceReady() || (this.runnerState()?.total_trials ?? 0) !== 0) return;
    this.run(this.api.createSchedule(this.sessionId));
  }

  startBaseline(kind: BaselineKind): void {
    const state = this.runnerState();
    if (!this.canStartBaseline() || (kind === 'eyes_closed' && state?.state !== 'baseline')) return;
    this.run(this.api.startBaseline(this.sessionId, kind));
  }

  startNextTrial(): void {
    const trialId = this.runnerState()?.next_trial_id;
    if (trialId) this.run(this.api.startTrialRest(this.sessionId, trialId));
  }

  canControlMedia(): boolean {
    const state = this.runnerState();
    return state?.trial_state === 'stimulus' || !!state?.stimulus_start_ready;
  }

  onPlaying(video?: HTMLVideoElement): void {
    if (video) this.activeVideo = video;
    const state = this.runnerState();
    if (state?.trial_state === 'stimulus' && this.playbackStarted) return;
    if (state?.trial_state === 'rest') {
      this.rewindMedia(video);
      if (state.stimulus_start_ready && !this.playbackStarted && !this.stimulusStarting) {
        this.triggerStimulusStart(video);
      }
      return;
    }
    if (state?.trial_state === 'stimulus') {
      this.playbackStarted = true;
      this.autoplayBlocked.set(false);
    }
  }

  private resumeAfterBackendStart(video: HTMLVideoElement | null): void {
    if (video && typeof (video as unknown as Node).isConnected === 'boolean' && !(video as unknown as Node).isConnected) {
      try {
        video.pause();
        video.currentTime = 0;
      } catch {}
    }
    const mounted = typeof document !== 'undefined' ? document.querySelector<HTMLVideoElement>('.video-shell video') : null;
    const target = (video && (typeof (video as unknown as Node).isConnected !== 'boolean' || (video as unknown as Node).isConnected)) ? video : (mounted ?? this.activeVideo);
    if (!target) return;
    this.activeVideo = target;
    const playPromise = target.play();
    if (playPromise !== undefined) {
      playPromise
        .then(() => {
          this.playbackStarted = true;
          this.autoplayBlocked.set(false);
        })
        .catch(() => this.handlePostStartPlaybackFailure(target));
    }
  }

  onEnded(): void {
    const state = this.runnerState();
    if (this.playbackFinished || state?.trial_state !== 'stimulus' || !state.current_trial_id) return;
    this.playbackFinished = true;
    this.pendingEnded = true;
    this.flushPendingFinish();
  }

  onMediaError(video?: HTMLVideoElement): void {
    const failedAfterBackendStart = this.runnerState()?.trial_state === 'stimulus';
    this.rewindMedia(video);
    this.mediaSubscription?.unsubscribe(); this.mediaSubscription = undefined;
    const url = this.mediaUrl(); if (url) URL.revokeObjectURL(url);
    this.mediaUrl.set(null); this.mediaReady.set(false); this.mediaError.set(true);
    if (failedAfterBackendStart) this.handlePostStartPlaybackFailure(video ?? this.activeVideo);
  }

  retryFinish(): void {
    if (!this.finishRetryAvailable() || this.runnerState()?.trial_state !== 'stimulus') return;
    this.finishRetryAvailable.set(false); this.pendingEnded = true; this.playbackFinished = true;
    this.flushPendingFinish();
  }

  markArtifact(eventType: string): void {
    const state = this.runnerState();
    if (this.busy() || state?.trial_state !== 'stimulus' || !state.current_trial_id) return;
    const submittedNote = this.artifactNote;
    const body: ArtifactRequest = { event_type: eventType, note: submittedNote.trim() || null };
    this.run(
      this.api.markArtifact(this.sessionId, state.current_trial_id, body),
      undefined,
      () => { if (this.artifactNote === submittedNote) this.artifactNote = ''; },
    );
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
    if (state.state === 'completed' || ((state.total_trials ?? 0) > 0 && (state.completed_trials ?? 0) >= (state.total_trials ?? 0))) return 'completed';
    if (state.state === 'interrupted') return 'interrupted';
    if (state.state === 'failed' || state.state === 'withdrawn' || state.file_recovery_required) return 'failed';

    if (state.trial_state === 'rating') return 'rating';
    if (state.trial_state === 'stimulus') return 'stimulus';
    if (state.trial_state === 'rest') return 'rest';
    if (state.break_required) return 'break';

    if (state.active_baseline === 'eyes_open') return 'eyes_open';
    if (state.active_baseline === 'eyes_closed') return 'eyes_closed';

    const eyesOpenDone = !!state.eyes_open_complete;
    const eyesClosedDone = !!state.eyes_closed_complete;

    if (eyesOpenDone && eyesClosedDone) return 'ready';
    if (eyesOpenDone && !eyesClosedDone) return 'eyes_closed';
    if (state.state === 'ready' || state.state === 'in_progress') return 'ready';
    if (state.state === 'baseline') return eyesOpenDone ? 'eyes_closed' : 'eyes_open';

    return 'device';
  }

  private loadMedia(stimulusId: number): void {
    if (this.mediaStimulusId === stimulusId && !this.mediaError()) return;
    this.releaseMedia();
    this.mediaStimulusId = stimulusId;
    this.mediaReady.set(false); this.mediaError.set(false); this.finishRetryAvailable.set(false); this.playbackStarted = false; this.playbackFinished = false; this.pendingEnded = false; this.playbackFailureHandled = false;
    this.mediaSubscription = this.api.getStimulusMedia(stimulusId).subscribe({
      next: blob => {
        if (this.mediaStimulusId !== stimulusId) return;
        this.mediaUrl.set(URL.createObjectURL(blob));
        this.mediaReady.set(true);
        if (this.runnerState()?.trial_state === 'stimulus') {
          queueMicrotask(() => this.playStimulusVideo());
        }
      },
      error: () => { if (this.mediaStimulusId === stimulusId) { this.mediaReady.set(false); this.mediaError.set(true); } },
    });
  }

  retryMediaDownload(): void {
    const stimulusId = this.runnerState()?.current_stimulus_id;
    if (stimulusId) {
      this.mediaStimulusId = null;
      this.loadMedia(stimulusId);
    }
  }

  private playStimulusVideo(video?: HTMLVideoElement): void {
    const state = this.runnerState();
    if (state && state.trial_state !== 'stimulus') return;
    const target = video ?? this.activeVideo ?? document.querySelector<HTMLVideoElement>('.video-shell video');
    if (!target) return;
    this.activeVideo = target;
    if (this.playbackStarted && !target.paused) return;
    const playPromise = target.play();
    if (playPromise !== undefined) {
      playPromise
        .then(() => {
          this.playbackStarted = true;
          this.autoplayBlocked.set(false);
        })
        .catch(err => {
          this.handlePostStartPlaybackFailure(target);
        });
    }
  }

  unblockAutoplay(video?: HTMLVideoElement): void {
    const target = video ?? this.activeVideo ?? document.querySelector<HTMLVideoElement>('.video-shell video');
    if (target) {
      void target.play().then(() => {
        this.playbackStarted = true;
        this.autoplayBlocked.set(false);
      }).catch(() => {});
    }
  }

  private stopAllMedia(except?: HTMLVideoElement): void {
    if (this.activeVideo && this.activeVideo !== except) {
      try {
        this.activeVideo.pause();
        this.activeVideo.currentTime = 0;
      } catch {}
    }
    if (typeof document !== 'undefined' && document.querySelectorAll) {
      document.querySelectorAll<HTMLVideoElement>('video').forEach(v => {
        if (v !== except) {
          try {
            v.pause();
            v.currentTime = 0;
          } catch {}
        }
      });
    }
  }

  private releaseMedia(): void {
    this.stopAllMedia();
    this.mediaSubscription?.unsubscribe(); this.mediaSubscription = undefined;
    const url = this.mediaUrl(); if (url) URL.revokeObjectURL(url);
    this.mediaUrl.set(null); this.mediaReady.set(false); this.mediaError.set(false); this.mediaStimulusId = null;
    this.playbackStarted = false; this.playbackFinished = false; this.pendingEnded = false;
    this.finishRetryAvailable.set(false); this.autoplayBlocked.set(false);
  }

  private flushPendingFinish(): void {
    const state = this.runnerState();
    if (!this.pendingEnded || this.busy() || state?.trial_state !== 'stimulus' || !state.current_trial_id) return;
    this.pendingEnded = false;
    this.run(
      this.api.finishStimulus(this.sessionId, state.current_trial_id),
      () => { this.finishRetryAvailable.set(true); },
      () => this.finishRetryAvailable.set(false),
    );
  }

  private handlePostStartPlaybackFailure(video: HTMLVideoElement | null): void {
    if (this.playbackFailureHandled) return;
    this.playbackFailureHandled = true;
    this.playbackStarted = false;
    this.pendingEnded = false;
    if (video) this.rewindMedia(video);
    const reason = 'Stimulus playback failed after Backend start';
    this.actionSubscription?.unsubscribe();
    this.actionSubscription = undefined;
    this.busy.set(true);
    this.error.set('');
    this.safetyInterruptSubscription = this.api.interrupt(this.sessionId, { reason }).subscribe({
      next: state => {
        this.busy.set(false);
        this.applyState(state);
        this.error.set('การเล่นวิดีโอคลิปล้มเหลว (Stimulus playback failed); collection was interrupted for recovery');
      },
      error: err => {
        this.busy.set(false);
        this.fail(err);
      },
    });
  }

  readonly toThaiError = toThaiError;

  private run(request: ReturnType<DatasetCollectionService['getRunnerState']>, onError?: () => void, onSuccess?: () => void): void {
    if (this.busy()) return;
    this.busy.set(true); this.error.set('');
    this.actionSubscription = request.subscribe({
      next: state => { this.busy.set(false); this.applyState(state); onSuccess?.(); this.flushPendingFinish(); },
      error: err => { this.busy.set(false); onError?.(); this.fail(err); this.flushPendingFinish(); },
    });
  }

  private inRange(value: number, min: number, max: number): boolean { return Number.isInteger(value) && value >= min && value <= max; }
  private rewindMedia(video?: HTMLVideoElement): void {
    const target = video ?? this.activeVideo;
    if (!target) return;
    target.pause();
    target.currentTime = 0;
  }
  private fail(err: unknown): void { this.error.set(toThaiError(err)); }
}
