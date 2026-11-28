import { Injectable, signal } from '@angular/core';
import { MuseClient } from 'muse-js';
import { toThaiError } from './language.service';

export type MuseWebBtState =
  | 'idle'
  | 'requesting'
  | 'connecting'
  | 'connected'
  | 'streaming'
  | 'failed';

export interface WebBtSensorRaw {
  tp9: number;
  af7: number;
  af8: number;
  tp10: number;
  timestamp: number;
}

// channelNames from muse-js: ['TP9', 'AF7', 'AF8', 'TP10', 'AUX']
const CH_TP9 = 0;
const CH_AF7 = 1;
const CH_AF8 = 2;
const CH_TP10 = 3;

interface Unsubscribable {
  unsubscribe(): void;
}

@Injectable({ providedIn: 'root' })
export class MuseWebBluetoothService {
  readonly state = signal<MuseWebBtState>('idle');
  readonly error = signal<string>('');
  readonly deviceName = signal<string | null>(null);
  readonly deviceId = signal<string | null>(null);

  /** True when Web Bluetooth API is available in this browser */
  readonly isSupported = typeof navigator !== 'undefined' && 'bluetooth' in navigator;

  private client: MuseClient | null = null;
  private eegSubscription: Unsubscribable | null = null;
  private connectionSubscription: Unsubscribable | null = null;
  private onSample: ((sample: WebBtSensorRaw) => void) | null = null;
  private onBatch: ((samples: WebBtSensorRaw[]) => void) | null = null;

  // Rolling per-channel values and packet buffers for 256 Hz streaming
  private _lastValues: Record<number, number> = {
    [CH_TP9]: 0,
    [CH_AF7]: 0,
    [CH_AF8]: 0,
    [CH_TP10]: 0,
  };
  private _channelPackets: Record<number, number[]> = {
    [CH_TP9]: [],
    [CH_AF7]: [],
    [CH_AF8]: [],
    [CH_TP10]: [],
  };
  private _packetReady: Record<number, boolean> = {};
  private _hasReceived: Record<number, boolean> = {};
  private _lastEmittedAt = 0;
  private _lastBatchEndTs = 0;
  private _lastReadingAt = 0;
  private _watchdogTimer: ReturnType<typeof setInterval> | null = null;

  /**
   * Open the browser Bluetooth picker, connect to Muse 2, and start
   * streaming EEG samples. Returns the device name on success.
   */
  async connect(
    onSample: (sample: WebBtSensorRaw) => void,
    onBatch?: (samples: WebBtSensorRaw[]) => void,
  ): Promise<string> {
    if (!this.isSupported) {
      const msg = 'เบราว์เซอร์นี้ไม่รองรับ Web Bluetooth (ใช้ Chrome หรือ Edge)';
      this.state.set('failed');
      this.error.set(msg);
      throw new Error(msg);
    }

    this.onSample = onSample;
    this.onBatch = onBatch ?? null;
    this.state.set('requesting');
    this.error.set('');

    try {
      this.client = new MuseClient();
      this.state.set('connecting');

      await this.client.connect();

      const name = (this.client as unknown as { deviceName?: string }).deviceName ?? 'Muse 2';
      this.deviceName.set(name);
      this.deviceId.set(name);

      await this.client.start();
      this.state.set('streaming');

      this._subscribeEeg();
      this._startWatchdog();
      return name;
    } catch (err: unknown) {
      const msg = toThaiError(err) || 'ไม่สามารถเชื่อมต่อ Muse 2 ได้';
      this.state.set('failed');
      this.error.set(msg);
      throw err;
    }
  }

  /** Allow updating the sample consumer (e.g. when switching sessions). */
  setOnSample(
    onSample: (sample: WebBtSensorRaw) => void,
    onBatch?: (samples: WebBtSensorRaw[]) => void,
  ): void {
    this.onSample = onSample;
    this.onBatch = onBatch ?? null;
  }

  async disconnect(): Promise<void> {
    this._stopWatchdog();
    this.eegSubscription?.unsubscribe();
    this.eegSubscription = null;
    this.connectionSubscription?.unsubscribe();
    this.connectionSubscription = null;
    this.onSample = null;
    this.onBatch = null;
    this._hasReceived = {};
    this._packetReady = {};
    this._lastBatchEndTs = 0;
    try {
      await this.client?.disconnect();
    } catch { /* ignore */ }
    this.client = null;
    this.state.set('idle');
    this.deviceName.set(null);
    this.deviceId.set(null);
  }

  private _subscribeEeg(): void {
    if (!this.client) return;

    // Track GATT connection drops
    this.connectionSubscription = this.client.connectionStatus.subscribe({
      next: connected => {
        if (!connected && this.state() === 'streaming') {
          this.state.set('failed');
          this.error.set(toThaiError('gatt server is disconnected'));
        }
      },
      error: () => {},
    });

    // muse-js emits one EEGReading per electrode per packet (~12 samples, 256 Hz)
    // reading.electrode: 0=TP9, 1=AF7, 2=AF8, 3=TP10, 4=AUX
    const sub = this.client.eegReadings.subscribe({
      next: reading => {
        const elec = reading.electrode as number;
        if (elec > CH_TP10) return; // skip AUX

        this._lastReadingAt = Date.now();
        const rawSamples = Array.isArray(reading.samples) ? reading.samples : [];
        this._lastValues[elec] = avg(rawSamples);
        this._channelPackets[elec] = rawSamples;
        this._hasReceived[elec] = true;
        this._packetReady[elec] = true;

        const allPacketReady =
          this._packetReady[CH_TP9] &&
          this._packetReady[CH_AF7] &&
          this._packetReady[CH_AF8] &&
          this._packetReady[CH_TP10];

        if (allPacketReady && this.onBatch) {
          this._packetReady = {};
          const tp9Arr = this._channelPackets[CH_TP9];
          const af7Arr = this._channelPackets[CH_AF7];
          const af8Arr = this._channelPackets[CH_AF8];
          const tp10Arr = this._channelPackets[CH_TP10];
          const count = Math.min(tp9Arr.length, af7Arr.length, af8Arr.length, tp10Arr.length);
          if (count > 0) {
            const nowSec = Date.now() / 1000;
            const baseTs = this._lastBatchEndTs > 0 && nowSec <= this._lastBatchEndTs
              ? this._lastBatchEndTs + 1 / 256
              : nowSec;
            const batch: WebBtSensorRaw[] = [];
            for (let i = 0; i < count; i++) {
              batch.push({
                tp9: tp9Arr[i],
                af7: af7Arr[i],
                af8: af8Arr[i],
                tp10: tp10Arr[i],
                timestamp: baseTs + i / 256,
              });
            }
            this._lastBatchEndTs = batch[batch.length - 1].timestamp;
            try {
              this.onBatch(batch);
            } catch (err) {
              console.warn('Muse batch forward error:', err);
            }
          }
        }

        const allChannelsSeen =
          this._hasReceived[CH_TP9] &&
          this._hasReceived[CH_AF7] &&
          this._hasReceived[CH_AF8] &&
          this._hasReceived[CH_TP10];

        const now = Date.now();
        // Fallback single-sample emit when no batch consumer is attached
        if (!this.onBatch && allChannelsSeen && now - this._lastEmittedAt >= 45 && this.onSample) {
          this._lastEmittedAt = now;
          try {
            this.onSample({
              tp9: this._lastValues[CH_TP9],
              af7: this._lastValues[CH_AF7],
              af8: this._lastValues[CH_AF8],
              tp10: this._lastValues[CH_TP10],
              timestamp: now / 1000,
            });
          } catch (err) {
            console.warn('Muse sample forward error:', err);
          }
        }
      },
      error: err => {
        console.error('Muse EEG stream error:', err);
        if (this.state() === 'streaming') {
          this.state.set('failed');
          this.error.set(toThaiError(err) || (localStorage.getItem('app_lang') === 'en' ? 'Muse EEG stream error' : 'สัญญาณ Muse ขัดข้อง'));
        }
      },
    });

    this.eegSubscription = sub;
  }

  private _startWatchdog(): void {
    this._stopWatchdog();
    this._lastReadingAt = Date.now();
    this._watchdogTimer = setInterval(() => {
      if (this.state() === 'streaming' && Date.now() - this._lastReadingAt > 5000) {
        // No samples received for > 5 seconds while in streaming state
        console.warn('Muse Web Bluetooth watchdog: no packets received for > 5 seconds');
      }
    }, 2000);
  }

  private _stopWatchdog(): void {
    if (this._watchdogTimer !== null) {
      clearInterval(this._watchdogTimer);
      this._watchdogTimer = null;
    }
  }
}

function avg(arr: number[]): number {
  if (!arr.length) return 0;
  let sum = 0;
  for (let i = 0; i < arr.length; i++) sum += arr[i];
  return sum / arr.length;
}
