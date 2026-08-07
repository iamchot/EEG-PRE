import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed, fakeAsync, tick } from '@angular/core/testing';
import { environment } from '../../../environments/environment';
import { MuseDevice, MuseDeviceService } from './muse-device.service';

const device: MuseDevice = { name: 'Creative Muse', address: 'AA:BB:CC:DD' };

describe('MuseDeviceService', () => {
  let service: MuseDeviceService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting(), MuseDeviceService],
    });
    service = TestBed.inject(MuseDeviceService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('keeps a scan busy until the first terminal scan status', fakeAsync(() => {
    service.scan();
    http.expectOne(`${environment.apiUrl}/muse/scans`).flush({ scan_id: 'scan-1', state: 'scanning', devices: [] });

    expect(service.scanStatus().state).toBe('scanning');
    tick(500);
    http.expectOne(`${environment.apiUrl}/muse/scans/scan-1`).flush({ scan_id: 'scan-1', state: 'scanning', devices: [] });
    expect(service.scanStatus().state).toBe('scanning');

    tick(500);
    http.expectOne(`${environment.apiUrl}/muse/scans/scan-1`).flush({ scan_id: 'scan-1', state: 'found', devices: [device] });
    expect(service.scanStatus()).toEqual({ scanId: 'scan-1', state: 'found', devices: [device], detail: null });
  }));

  it('enters scanning and clears a previous typed failure before scan creation responds', () => {
    service.scanStatus.set({ scanId: 'scan-old', state: 'failed', devices: [], detail: 'scan_failed' });

    service.scan();

    const enteredScanning = service.scanStatus().state === 'scanning'
      && service.scanStatus().detail === null;
    http.expectOne(`${environment.apiUrl}/muse/scans`).flush({ scan_id: 'scan-2', state: 'not_found', devices: [] });
    expect(enteredScanning).toBeTrue();
  });

  it('keeps exactly one active scan poll and cancels it on request', fakeAsync(() => {
    service.scan();
    service.scan();
    http.expectOne(`${environment.apiUrl}/muse/scans`).flush({ scan_id: 'scan-1', state: 'scanning', devices: [] });

    tick(500);
    http.expectOne(`${environment.apiUrl}/muse/scans/scan-1`).flush({ scan_id: 'scan-1', state: 'scanning', devices: [] });
    service.cancelScan();
    tick(1000);

    http.expectNone(`${environment.apiUrl}/muse/scans/scan-1`);
    expect(service.scanStatus().state).toBe('idle');
  }));

  it('exposes a typed scan failure instead of leaving the scan busy', () => {
    service.scan();
    http.expectOne(`${environment.apiUrl}/muse/scans`).flush({ scan_id: 'scan-1', state: 'failed', devices: [], detail: 'scan_failed' });

    expect(service.scanStatus()).toEqual({ scanId: 'scan-1', state: 'failed', devices: [], detail: 'scan_failed' });
  });

  it('uses the user Muse URL and only marks the selected device connected after verified connected', () => {
    let result = '';
    service.connectUser(7, device).subscribe(status => result = status.state);

    const request = http.expectOne(`${environment.apiUrl}/sessions/7/muse`);
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual(device);
    request.flush({ owner: { kind: 'user', session_id: 7 }, state: 'waiting_for_lsl', detail: null });

    expect(result).toBe('waiting_for_lsl');
    expect(service.connectedDevice()).toBeNull();
    expect(service.connectionStatus().state).toBe('waiting_for_lsl');
  });

  it('stores the selected device only for the exact connected status', () => {
    service.connectUser(7, device).subscribe();
    http.expectOne(`${environment.apiUrl}/sessions/7/muse`).flush({
      owner: { kind: 'user', session_id: 7 }, state: 'connected', detail: null,
    });

    expect(service.connectedDevice()).toEqual(device);
  });

  it('uses the user URL for disconnect', () => {
    service.disconnectUser(7).subscribe();

    const request = http.expectOne(`${environment.apiUrl}/sessions/7/muse`);
    expect(request.request.method).toBe('DELETE');
    request.flush({ owner: { kind: 'user', session_id: 7 }, state: 'idle', detail: null });
    expect(service.connectionStatus().state).toBe('idle');
  });

  it('records every connection stage and exposes typed failures', () => {
    const statuses = [
      'starting_bridge', 'connecting_bluetooth', 'waiting_for_lsl', 'connected', 'failed',
    ] as const;

    statuses.forEach((state) => {
      service.connectUser(7, device).subscribe();
      http.expectOne(`${environment.apiUrl}/sessions/7/muse`).flush({
        owner: { kind: 'user', session_id: 7 },
        state,
        detail: state === 'failed' ? 'bluetooth_timeout' : null,
      });
      expect(service.connectionStatus().state).withContext(state).toBe(state);
    });
    expect(service.connectionStatus().detail).toBe('bluetooth_timeout');
  });

  it('uses the admin URL for connect and disconnect', () => {
    service.connectAdmin(13, device).subscribe();
    const connect = http.expectOne(`${environment.apiUrl}/admin/dataset-collection/sessions/13/muse`);
    expect(connect.request.method).toBe('POST');
    expect(connect.request.body).toEqual(device);
    connect.flush({ owner: { kind: 'collection', session_id: 13 }, state: 'connected', detail: null });

    service.disconnectAdmin(13).subscribe();
    const disconnect = http.expectOne(`${environment.apiUrl}/admin/dataset-collection/sessions/13/muse`);
    expect(disconnect.request.method).toBe('DELETE');
    disconnect.flush({ owner: { kind: 'collection', session_id: 13 }, state: 'idle', detail: null });
    expect(service.connectionStatus().state).toBe('idle');
  });

  it('polls a real user status URL through connected and clears a lost Muse', fakeAsync(() => {
    service.connectUser(7, device).subscribe();
    http.expectOne(`${environment.apiUrl}/sessions/7/muse`).flush({
      owner: { kind: 'user', session_id: 7 }, state: 'waiting_for_lsl', detail: null,
    });

    tick(500);
    http.expectOne(`${environment.apiUrl}/sessions/7/muse`).flush({
      owner: { kind: 'user', session_id: 7 }, state: 'connected', detail: null,
    });
    expect(service.connectedDevice()).toEqual(device);

    tick(500);
    http.expectOne(`${environment.apiUrl}/sessions/7/muse`).flush({
      owner: { kind: 'user', session_id: 7 }, state: 'failed', detail: 'bridge_exited',
    });
    expect(service.connectionStatus().state).toBe('failed');
    expect(service.connectedDevice()).toBeNull();
  }));
});
