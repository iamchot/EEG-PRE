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

@Injectable({ providedIn: 'root' })
export class MuseWebBluetoothService {
  readonly state = signal<MuseWebBtState>('idle');
  readonly error = signal<string>('');
  readonly deviceName = signal<string | null>(null);
  readonly deviceId = signal<string | null>(null);

  /** True when Web Bluetooth API is available in this browser */
  readonly isSupported = typeof navigator !== 'undefined' && 'bluetooth' in navigator;

  private client: MuseClient | null = null;
  private eegSubscription: { unsubscribe(): void } | null = null;
  private onSample: ((sample: WebBtSensorRaw) => void) | null = null;

  // Buffer one sample per channel before emitting combined packet
  private _buf: Partial<Record<number, number>> = {};

  /**
   * Open the browser Bluetooth picker, connect to Muse 2, and start
   * streaming EEG samples. Returns the device name on success.
   */
  async connect(onSample: (sample: WebBtSensorRaw) => void): Promise<string> {
    if (!this.isSupported) {
      const msg = 'เบราว์เซอร์นี้ไม่รองรับ Web Bluetooth (ใช้ Chrome หรือ Edge)';
      this.state.set('failed');
      this.error.set(msg);
      throw new Error(msg);
    }

    this.onSample = onSample;
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
      return name;
    } catch (err: unknown) {
      const msg = toThaiError(err) || 'ไม่สามารถเชื่อมต่อ Muse 2 ได้';
      this.state.set('failed');
      this.error.set(msg);
      throw err;
    }
  }

  /** Allow updating the sample consumer (e.g. when switching sessions). */
  setOnSample(onSample: (sample: WebBtSensorRaw) => void): void {
    this.onSample = onSample;
  }

  async disconnect(): Promise<void> {
    this.eegSubscription?.unsubscribe();
    this.eegSubscription = null;
    this.onSample = null;
    this._buf = {};
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

    // muse-js emits one EEGReading per electrode per packet (~12 samples, 256 Hz)
    // reading.electrode: 0=TP9, 1=AF7, 2=AF8, 3=TP10, 4=AUX
    // We average the samples in each packet and emit when all 4 channels are ready
    const sub = this.client.eegReadings.subscribe(reading => {
      if (!this.onSample) return;
      const elec = reading.electrode as number;
      if (elec > CH_TP10) return; // skip AUX

      this._buf[elec] = avg(reading.samples);

      if (
        this._buf[CH_TP9]  !== undefined &&
        this._buf[CH_AF7]  !== undefined &&
        this._buf[CH_AF8]  !== undefined &&
        this._buf[CH_TP10] !== undefined
      ) {
        this.onSample({
          tp9:  this._buf[CH_TP9]!,
          af7:  this._buf[CH_AF7]!,
          af8:  this._buf[CH_AF8]!,
          tp10: this._buf[CH_TP10]!,
          timestamp: Date.now() / 1000,
        });
        this._buf = {};
      }
    });

    this.eegSubscription = sub;
  }
}

function avg(arr: number[]): number {
  if (!arr.length) return 0;
  let sum = 0;
  for (let i = 0; i < arr.length; i++) sum += arr[i];
  return sum / arr.length;
}
