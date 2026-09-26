import { DecimalPipe } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { Component, OnDestroy, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { environment } from '../../../environments/environment';
import { EegWsService } from '../../core/services/eeg-ws.service';
import { ComicService } from '../../core/services/comic.service';
import { PersonaService, Persona } from '../../core/services/persona.service';
import { HorseshoeSensorComponent } from '../../shared/components/horseshoe-sensor/horseshoe-sensor.component';
import { EegWaveformComponent } from '../../shared/components/eeg-waveform/eeg-waveform.component';
import { LanguageService, toThaiError } from '../../core/services/language.service';
import { TranslatePipe } from '../../core/pipes/translate.pipe';
import { MuseWebBluetoothService } from '../../core/services/muse-web-bluetooth.service';

@Component({
  selector: 'app-eeg-session',
  standalone: true,
  imports: [FormsModule, DecimalPipe, HorseshoeSensorComponent, EegWaveformComponent, TranslatePipe],
  templateUrl: './eeg-session.component.html',
  styleUrl: './eeg-session.component.css',
})
export class EegSessionComponent implements OnInit, OnDestroy {
  readonly lang = inject(LanguageService);
  readonly eegWs = inject(EegWsService);
  readonly museBt = inject(MuseWebBluetoothService);

  currentPhase = computed(() => this.eegWs.phase());
  generating = signal(false);
  connecting = signal(false);
  connectError = signal('');
  personas = signal<Persona[]>([]);
  detectedEmotion = signal('');
  selectedPersonaId: number | null = null;
  inputStory = '';
  sessionId = signal<string | null>(null);
  dbSessionId = signal<number | null>(null);

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

  private readonly http = inject(HttpClient);
  private readonly personaService = inject(PersonaService);
  private readonly comicService = inject(ComicService);
  private readonly router = inject(Router);

  ngOnInit() {
    this.personaService.getAll().subscribe((p) => this.personas.set(p));
    this.createSession();
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
    return 'fallback';
  });

  activeStepKey = computed(() => (
    { device: 'connect', prepare: 'signal', baseline: 'signal', ready: 'emotion', record: 'emotion', emotion: 'emotion', generate: 'comic', fallback: 'connect' }[this.stage()] ?? 'connect'
  ));
  stepDone(key: string) {
    return this.steps().findIndex((s) => s.key === key) < this.steps().findIndex((s) => s.key === this.activeStepKey());
  }

  private createSession() {
    this.http.post<{ id: number }>(`${environment.apiUrl}/sessions`, {}).subscribe({
      next: (s) => {
        this.dbSessionId.set(s.id);
        this.sessionId.set(String(s.id));
        this.eegWs.connect(String(s.id));
      },
      error: () => { this.sessionId.set('local-dev'); },
    });
  }

  async scanDevices() {
    const sessionId = this.dbSessionId();
    if (!sessionId) return;
    this.connecting.set(true);
    this.connectError.set('');
    try {
      const deviceName = await this.museBt.connect((sample) => {
        // Stream raw EEG samples to backend via existing WebSocket
        this.eegWs.sendEegSample(sample);
      });
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

  startBaseline() {
    if (this.sessionId()) {
      this.http.post(`${environment.apiUrl}/sessions/${this.sessionId()}/start-baseline`, {}).subscribe();
    }
    this.eegWs.sendCommand('start_baseline');
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

  confirmEmotion() {
    if (!this.sessionId()) return;
    this.http.post<{ final_emotion?: string }>(`${environment.apiUrl}/sessions/${this.sessionId()}/confirm-emotion`, {}).subscribe({
      next: (result) => { this.detectedEmotion.set(result.final_emotion ?? 'excited'); this.generateComic(); },
      error: () => { this.detectedEmotion.set('excited'); this.generateComic(); },
    });
  }

  remeasure() { this.eegWs.sendCommand('remeasure'); }
  restart() { this.museBt.disconnect(); this.eegWs.disconnect(); this.createSession(); }

  private generateComic() {
    const sessionId = this.dbSessionId();
    if (!sessionId) return;
    this.generating.set(true);
    this.comicService.generate({
      session_id: sessionId,
      persona_id: this.selectedPersonaId ?? undefined,
      input_story: this.inputStory,
      art_style: this.selectedPersonaForStyle(),
    }).subscribe({
      next: (comic) => { this.generating.set(false); this.router.navigate(['/comic', comic.id]); },
      error: () => this.generating.set(false),
    });
  }

  private selectedPersonaForStyle(): string {
    const p = this.personas().find((x) => x.id === this.selectedPersonaId);
    return p?.art_style ?? 'Manga';
  }

  emotionEmoji(e: string) {
    return ({ happy: 'Happy', sad: 'Sad', stressed: 'Stressed', excited: 'Excited' } as Record<string, string>)[e] ?? (e || 'Emotion');
  }

  emotionLabel(e: string) {
    return ({ happy: 'มีความสุข (Happy)', sad: 'เศร้า (Sad)', stressed: 'เครียด (Stressed)', excited: 'ตื่นเต้น (Excited)' } as Record<string, string>)[e] ?? (e || 'อารมณ์');
  }
}
