import { DecimalPipe } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { Component, OnDestroy, OnInit, computed, effect, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { environment } from '../../../environments/environment';
import { EegWsService, SensorStatus } from '../../core/services/eeg-ws.service';
import { ComicService } from '../../core/services/comic.service';
import { PersonaService, Persona } from '../../core/services/persona.service';
import { HorseshoeSensorComponent } from '../../shared/components/horseshoe-sensor/horseshoe-sensor.component';
import { EegWaveformComponent } from '../../shared/components/eeg-waveform/eeg-waveform.component';
import { LanguageService, toThaiError } from '../../core/services/language.service';
import { TranslatePipe } from '../../core/pipes/translate.pipe';
import { MuseWebBluetoothService } from '../../core/services/muse-web-bluetooth.service';
import { AppSelectComponent, AppSelectOption } from '../../shared/components/app-select/app-select.component';

@Component({
  selector: 'app-eeg-session',
  standalone: true,
  imports: [FormsModule, DecimalPipe, HorseshoeSensorComponent, EegWaveformComponent, TranslatePipe, AppSelectComponent],
  templateUrl: './eeg-session.component.html',
  styleUrl: './eeg-session.component.css',
})
export class EegSessionComponent implements OnInit, OnDestroy {
  readonly lang = inject(LanguageService);
  readonly eegWs = inject(EegWsService);
  readonly museBt = inject(MuseWebBluetoothService);

  currentPhase = computed(() => this.eegWs.phase());
  generating = signal(false);
  generateError = signal('');
  connecting = signal(false);
  connectError = signal('');
  personas = signal<Persona[]>([]);
  readonly personaOptions = computed<AppSelectOption<number | null>[]>(() => {
    this.lang.currentLang();
    return [
      { value: null, label: this.lang.t('session.persona_none') },
      ...this.personas().map((p) => ({ value: p.id, label: p.persona_name })),
    ];
  });
  readonly artStyleOptions = computed<AppSelectOption<string>[]>(() =>
    this.artStyles.map((style) => ({ value: style, label: style }))
  );
  private confirmedEmotion = signal('');
  detectedEmotion = computed(() => this.confirmedEmotion() || this.eegWs.detectedEmotion());
  readonly artStyles = ['Webtoon', 'Manga', 'American Comic', 'Comic'] as const;
  selectedPersonaId: number | null = null;
  selectedArtStyle = 'Manga';
  inputStory = '';
  sessionId = signal<string | null>(null);
  dbSessionId = signal<number | null>(null);

  /** Accepted seconds from authoritative backend stream */
  readonly displayAcceptedSeconds = computed(() => this.eegWs.acceptedSeconds());

  readonly steps = computed(() => {
    this.lang.currentLang();
    return [
      { key: 'connect', label: this.lang.t('session.step1') },
      { key: 'signal', label: this.lang.t('session.step2') },
      { key: 'emotion', label: this.lang.t('session.step3') },
      { key: 'comic', label: this.lang.t('session.step4') },
    ];
  });

  /** Web Bluetooth convenience signals */
  readonly btState = this.museBt.state;
  readonly btError = this.museBt.error;
  readonly btDeviceName = this.museBt.deviceName;
  readonly isConnecting = computed(() =>
    this.btState() === 'requesting' || this.btState() === 'connecting'
  );
  readonly isStreaming = computed(() => this.btState() === 'streaming');
  readonly connectionStatus = computed(() => ({
    state: this.btState() === 'streaming' ? 'connected' : this.btState(),
  }));

  readonly sensorKeys: ('tp9' | 'af7' | 'af8' | 'tp10')[] = ['tp9', 'af7', 'af8', 'tp10'];

  sensorStatus(key: 'tp9' | 'af7' | 'af8' | 'tp10'): SensorStatus {
    return this.eegWs.sensors()[key];
  }

  sensorQualityTone(key: 'tp9' | 'af7' | 'af8' | 'tp10'): 'good' | 'fair' | 'poor' | 'unknown' {
    const s = this.sensorStatus(key);
    if (!s || s.state === 'unknown') return 'unknown';
    if (s.state === 'good') return 'good';
    if (s.quality_score >= 35) return 'fair';
    return 'poor';
  }

  sensorQualityScore(key: 'tp9' | 'af7' | 'af8' | 'tp10'): string {
    const s = this.sensorStatus(key);
    if (!s || s.state === 'unknown') return this.lang.currentLang() === 'th' ? 'รอสัญญาณ' : 'Waiting';
    return `${Math.round(s.quality_score)}%`;
  }

  sensorQualityLabel(key: 'tp9' | 'af7' | 'af8' | 'tp10'): string {
    const isTh = this.lang.currentLang() === 'th';
    const tone = this.sensorQualityTone(key);
    switch (tone) {
      case 'good': return isTh ? 'สัมผัสผิวดี' : 'Good Contact';
      case 'fair': return isTh ? 'สัญญาณปานกลาง' : 'Fair Signal';
      case 'poor': return isTh ? 'แตะไม่สนิท' : 'Poor Contact';
      default: return isTh ? 'รอสัญญาณ' : 'Waiting';
    }
  }

  private readonly http = inject(HttpClient);
  private readonly personaService = inject(PersonaService);
  private readonly comicService = inject(ComicService);
  private readonly router = inject(Router);

  ngOnInit() {
    this.personaService.getAll().subscribe((p) => this.personas.set(p));
  }

  ngOnDestroy() {
    this.museBt.disconnect();
    this.eegWs.disconnect();
  }

  stage = computed(() => {
    if (this.generating()) return 'generate';
    const bt = this.btState();
    if (bt !== 'streaming') return 'device';
    const p = this.currentPhase();
    if (p === 'DISCOVERING' || p === 'DEVICE_CONFIRMATION' || p === 'CONNECTING') return 'prepare';
    if (p === 'PREPARATION' || p === 'FITTING') return 'prepare';
    if (p === 'BASELINE') return 'baseline';
    if (p === 'READY') return 'ready';
    if (p === 'RECORDING' || p === 'PAUSED_SIGNAL_QUALITY') return 'record';
    if (p === 'EMOTION_CONFIRMATION' || p === 'COMPLETED') return 'emotion';
    if (p === 'TIMEOUT') return 'timeout';
    return 'fallback';
  });

  activeStepKey = computed(() => (
    { device: 'connect', prepare: 'signal', baseline: 'signal', ready: 'emotion', record: 'emotion', emotion: 'emotion', timeout: 'emotion', generate: 'comic', fallback: 'connect' }[this.stage()] ?? 'connect'
  ));
  stepDone(key: string) {
    return this.steps().findIndex((s) => s.key === key) < this.steps().findIndex((s) => s.key === this.activeStepKey());
  }

  private async ensureSession(): Promise<boolean> {
    if (this.dbSessionId()) return true;
    try {
      const s = await firstValueFrom(
        this.http.post<{ id: number }>(`${environment.apiUrl}/sessions`, {}),
      );
      this.dbSessionId.set(s.id);
      this.sessionId.set(String(s.id));
      this.eegWs.connect(String(s.id));
      return true;
    } catch {
      this.sessionId.set('local-dev');
      return false;
    }
  }

  async scanDevices() {
    this.connecting.set(true);
    this.connectError.set('');
    try {
      const deviceName = await this.museBt.connect((sample) => {
        // Stream raw EEG samples to backend via existing WebSocket
        this.eegWs.sendEegSample(sample);
      });
      await this.ensureSession();
      // Notify backend of device identity
      this.eegWs.sendCommand('confirm_device', {
        device_name: deviceName,
        device_id: deviceName,
      });
    } catch (err: unknown) {
      this.connectError.set(toThaiError(err));
    } finally {
      this.connecting.set(false);
    }
  }

  readonly Math = Math;

  startBaseline(subphase: string = 'eyes_open') {
    if (this.sessionId()) {
      this.http.post(`${environment.apiUrl}/sessions/${this.sessionId()}/start-baseline?subphase=${subphase}`, {}).subscribe();
    }
    this.eegWs.sendCommand('start_baseline', { subphase });
  }

  startRecording() {
    if (this.sessionId()) {
      this.http.post(`${environment.apiUrl}/sessions/${this.sessionId()}/start-recording`, {}).subscribe();
    }
    this.eegWs.sendCommand('start_recording');
  }

  cancelSession() {
    if (this.sessionId()) {
      this.http.post(`${environment.apiUrl}/sessions/${this.sessionId()}/cancel`, {}).subscribe();
    }
    this.museBt.disconnect();
    this.eegWs.disconnect();
    this.router.navigate(['/dashboard']);
  }

  /** Smart rollback: reset recording back to READY (story prompt) instead of full cancel */
  retryRecording() {
    if (this.sessionId()) {
      this.http.post(`${environment.apiUrl}/sessions/${this.sessionId()}/reset-recording`, {}).subscribe({
        error: () => {
          // Fallback: use WebSocket command if HTTP endpoint not available
          this.eegWs.sendCommand('reset_recording');
        },
      });
    }
    this.eegWs.sendCommand('reset_recording');
  }

  confirmEmotion() {
    if (!this.sessionId()) return;
    this.generateError.set('');
    if (this.currentPhase() === 'COMPLETED') {
      this.generateComic();
      return;
    }
    this.http.post<{ final_emotion?: string }>(`${environment.apiUrl}/sessions/${this.sessionId()}/confirm-emotion`, {}).subscribe({
      next: (result) => {
        if (result.final_emotion) {
          this.confirmedEmotion.set(result.final_emotion);
        }
        this.generateComic();
      },
      error: () => {
        if (!this.detectedEmotion()) {
          this.confirmedEmotion.set('excited');
        }
        this.generateComic();
      },
    });
  }

  remeasure() {
    this.generateError.set('');
    this.confirmedEmotion.set('');
    this.eegWs.sendCommand('remeasure');
  }
  restart() {
    this.generateError.set('');
    this.confirmedEmotion.set('');
    this.museBt.disconnect();
    this.eegWs.disconnect();
    this.dbSessionId.set(null);
    this.sessionId.set(null);
  }

  private generateComic() {
    const sessionId = this.dbSessionId();
    if (!sessionId) return;
    this.generateError.set('');
    this.generating.set(true);
    this.comicService.generate({
      session_id: sessionId,
      persona_id: this.selectedPersonaId ?? undefined,
      input_story: this.inputStory,
      art_style: this.selectedPersonaForStyle(),
    }).subscribe({
      next: (comic) => { this.generating.set(false); this.router.navigate(['/comic', comic.id]); },
      error: (err: { status?: number; error?: { detail?: string } }) => {
        this.generating.set(false);
        const detail = err?.error?.detail;
        if (detail) {
          this.generateError.set(detail);
        } else if (err?.status && err.status >= 500) {
          this.generateError.set(`เซิร์ฟเวอร์ขัดข้อง (HTTP ${err.status}) กรุณาดู log ของ Backend`);
        } else {
          this.generateError.set(toThaiError(err));
        }
      },
    });
  }

  private selectedPersonaForStyle(): string {
    return this.selectedArtStyle || 'Manga';
  }

  emotionEmoji(e: string) {
    return ({ happy: 'Happy', sad: 'Sad', stressed: 'Stressed', excited: 'Excited' } as Record<string, string>)[e] ?? (e || 'Emotion');
  }

  emotionLabel(e: string) {
    const isTh = this.lang.currentLang() === 'th';
    const thMap: Record<string, string> = { happy: 'มีความสุข', sad: 'เศร้า', stressed: 'เครียด', excited: 'ตื่นเต้น' };
    const enMap: Record<string, string> = { happy: 'Happy', sad: 'Sad', stressed: 'Stressed', excited: 'Excited' };
    return (isTh ? thMap : enMap)[e] ?? (e || (isTh ? 'อารมณ์' : 'Emotion'));
  }

  currentPhaseLabel(): string {
    const isTh = this.lang.currentLang() === 'th';
    const p = this.currentPhase();
    const thMap: Record<string, string> = {
      TIMEOUT: 'หมดเวลาการบันทึก',
      FAILED: 'การประมวลผลขัดข้อง',
      DISCONNECTED: 'ขาดการเชื่อมต่อกับ Muse 2',
      CANCELLED: 'ยกเลิกเซสชันแล้ว',
    };
    const enMap: Record<string, string> = {
      TIMEOUT: 'Recording Timeout',
      FAILED: 'Session Failed',
      DISCONNECTED: 'Muse 2 Disconnected',
      CANCELLED: 'Session Cancelled',
    };
    return (isTh ? thMap : enMap)[p] ?? p;
  }

  phaseReason(): string {
    const isTh = this.lang.currentLang() === 'th';
    const reason = this.eegWs.latestMessage()?.reason;
    if (reason) return reason;
    const p = this.currentPhase();
    if (p === 'TIMEOUT') {
      return isTh
        ? 'ไม่สามารถสะสมคลื่นสะอาดครบ 30 วินาทีภายใน 120 วินาที กรุณาลองใหม่อีกครั้ง'
        : 'Could not accumulate 30 clean seconds within 120s limit. Please try again.';
    }
    return isTh ? 'กำลังรอการอัปเดตสถานะจากระบบ...' : 'Waiting for status update from backend...';
  }
}
