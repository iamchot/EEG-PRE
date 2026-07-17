import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';

import { environment } from '../../../environments/environment';
import { DatasetCollectionService } from './dataset-collection.service';

describe('DatasetCollectionService', () => {
  let service: DatasetCollectionService;
  let http: HttpTestingController;
  const baseUrl = `${environment.apiUrl}/admin/dataset-collection`;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(DatasetCollectionService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('gets the collection overview', () => {
    service.getOverview().subscribe();
    const request = http.expectOne(`${baseUrl}/overview`);
    expect(request.request.method).toBe('GET');
    request.flush({ participants: 1, sessions: 2, trials: 3, review_counts: {}, quadrant_counts: {} });
  });

  it('lists participants with skip and limit', () => {
    service.listParticipants(10, 25).subscribe();
    const request = http.expectOne(`${baseUrl}/participants?skip=10&limit=25`);
    expect(request.request.method).toBe('GET');
    request.flush({ items: [] });
  });

  it('creates a participant with only consent_confirmed_at', () => {
    const body = { consent_confirmed_at: '2026-07-17T08:30:00Z' };
    service.createParticipant(body).subscribe();
    const request = http.expectOne(`${baseUrl}/participants`);
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual(body);
    request.flush({});
  });

  it('lists stimuli with skip and limit', () => {
    service.listStimuli(5, 50).subscribe();
    const request = http.expectOne(`${baseUrl}/stimuli?skip=5&limit=50`);
    expect(request.request.method).toBe('GET');
    request.flush({ items: [] });
  });

  it('creates a stimulus with the backend field names', () => {
    const body = {
      title: 'Calm lake',
      file_path: 'stimuli/calm-lake.mp4',
      checksum: 'sha256:abc123',
      duration_seconds: 45,
      target_quadrant: 'positive_low' as const,
      approval_state: 'approved' as const,
      stimulus_set_version: 'v1',
    };
    service.createStimulus(body).subscribe();
    const request = http.expectOne(`${baseUrl}/stimuli`);
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual(body);
    request.flush({});
  });

  it('lists sessions with skip and limit', () => {
    service.listSessions(0, 100).subscribe();
    const request = http.expectOne(`${baseUrl}/sessions?skip=0&limit=100`);
    expect(request.request.method).toBe('GET');
    request.flush({ items: [] });
  });

  it('creates a session with participant and device details', () => {
    const body = { participant_id: 7, device_id: 'muse-01', device_name: 'Muse 2' };
    service.createSession(body).subscribe();
    const request = http.expectOne(`${baseUrl}/sessions`);
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual(body);
    request.flush({});
  });
});
