import { Injectable, signal, computed } from '@angular/core';
import { environment } from '../../../environments/environment';
import { AuthService } from './auth.service';

export type SensorState = 'unknown' | 'poor' | 'good' | 'stale';
export type DeviceState = 'disconnected' | 'connecting' | 'connected';
export type EEGPhase =
  | 'DISCOVERING' | 'DEVICE_CONFIRMATION' | 'CONNECTING' | 'PREPARATION'
  | 'FITTING' | 'BASELINE' | 'READY' | 'RECORDING' | 'PAUSED_SIGNAL_QUALITY'
  | 'EMOTION_CONFIRMATION' | 'COMPLETED' | 'TIMEOUT' | 'CANCELLED' | 'FAILED' | 'DISCONNECTED';

export interface SensorStatus {
  state: SensorState;
  quality_score: number;
  timestamp: number;
  sequence: number;
}

export interface EEGMessage {
  session_id: string;
  phase: EEGPhase;
  sequence: number;
  timestamp: number;
  device_state: DeviceState;
  device_name: string | null;
  tp9: SensorStatus;
  af7: SensorStatus;
  af8: SensorStatus;
  tp10: SensorStatus;
  accepted_seconds: number;
  wall_clock_seconds: number;
  baseline_seconds?: number;
  ready: boolean;
  reason?: string;
  error_code?: string;
}

@Injectable({ providedIn: 'root' })
export class EegWsService {
  private ws: WebSocket | null = null;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;

  readonly latestMessage = signal<EEGMessage | null>(null);
  readonly phase = computed(() => this.latestMessage()?.phase ?? 'DISCOVERING');
  readonly sensors = computed(() => ({
    tp9: this.latestMessage()?.tp9 ?? defaultSensor(),
    af7: this.latestMessage()?.af7 ?? defaultSensor(),
    af8: this.latestMessage()?.af8 ?? defaultSensor(),
    tp10: this.latestMessage()?.tp10 ?? defaultSensor(),
  }));
  readonly allSensorsGood = computed(() => {
    const s = this.sensors();
    return (s.tp9.state === 'good' && s.af7.state === 'good' &&
            s.af8.state === 'good' && s.tp10.state === 'good');
  });
  readonly acceptedSeconds = computed(() => this.latestMessage()?.accepted_seconds ?? 0);
  readonly baselineSeconds = computed(() => this.latestMessage()?.baseline_seconds ?? 0);
  readonly wallClockSeconds = computed(() => this.latestMessage()?.wall_clock_seconds ?? 0);
  readonly ready = computed(() => this.latestMessage()?.ready ?? false);
  readonly isConnected = signal(false);

  constructor(private auth: AuthService) {}

  connect(sessionId: string) {
    this.disconnect();
    const token = this.auth.getToken();
    const url = `${environment.wsUrl}/sessions/ws/${sessionId}${token ? `?token=${token}` : ''}`;
    this.ws = new WebSocket(url);

    this.ws.onopen = () => this.isConnected.set(true);

    this.ws.onmessage = (event) => {
      try {
        const msg: EEGMessage = JSON.parse(event.data);
        this.latestMessage.set(msg);
      } catch (_) { /* ignore parse errors */ }
    };

    this.ws.onclose = () => {
      this.isConnected.set(false);
      this._scheduleReconnect(sessionId);
    };

    this.ws.onerror = () => {
      this.isConnected.set(false);
    };
  }

  disconnect() {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      this.ws.onclose = null;
      this.ws.close();
      this.ws = null;
    }
    this.isConnected.set(false);
  }

  send(cmd: object) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(cmd));
    }
  }

  sendCommand(cmd: string, extras: Record<string, unknown> = {}) {
    this.send({ cmd, ...extras });
  }

  private _scheduleReconnect(sessionId: string) {
    this.reconnectTimer = setTimeout(() => this.connect(sessionId), 3000);
  }
}

function defaultSensor(): SensorStatus {
  return { state: 'unknown', quality_score: 0, timestamp: 0, sequence: 0 };
}
