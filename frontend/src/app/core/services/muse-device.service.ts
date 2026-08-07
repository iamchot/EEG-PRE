import { HttpClient } from '@angular/common/http';
import { Injectable, signal } from '@angular/core';
import { Observable, Subscription, of, timer } from 'rxjs';
import { catchError, finalize, map, switchMap, takeWhile, tap } from 'rxjs/operators';
import { environment } from '../../../environments/environment';

export type MuseScanState = 'idle' | 'scanning' | 'found' | 'not_found' | 'failed';
export type MuseConnectionState =
  | 'idle'
  | 'starting_bridge'
  | 'connecting_bluetooth'
  | 'waiting_for_lsl'
  | 'connected'
  | 'failed'
  | 'disconnecting';

export type MuseScanFailure = 'scan_failed';
export type MuseConnectionFailure =
  | 'device_in_use'
  | 'bridge_exited'
  | 'bluetooth_timeout'
  | 'lsl_timeout'
  | 'bridge_failed';

export interface MuseDevice {
  address: string;
  name: string;
}

export interface MuseOwner {
  kind: 'user' | 'collection';
  sessionId: number;
}

export interface MuseScanStatus {
  scanId: string | null;
  state: MuseScanState;
  devices: MuseDevice[];
  detail: MuseScanFailure | null;
}

export interface MuseConnectionStatus {
  owner: MuseOwner | null;
  state: MuseConnectionState;
  detail: MuseConnectionFailure | null;
}

interface ApiMuseScanStatus {
  scan_id: string;
  state: Exclude<MuseScanState, 'idle'>;
  devices: MuseDevice[];
  detail?: MuseScanFailure | null;
}

interface ApiMuseConnectionStatus {
  owner: { kind: MuseOwner['kind']; session_id: number };
  state: MuseConnectionState;
  detail?: MuseConnectionFailure | null;
}

const idleScanStatus: MuseScanStatus = {
  scanId: null,
  state: 'idle',
  devices: [],
  detail: null,
};

const idleConnectionStatus: MuseConnectionStatus = {
  owner: null,
  state: 'idle',
  detail: null,
};

@Injectable({ providedIn: 'root' })
export class MuseDeviceService {
  readonly scanStatus = signal<MuseScanStatus>(idleScanStatus);
  readonly connectionStatus = signal<MuseConnectionStatus>(idleConnectionStatus);
  readonly connectedDevice = signal<MuseDevice | null>(null);

  private scanSubscription: Subscription | null = null;
  private connectionPollSubscription: Subscription | null = null;
  private connectionPollOwner: MuseOwner | null = null;

  constructor(private readonly http: HttpClient) {}

  scan(): void {
    if (this.scanSubscription) return;

    this.scanStatus.set({ scanId: null, state: 'scanning', devices: [], detail: null });
    this.scanSubscription = this.http.post<ApiMuseScanStatus>(`${environment.apiUrl}/muse/scans`, {}).pipe(
      map(toScanStatus),
      switchMap((status) => {
        this.scanStatus.set(status);
        return status.state === 'scanning' ? this.pollScan(status.scanId!) : of(status);
      }),
      catchError(() => of<MuseScanStatus>({ scanId: null, state: 'failed', devices: [], detail: 'scan_failed' })),
      tap((status) => this.scanStatus.set(status)),
      finalize(() => this.scanSubscription = null),
    ).subscribe();
  }

  cancelScan(): void {
    this.scanSubscription?.unsubscribe();
    this.scanSubscription = null;
    this.scanStatus.set(idleScanStatus);
  }

  connectUser(sessionId: number, device: MuseDevice): Observable<MuseConnectionStatus> {
    const owner: MuseOwner = { kind: 'user', sessionId };
    return this.connect(`${environment.apiUrl}/sessions/${sessionId}/muse`, owner, device);
  }

  disconnectUser(sessionId: number): Observable<MuseConnectionStatus> {
    return this.disconnect(
      `${environment.apiUrl}/sessions/${sessionId}/muse`,
      { kind: 'user', sessionId },
    );
  }

  connectAdmin(sessionId: number, device: MuseDevice): Observable<MuseConnectionStatus> {
    const owner: MuseOwner = { kind: 'collection', sessionId };
    return this.connect(`${environment.apiUrl}/admin/dataset-collection/sessions/${sessionId}/muse`, owner, device);
  }

  disconnectAdmin(sessionId: number): Observable<MuseConnectionStatus> {
    return this.disconnect(
      `${environment.apiUrl}/admin/dataset-collection/sessions/${sessionId}/muse`,
      { kind: 'collection', sessionId },
    );
  }

  resetState(): void {
    this.stopConnectionPolling();
    this.cancelScan();
    this.scanStatus.set({ scanId: '', state: 'idle', devices: [], detail: null });
    this.connectionStatus.set({ owner: null, state: 'idle', detail: null });
    this.connectedDevice.set(null);
  }

  private pollScan(scanId: string): Observable<MuseScanStatus> {
    return timer(500, 500).pipe(
      switchMap(() => this.http.get<ApiMuseScanStatus>(`${environment.apiUrl}/muse/scans/${scanId}`).pipe(
        map(toScanStatus),
        catchError(() => of<MuseScanStatus>({ scanId, state: 'failed', devices: [], detail: 'scan_failed' })),
      )),
      takeWhile((status) => status.state === 'scanning', true),
    );
  }

  private connect(
    url: string,
    owner: MuseOwner,
    device?: MuseDevice,
  ): Observable<MuseConnectionStatus> {
    this.stopConnectionPolling();
    this.connectionStatus.set({ owner, state: 'starting_bridge', detail: null });
    this.connectedDevice.set(null);
    return this.http.post<ApiMuseConnectionStatus>(url, device ?? {}).pipe(
      map(toConnectionStatus),
      catchError(() => of<MuseConnectionStatus>({ owner, state: 'failed', detail: 'bridge_failed' })),
      tap((status) => {
        this.setConnectionStatus(status, device);
        if (status.state !== 'failed' && status.state !== 'idle') this.startConnectionPolling(url, owner, device);
      }),
    );
  }

  private disconnect(url: string, owner: MuseOwner): Observable<MuseConnectionStatus> {
    this.stopConnectionPolling(owner);
    this.connectionStatus.set({ owner, state: 'disconnecting', detail: null });
    return this.http.delete<ApiMuseConnectionStatus>(url).pipe(
      map(toConnectionStatus),
      catchError(() => of<MuseConnectionStatus>({ owner, state: 'failed', detail: 'bridge_failed' })),
      tap((status) => this.setConnectionStatus(status)),
    );
  }

  private setConnectionStatus(status: MuseConnectionStatus, device?: MuseDevice): void {
    this.connectionStatus.set(status);
    this.connectedDevice.set(status.state === 'connected' ? device ?? this.connectedDevice() : null);
  }

  private startConnectionPolling(url: string, owner: MuseOwner, device?: MuseDevice): void {
    this.stopConnectionPolling();
    this.connectionPollOwner = owner;
    this.connectionPollSubscription = timer(500, 500).pipe(
      switchMap(() => this.http.get<ApiMuseConnectionStatus>(url).pipe(
        map(toConnectionStatus),
        catchError(() => of<MuseConnectionStatus>({ owner, state: 'failed', detail: 'bridge_failed' })),
      )),
      tap((status) => this.setConnectionStatus(status, device)),
      takeWhile((status) => status.state !== 'failed' && status.state !== 'idle', true),
      finalize(() => {
        this.connectionPollSubscription = null;
        this.connectionPollOwner = null;
      }),
    ).subscribe();
  }

  private stopConnectionPolling(owner?: MuseOwner): void {
    if (owner && (!this.connectionPollOwner || this.connectionPollOwner.kind !== owner.kind || this.connectionPollOwner.sessionId !== owner.sessionId)) return;
    this.connectionPollSubscription?.unsubscribe();
    this.connectionPollSubscription = null;
    this.connectionPollOwner = null;
  }
}

function toScanStatus(status: ApiMuseScanStatus): MuseScanStatus {
  return {
    scanId: status.scan_id,
    state: status.state,
    devices: status.devices,
    detail: status.detail ?? null,
  };
}

function toConnectionStatus(status: ApiMuseConnectionStatus): MuseConnectionStatus {
  return {
    owner: { kind: status.owner.kind, sessionId: status.owner.session_id },
    state: status.state,
    detail: status.detail ?? null,
  };
}
