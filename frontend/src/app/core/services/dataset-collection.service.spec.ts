import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';

import { environment } from '../../../environments/environment';
import {
  CollectionList,
  CollectionOverview,
  CollectionSession,
  DatasetCollectionService,
  DatasetParticipant,
  EmotionStimulus,
  CollectionRunnerState,
} from './dataset-collection.service';

describe('DatasetCollectionService', () => {
  let service: DatasetCollectionService;
  let http: HttpTestingController;
  const baseUrl = `${environment.apiUrl}/admin/dataset-collection`;
  const participant: DatasetParticipant = {
    id: 7, participant_code: 'P007', consent_confirmed_at: '2026-07-17T08:30:00Z',
    state: 'active', withdrawn_at: null, created_at: '2026-07-17T08:31:00Z',
  };
  const stimulus: EmotionStimulus = {
    id: 11, title: 'Calm lake', file_path: 'stimuli/calm-lake.mp4', checksum: 'abc123',
    duration_seconds: 45, target_quadrant: 'positive_low', approval_state: 'approved',
    stimulus_set_version: 'v1', created_at: '2026-07-17T09:00:00Z',
  };
  const session: CollectionSession = {
    id: 13, participant_id: 7, device_id: 'muse-01', device_name: 'Muse 2',
    completed_trials: 2, total_trials: 8, state: 'in_progress',
    started_at: '2026-07-17T09:05:00Z', completed_at: null, created_at: '2026-07-17T09:04:00Z',
  };

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    service = TestBed.inject(DatasetCollectionService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('gets and emits the complete collection overview', () => {
    const response: CollectionOverview = {
      participants: 1, sessions: 2, trials: 3,
      review_counts: { pending: 1, accepted: 1, rejected: 1 },
      quadrant_counts: { positive_low: 2, positive_high: 1, negative_low: 3, negative_high: 4 },
    };
    let received: CollectionOverview | undefined;
    service.getOverview().subscribe(value => received = value);
    const request = http.expectOne(`${baseUrl}/overview`);
    expect(request.request.method).toBe('GET');
    request.flush(response);
    expect(received).toEqual(response);
  });

  it('lists and emits complete participants with skip and limit', () => {
    const response: CollectionList<DatasetParticipant> = { items: [participant] };
    let received: CollectionList<DatasetParticipant> | undefined;
    service.listParticipants(10, 25).subscribe(value => received = value);
    const request = http.expectOne(`${baseUrl}/participants?skip=10&limit=25`);
    expect(request.request.method).toBe('GET');
    request.flush(response);
    expect(received).toEqual(response);
  });

  it('creates and emits a complete participant while sending only consent_confirmed_at', () => {
    const body = { consent_confirmed_at: '2026-07-17T08:30:00Z' };
    let received: DatasetParticipant | undefined;
    service.createParticipant(body).subscribe(value => received = value);
    const request = http.expectOne(`${baseUrl}/participants`);
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual(body);
    request.flush(participant);
    expect(received).toEqual(participant);
  });

  it('lists and emits complete stimuli with skip and limit', () => {
    const response: CollectionList<EmotionStimulus> = { items: [stimulus] };
    let received: CollectionList<EmotionStimulus> | undefined;
    service.listStimuli(5, 50).subscribe(value => received = value);
    const request = http.expectOne(`${baseUrl}/stimuli?skip=5&limit=50`);
    expect(request.request.method).toBe('GET');
    request.flush(response);
    expect(received).toEqual(response);
  });

  it('creates and emits a complete stimulus while sending exact backend fields', () => {
    const { id, created_at, ...body } = stimulus;
    let received: EmotionStimulus | undefined;
    service.createStimulus(body).subscribe(value => received = value);
    const request = http.expectOne(`${baseUrl}/stimuli`);
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual(body);
    request.flush(stimulus);
    expect(received).toEqual(stimulus);
  });

  it('lists and emits complete sessions with skip and limit', () => {
    const response: CollectionList<CollectionSession> = { items: [session] };
    let received: CollectionList<CollectionSession> | undefined;
    service.listSessions(0, 100).subscribe(value => received = value);
    const request = http.expectOne(`${baseUrl}/sessions?skip=0&limit=100`);
    expect(request.request.method).toBe('GET');
    request.flush(response);
    expect(received).toEqual(response);
  });

  it('creates and emits a complete session while sending exact device details', () => {
    const body = { participant_id: 7, device_id: 'muse-01', device_name: 'Muse 2' };
    let received: CollectionSession | undefined;
    service.createSession(body).subscribe(value => received = value);
    const request = http.expectOne(`${baseUrl}/sessions`);
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual(body);
    request.flush(session);
    expect(received).toEqual(session);
  });

  describe('runner commands', () => {
    const runnerState: CollectionRunnerState = {
      session_id: 13,
      state: 'ready',
      active_baseline: null,
      current_trial_id: null,
      current_trial_order: null,
      current_stimulus_id: null,
      current_stimulus_title: null,
      trial_state: null,
      completed_trials: 0,
      total_trials: 12,
      next_trial_order: 1,
      next_trial_id: 21,
      next_stimulus_id: 11,
      next_stimulus_title: 'Calm lake',
      break_required: false,
      interruption_reason: null,
      accepted_clean_seconds: 0,
      wall_clock_seconds: 0,
      file_recovery_required: false,
      sensors: {
        tp9: { state: 'unknown', quality_score: 0, timestamp: 0, sequence: 0 }, af7: { state: 'unknown', quality_score: 0, timestamp: 0, sequence: 0 },
        af8: { state: 'unknown', quality_score: 0, timestamp: 0, sequence: 0 }, tp10: { state: 'unknown', quality_score: 0, timestamp: 0, sequence: 0 },
      },
      sampling_rate_hz: null, sampling_rate_ok: false, live_sensor_ready: false,
      stimulus_start_ready: false, quality_source: 'derived_eeg_window',
    };

    const expectPost = (call: () => void, path: string, body: unknown) => {
      call();
      const request = http.expectOne(`${baseUrl}/sessions/13${path}`);
      expect(request.request.method).toBe('POST');
      expect(request.request.body).toEqual(body);
      request.flush(runnerState);
    };

    it('creates the schedule without a browser-owned payload', () => {
      expectPost(() => service.createSchedule(13).subscribe(), '/schedule', null);
    });

    it('selects a device with the exact backend body', () => {
      const body = { device_id: 'muse-01', device_name: 'Muse 2' };
      expectPost(() => service.selectDevice(13, body).subscribe(), '/device', body);
    });

    it('starts either baseline without a browser timestamp', () => {
      expectPost(() => service.startBaseline(13, 'eyes_open').subscribe(), '/baseline/eyes_open/start', null);
    });

    it('starts Trial rest and stimulus and finishes stimulus without payloads', () => {
      expectPost(() => service.startTrialRest(13, 21).subscribe(), '/trials/21/rest/start', null);
      expectPost(() => service.startStimulus(13, 21).subscribe(), '/trials/21/stimulus/start', null);
      expectPost(() => service.finishStimulus(13, 21).subscribe(), '/trials/21/stimulus/finish', null);
    });

    it('marks an artifact with event type and optional note only', () => {
      const body = { event_type: 'movement', note: 'adjusted posture' };
      expectPost(() => service.markArtifact(13, 21, body).subscribe(), '/trials/21/artifacts', body);
    });

    it('submits only valence, arousal, and confidence ratings', () => {
      const body = { valence: 7, arousal: 4, confidence: 5 };
      expectPost(() => service.submitRating(13, 21, body).subscribe(), '/trials/21/rating', body);
    });

    it('interrupts with a reason and resumes without a browser-owned payload', () => {
      const body = { reason: 'operator emergency stop' };
      expectPost(() => service.interrupt(13, body).subscribe(), '/interrupt', body);
      expectPost(() => service.resume(13).subscribe(), '/resume', null);
    });

    it('gets the persisted runner state', () => {
      let received: CollectionRunnerState | undefined;
      service.getRunnerState(13).subscribe(value => received = value);
      const request = http.expectOne(`${baseUrl}/sessions/13/runner-state`);
      expect(request.request.method).toBe('GET');
      request.flush(runnerState);
      expect(received).toEqual(runnerState);
    });

    it('fetches authenticated stimulus media as a Blob without using its local path', () => {
      const media = new Blob(['video'], { type: 'video/mp4' });
      let received: Blob | undefined;
      service.getStimulusMedia(11).subscribe(value => received = value);
      const request = http.expectOne(`${baseUrl}/stimuli/11/media`);
      expect(request.request.method).toBe('GET');
      expect(request.request.responseType).toBe('blob');
      expect(request.request.url).not.toContain(stimulus.file_path);
      request.flush(media);
      expect(received).toBe(media);
    });
  });
});
