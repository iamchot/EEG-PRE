import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { environment } from '../../../environments/environment';
import { SystemHealth, SystemHealthService } from './system-health.service';

const health: SystemHealth = {
  api: { state: 'available', detail: 'API is responding', checked_at: '2026-07-29T10:15:30.123Z', latency_ms: 12 },
  comfyui: { state: 'degraded', detail: 'Queue is slow', checked_at: '2026-07-29T10:15:31.456Z', latency_ms: 820 },
  gemini: { state: 'unavailable', detail: 'Credential rejected', checked_at: '2026-07-29T10:15:32.789Z', latency_ms: null },
  muse: { state: 'checking', detail: 'Waiting for a session', checked_at: '2026-07-29T10:15:33.000Z', latency_ms: null },
};

describe('SystemHealthService', () => {
  let service: SystemHealthService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting(), SystemHealthService],
    });
    service = TestBed.inject(SystemHealthService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('clears stale health while checking and preserves every backend state and timestamp', () => {
    service.health.set({
      ...health,
      comfyui: { ...health.comfyui, state: 'available', checked_at: 'old-check' },
    });

    service.refresh();

    expect(service.loading()).toBeTrue();
    expect(service.health()).toBeNull();
    const request = http.expectOne(`${environment.apiUrl}/system/health`);
    expect(request.request.method).toBe('GET');
    request.flush(health);

    expect(service.loading()).toBeFalse();
    expect(service.error()).toBeNull();
    expect(service.health()).toEqual(health);
  });

  it('clears stale health instead of leaving a green result visible when the health check fails', () => {
    service.health.set(health);

    service.refresh();
    http.expectOne(`${environment.apiUrl}/system/health`).flush('offline', { status: 503, statusText: 'Service Unavailable' });

    expect(service.loading()).toBeFalse();
    expect(service.health()).toBeNull();
    expect(service.error()?.status).toBe(503);
  });
});
