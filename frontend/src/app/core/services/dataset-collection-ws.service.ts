import { Injectable, OnDestroy, signal } from '@angular/core';
import { Subscription } from 'rxjs';

import { environment } from '../../../environments/environment';
import { AuthService } from './auth.service';
import {
  BaselineKind,
  CollectionRunnerState,
  CollectionSessionState,
  DatasetCollectionService,
  TrialState,
} from './dataset-collection.service';

const RECONNECT_DELAY_MS = 3000;
const SESSION_STATES: readonly CollectionSessionState[] = [
  'preparation', 'baseline', 'ready', 'in_progress', 'completed', 'interrupted', 'withdrawn', 'failed',
];
const BASELINE_KINDS: readonly BaselineKind[] = ['eyes_open', 'eyes_closed'];
const TRIAL_STATES: readonly TrialState[] = [
  'scheduled', 'rest', 'stimulus', 'rating', 'completed', 'interrupted', 'failed',
];
const MESSAGE_KEYS = new Set([
  'sequence', 'stream_error', 'session_id', 'state', 'active_baseline', 'current_trial_id',
  'current_trial_order', 'current_stimulus_id', 'current_stimulus_title', 'trial_state',
  'completed_trials', 'total_trials', 'next_trial_order', 'next_trial_id', 'next_stimulus_id',
  'next_stimulus_title', 'break_required', 'interruption_reason', 'accepted_clean_seconds',
  'wall_clock_seconds', 'file_recovery_required',
]);

interface CollectionWsMessage extends CollectionRunnerState {
  sequence: number;
  stream_error?: string;
}

@Injectable({ providedIn: 'root' })
export class DatasetCollectionWsService implements OnDestroy {
  private socket: WebSocket | null = null;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private refreshSubscription: Subscription | null = null;
  private sessionId: number | null = null;
  private latestSequence = 0;
  private explicitlyDisconnected = true;
  private destroyed = false;

  readonly state = signal<CollectionRunnerState | null>(null);
  readonly isConnected = signal(false);

  constructor(
    private readonly auth: AuthService,
    private readonly runnerApi: DatasetCollectionService,
  ) {}

  connect(sessionId: number): void {
    this.disconnect();
    this.destroyed = false;
    this.explicitlyDisconnected = false;
    this.sessionId = sessionId;
    this.latestSequence = 0;
    this.state.set(null);
    this.openSocket(sessionId, false);
  }

  disconnect(): void {
    this.explicitlyDisconnected = true;
    this.cancelReconnect();
    this.refreshSubscription?.unsubscribe();
    this.refreshSubscription = null;
    const socket = this.socket;
    this.socket = null;
    if (socket) {
      socket.onopen = null;
      socket.onmessage = null;
      socket.onclose = null;
      socket.onerror = null;
      socket.close();
    }
    this.isConnected.set(false);
  }

  ngOnDestroy(): void {
    this.destroyed = true;
    this.disconnect();
  }

  private openSocket(sessionId: number, reconnect: boolean): void {
    if (this.explicitlyDisconnected || this.destroyed) return;
    if (reconnect) this.latestSequence = 0;
    const token = encodeURIComponent(this.auth.getToken() ?? '');
    const socket = new WebSocket(
      `${environment.wsUrl}/admin/dataset-collection/ws/${sessionId}?token=${token}`,
    );
    this.socket = socket;

    socket.onopen = () => {
      if (this.socket !== socket) return;
      this.isConnected.set(true);
      if (reconnect) this.refreshPersistedState(sessionId, socket);
    };
    socket.onmessage = event => {
      if (this.socket !== socket) return;
      const message = parseMessage(event.data);
      if (!message || message.sequence <= this.latestSequence) return;
      this.latestSequence = message.sequence;
      const { sequence: _sequence, stream_error: _streamError, ...runnerState } = message;
      this.state.set(runnerState);
    };
    socket.onerror = () => {
      if (this.socket === socket) this.isConnected.set(false);
    };
    socket.onclose = event => {
      if (this.socket !== socket) return;
      this.socket = null;
      this.isConnected.set(false);
      if (!event.wasClean || event.code !== 1000) this.scheduleReconnect(sessionId);
    };
  }

  private scheduleReconnect(sessionId: number): void {
    if (this.explicitlyDisconnected || this.destroyed || this.reconnectTimer !== null) return;
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      if (!this.explicitlyDisconnected && !this.destroyed && this.sessionId === sessionId) {
        this.openSocket(sessionId, true);
      }
    }, RECONNECT_DELAY_MS);
  }

  private cancelReconnect(): void {
    if (this.reconnectTimer !== null) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }

  private refreshPersistedState(sessionId: number, socket: WebSocket): void {
    this.refreshSubscription?.unsubscribe();
    const sequenceAtRequest = this.latestSequence;
    this.refreshSubscription = this.runnerApi.getRunnerState(sessionId).subscribe({
      next: state => {
        if (this.socket === socket && this.latestSequence === sequenceAtRequest) this.state.set(state);
      },
      error: () => undefined,
    });
  }
}

function parseMessage(raw: unknown): CollectionWsMessage | null {
  if (typeof raw !== 'string') return null;
  let value: unknown;
  try {
    value = JSON.parse(raw);
  } catch {
    return null;
  }
  if (!isRecord(value) || Object.keys(value).some(key => !MESSAGE_KEYS.has(key))) return null;
  const requiredKeys = [...MESSAGE_KEYS].filter(key => key !== 'stream_error');
  if (requiredKeys.some(key => !(key in value))) return null;
  if (!isPositiveInteger(value['sequence']) || !isPositiveInteger(value['session_id'])) return null;
  if (!isEnum(value['state'], SESSION_STATES)) return null;
  if (!isNullableEnum(value['active_baseline'], BASELINE_KINDS)) return null;
  if (!isNullableEnum(value['trial_state'], TRIAL_STATES)) return null;
  if (!isNullableInteger(value['current_trial_id']) || !isNullableInteger(value['current_trial_order'])) return null;
  if (!isNullableInteger(value['current_stimulus_id']) || !isNullableString(value['current_stimulus_title'])) return null;
  if (!isNonnegativeInteger(value['completed_trials']) || !isNonnegativeInteger(value['total_trials'])) return null;
  if (!isNullableInteger(value['next_trial_order']) || !isNullableInteger(value['next_trial_id'])) return null;
  if (!isNullableInteger(value['next_stimulus_id']) || !isNullableString(value['next_stimulus_title'])) return null;
  if (typeof value['break_required'] !== 'boolean' || !isNullableString(value['interruption_reason'])) return null;
  if (!isNonnegativeNumber(value['accepted_clean_seconds']) || !isNonnegativeNumber(value['wall_clock_seconds'])) return null;
  if (typeof value['file_recovery_required'] !== 'boolean') return null;
  if ('stream_error' in value && typeof value['stream_error'] !== 'string') return null;
  return value as unknown as CollectionWsMessage;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isEnum<T extends string>(value: unknown, allowed: readonly T[]): value is T {
  return typeof value === 'string' && allowed.includes(value as T);
}

function isNullableEnum<T extends string>(value: unknown, allowed: readonly T[]): value is T | null {
  return value === null || isEnum(value, allowed);
}

function isPositiveInteger(value: unknown): value is number {
  return typeof value === 'number' && Number.isSafeInteger(value) && value > 0;
}

function isNonnegativeInteger(value: unknown): value is number {
  return typeof value === 'number' && Number.isSafeInteger(value) && value >= 0;
}

function isNullableInteger(value: unknown): value is number | null {
  return value === null || isPositiveInteger(value);
}

function isNonnegativeNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0;
}

function isNullableString(value: unknown): value is string | null {
  return value === null || typeof value === 'string';
}
