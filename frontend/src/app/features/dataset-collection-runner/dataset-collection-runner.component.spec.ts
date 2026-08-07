import { ComponentFixture, fakeAsync, flushMicrotasks, TestBed, tick } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ActivatedRoute, provideRouter } from '@angular/router';
import { signal } from '@angular/core';
import { of, Subject, throwError } from 'rxjs';

import { authGuard, adminGuard } from '../../core/guards/auth.guard';
import {
  CollectionRunnerState,
  DatasetCollectionService,
} from '../../core/services/dataset-collection.service';
import { DatasetCollectionWsService } from '../../core/services/dataset-collection-ws.service';
import { MuseDeviceService } from '../../core/services/muse-device.service';
import { environment } from '../../../environments/environment';
import { routes } from '../../app.routes';
import { DatasetCollectionComponent } from '../dataset-collection/dataset-collection.component';
import { DatasetCollectionRunnerComponent } from './dataset-collection-runner.component';

const measuredGoodSensors: CollectionRunnerState['sensors'] = {
  tp9: { state: 'good', quality_score: 81, timestamp: 10, sequence: 1 },
  af7: { state: 'good', quality_score: 82, timestamp: 10, sequence: 1 },
  af8: { state: 'good', quality_score: 83, timestamp: 10, sequence: 1 },
  tp10: { state: 'good', quality_score: 84, timestamp: 10, sequence: 1 },
};

const runnerState = (overrides: Partial<CollectionRunnerState> = {}): CollectionRunnerState => ({
  session_id: 13,
  state: 'preparation',
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
    tp9: { state: 'unknown', quality_score: 0, timestamp: 0, sequence: 0 },
    af7: { state: 'unknown', quality_score: 0, timestamp: 0, sequence: 0 },
    af8: { state: 'unknown', quality_score: 0, timestamp: 0, sequence: 0 },
    tp10: { state: 'unknown', quality_score: 0, timestamp: 0, sequence: 0 },
  },
  sampling_rate_hz: null,
  sampling_rate_ok: false,
  live_sensor_ready: false,
  stimulus_start_ready: false,
  quality_source: 'derived_eeg_window',
  ...overrides,
});

describe('DatasetCollectionRunnerComponent Admin Muse HTTP contract', () => {
  let fixture: ComponentFixture<DatasetCollectionRunnerComponent>;
  let component: DatasetCollectionRunnerComponent;
  let api: jasmine.SpyObj<DatasetCollectionService>;
  let ws: {
    state: ReturnType<typeof signal<CollectionRunnerState | null>>;
    streamError: ReturnType<typeof signal<string | null>>;
    isConnected: ReturnType<typeof signal<boolean>>;
    connect: jasmine.Spy;
    disconnect: jasmine.Spy;
  };
  let http: HttpTestingController;

  beforeEach(async () => {
    api = jasmine.createSpyObj<DatasetCollectionService>('DatasetCollectionService', [
      'getRunnerState', 'selectDevice', 'startBaseline', 'startTrialRest', 'startStimulus',
      'finishStimulus', 'markArtifact', 'submitRating', 'interrupt', 'resume', 'getStimulusMedia', 'createSchedule',
    ]);
    api.getRunnerState.and.returnValue(of(runnerState({ total_trials: 0, next_trial_order: null, next_trial_id: null, next_stimulus_id: null, next_stimulus_title: null })));
    api.selectDevice.and.returnValue(of(runnerState({ total_trials: 0, next_trial_order: null, next_trial_id: null, next_stimulus_id: null, next_stimulus_title: null })));
    ws = {
      state: signal<CollectionRunnerState | null>(null), streamError: signal<string | null>(null), isConnected: signal(false),
      connect: jasmine.createSpy('connect'), disconnect: jasmine.createSpy('disconnect'),
    };
    await TestBed.configureTestingModule({
      imports: [DatasetCollectionRunnerComponent],
      providers: [
        provideRouter([]), provideHttpClient(), provideHttpClientTesting(), MuseDeviceService,
        { provide: ActivatedRoute, useValue: { snapshot: { paramMap: { get: (key: string) => key === 'id' ? '13' : null } } } },
        { provide: DatasetCollectionService, useValue: api },
        { provide: DatasetCollectionWsService, useValue: ws },
      ],
    }).compileComponents();
    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(DatasetCollectionRunnerComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  afterEach(() => { fixture.destroy(); http.verify(); });

  it('posts a discovered Admin Muse and persists it only after the real service poll verifies connected', fakeAsync(() => {
    component.connectMuse({ address: 'AA:BB:CC:DD', name: 'Studio Muse' });
    const connect = http.expectOne(`${environment.apiUrl}/admin/dataset-collection/sessions/13/muse`);
    expect(connect.request.body).toEqual({ address: 'AA:BB:CC:DD', name: 'Studio Muse' });
    connect.flush({ owner: { kind: 'collection', session_id: 13 }, state: 'waiting_for_lsl', detail: null });
    expect(api.selectDevice).not.toHaveBeenCalled();

    tick(500);
    http.expectOne(`${environment.apiUrl}/admin/dataset-collection/sessions/13/muse`).flush({
      owner: { kind: 'collection', session_id: 13 }, state: 'connected', detail: null,
    });
    fixture.detectChanges();
    expect(api.selectDevice).toHaveBeenCalledOnceWith(13, { device_id: 'AA:BB:CC:DD', device_name: 'Studio Muse' });

    TestBed.inject(MuseDeviceService).disconnectAdmin(13).subscribe();
    const disconnect = http.expectOne(`${environment.apiUrl}/admin/dataset-collection/sessions/13/muse`);
    expect(disconnect.request.method).toBe('DELETE');
    disconnect.flush({ owner: { kind: 'collection', session_id: 13 }, state: 'idle', detail: null });
  }));
});

describe('DatasetCollectionRunnerComponent', () => {
  let fixture: ComponentFixture<DatasetCollectionRunnerComponent>;
  let component: DatasetCollectionRunnerComponent;
  let api: jasmine.SpyObj<DatasetCollectionService>;
  let ws: {
    state: ReturnType<typeof signal<CollectionRunnerState | null>>;
    streamError: ReturnType<typeof signal<string | null>>;
    isConnected: ReturnType<typeof signal<boolean>>;
    connect: jasmine.Spy;
    disconnect: jasmine.Spy;
  };
  let muse: {
    scanStatus: ReturnType<typeof signal>;
    connectionStatus: ReturnType<typeof signal>;
    connectedDevice: ReturnType<typeof signal>;
    scan: jasmine.Spy;
    connectAdmin: jasmine.Spy;
  };

  beforeEach(async () => {
    api = jasmine.createSpyObj<DatasetCollectionService>('DatasetCollectionService', [
      'getRunnerState', 'selectDevice', 'startBaseline', 'startTrialRest', 'startStimulus',
      'finishStimulus', 'markArtifact', 'submitRating', 'interrupt', 'resume',
      'getStimulusMedia', 'createSchedule',
      'getOverview', 'listParticipants', 'listStimuli', 'listSessions', 'createParticipant',
      'createStimulus', 'createSession',
    ]);
    api.getRunnerState.and.returnValue(of(runnerState({ total_trials: 0, next_trial_order: null, next_trial_id: null, next_stimulus_id: null, next_stimulus_title: null })));
    for (const method of ['selectDevice', 'startBaseline', 'startTrialRest', 'startStimulus', 'finishStimulus', 'markArtifact', 'submitRating', 'interrupt', 'resume'] as const) {
      api[method].and.returnValue(of(runnerState()));
    }
    api.getStimulusMedia.and.returnValue(of(new Blob(['video'], { type: 'video/mp4' })));
    api.getOverview.and.returnValue(of({ participants: 0, sessions: 0, trials: 0, review_counts: { pending: 0, accepted: 0, rejected: 0 }, quadrant_counts: { positive_low: 0, positive_high: 0, negative_low: 0, negative_high: 0 } }));
    api.listParticipants.and.returnValue(of({ items: [] })); api.listStimuli.and.returnValue(of({ items: [] })); api.listSessions.and.returnValue(of({ items: [] }));
    ws = {
      state: signal<CollectionRunnerState | null>(null),
      streamError: signal<string | null>(null),
      isConnected: signal(false),
      connect: jasmine.createSpy('connect'),
      disconnect: jasmine.createSpy('disconnect'),
    };
    muse = {
      scanStatus: signal({ scanId: null, state: 'idle', devices: [], detail: null }),
      connectionStatus: signal({ owner: null, state: 'idle', detail: null }),
      connectedDevice: signal(null),
      scan: jasmine.createSpy('scan'),
      connectAdmin: jasmine.createSpy('connectAdmin'),
    };

    await TestBed.configureTestingModule({
      imports: [DatasetCollectionRunnerComponent, DatasetCollectionComponent],
      providers: [
        provideRouter([]),
        { provide: ActivatedRoute, useValue: { snapshot: { paramMap: { get: (key: string) => key === 'id' ? '13' : null } } } },
        { provide: DatasetCollectionService, useValue: api },
        { provide: DatasetCollectionWsService, useValue: ws },
        { provide: MuseDeviceService, useValue: muse },
      ],
    }).compileComponents();
    fixture = TestBed.createComponent(DatasetCollectionRunnerComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  afterEach(() => fixture.destroy());

  it('loads the route session id, connects its Admin stream, and never regenerates a schedule on refresh', () => {
    expect(api.getRunnerState).toHaveBeenCalledOnceWith(13);
    expect(ws.connect).toHaveBeenCalledOnceWith(13);
    expect(muse.connectAdmin).not.toHaveBeenCalled();
    expect(api.createSchedule).not.toHaveBeenCalled();
    expect(fixture.nativeElement.textContent).toContain('Schedule not prepared');
    expect(fixture.nativeElement.textContent).not.toContain('Trial 12');
  });

  it('persists a discovered Muse only after the exact managed connected stage and an explicit schedule click', () => {
    const device = { address: 'AA:BB:CC:DD', name: 'Studio Muse' };
    muse.scanStatus.set({ scanId: 'scan-1', state: 'found', devices: [device], detail: null });
    muse.connectAdmin.and.returnValue(of({ owner: { kind: 'collection', sessionId: 13 }, state: 'waiting_for_lsl', detail: null }));
    api.selectDevice.and.returnValue(of(runnerState({ total_trials: 0, next_trial_order: null, next_trial_id: null, next_stimulus_id: null, next_stimulus_title: null })));
    api.createSchedule.and.returnValue(of(runnerState({ total_trials: 12 })));
    fixture.detectChanges();

    const deviceButton = fixture.nativeElement.querySelector('[data-muse-device]') as HTMLButtonElement;
    expect(deviceButton).not.toBeNull();
    deviceButton.click();
    expect(muse.connectAdmin).toHaveBeenCalledOnceWith(13, device);
    expect(api.selectDevice).not.toHaveBeenCalled();

    muse.connectAdmin.and.returnValue(of({ owner: { kind: 'collection', sessionId: 13 }, state: 'connected', detail: null }));
    deviceButton.click();
    expect(api.selectDevice).toHaveBeenCalledOnceWith(13, { device_id: 'AA:BB:CC:DD', device_name: 'Studio Muse' });

    fixture.detectChanges();
    const schedule = fixture.nativeElement.querySelector('#prepare-schedule') as HTMLButtonElement;
    expect(schedule).not.toBeNull();
    schedule.click();
    expect(api.createSchedule).toHaveBeenCalledOnceWith(13);
  });

  it('registers the runner route with both authentication and Admin guards', () => {
    const route = routes.find(item => item.path === 'admin/dataset-collection/sessions/:id/run');
    expect(route).toBeDefined();
    expect(route?.canActivate).toEqual([authGuard, adminGuard]);
  });

  it('renders Creative Headset Setup, Muse discovery progress, sensor points, and the non-medical notice', () => {
    muse.connectionStatus.set({ owner: { kind: 'collection', sessionId: 13 }, state: 'waiting_for_lsl', detail: null });
    fixture.detectChanges();
    const text = fixture.nativeElement.textContent;
    expect(text).toContain('Creative Headset Setup');
    expect(text).toContain('TP9');
    expect(text).toContain('AF7');
    expect(text).toContain('AF8');
    expect(text).toContain('TP10');
    expect(fixture.nativeElement.querySelector('#scan-muse')).not.toBeNull();
    expect(fixture.nativeElement.querySelector('#device-id')).toBeNull();
    expect(fixture.nativeElement.querySelector('#device-name')).toBeNull();
    expect(text).toContain('Waiting for LSL');
    expect(text.toLowerCase()).toContain('entertainment');
    expect(text.toLowerCase()).toContain('not medical');
    expect(text).toContain('derived EEG');
  });

  it('shows eyes-open before eyes-closed with exact wall and clean targets', () => {
    component.startBaseline('eyes_closed');
    expect(api.startBaseline).not.toHaveBeenCalled();
    ws.isConnected.set(true);
    component.applyState(runnerState({ total_trials: 12, sensors: measuredGoodSensors, sampling_rate_hz: 256, sampling_rate_ok: true, live_sensor_ready: true }));
    component.devicePersisted.set(true);
    for (const key of component.sensorKeys) component.setContact(key, true);
    api.startBaseline.and.returnValue(of(runnerState({ state: 'baseline', active_baseline: 'eyes_open' })));
    component.startBaseline('eyes_open');
    expect(api.startBaseline).toHaveBeenCalledOnceWith(13, 'eyes_open');
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('60');
    expect(fixture.nativeElement.textContent).toContain('30');
  });

  it('keeps manual confirmations separate and gates baseline on four measured live sensors too', () => {
    ws.isConnected.set(true);
    component.devicePersisted.set(true);
    fixture.detectChanges();
    const confirmations = Array.from(fixture.nativeElement.querySelectorAll('[data-contact-confirmation]')) as HTMLInputElement[];
    expect(confirmations.length).toBe(4);
    expect(fixture.nativeElement.textContent).toContain('การยืนยันการสัมผัสโดย Admin');
    component.applyState(runnerState({ total_trials: 12, sensors: measuredGoodSensors, sampling_rate_hz: 256, sampling_rate_ok: true, live_sensor_ready: true }));
    expect(component.canStartBaseline()).toBeFalse();
    for (const input of confirmations) { input.click(); fixture.detectChanges(); }
    expect(component.sensorStatus('tp9').state).toBe('good');
    expect(component.sensorStatus('af7').state).toBe('good');
    expect(component.sensorStatus('af8').state).toBe('good');
    expect(component.sensorStatus('tp10').state).toBe('good');
    expect(component.sensorStatus('tp9').quality_score).toBe(81);
    expect(component.canStartBaseline()).toBeTrue();
    fixture.detectChanges();
    expect((fixture.nativeElement.querySelector('[data-stage="device"] button:last-of-type') as HTMLButtonElement).disabled).toBeFalse();
  });

  it('pauses and rewinds an early rest playback attempt until backend readiness', () => {
    component.applyState(runnerState({ state: 'in_progress', current_trial_id: 21, current_stimulus_id: 11, trial_state: 'rest', stimulus_start_ready: false }));
    const video = { pause: jasmine.createSpy('pause'), currentTime: 4 } as unknown as HTMLVideoElement;
    component.onPlaying(video);
    expect(video.pause).toHaveBeenCalled();
    expect(video.currentTime).toBe(0);
    expect(api.startStimulus).not.toHaveBeenCalled();
  });

  it('rewinds and exposes retry when backend rejects a playing event', () => {
    api.startStimulus.and.returnValue(throwError(() => ({ error: { detail: 'rest not ready' } })));
    component.applyState(runnerState({ state: 'in_progress', current_trial_id: 21, current_stimulus_id: 11, trial_state: 'rest', stimulus_start_ready: true }));
    const video = { pause: jasmine.createSpy('pause'), currentTime: 4 } as unknown as HTMLVideoElement;
    component.onPlaying(video);
    expect(video.pause).toHaveBeenCalled();
    expect(video.currentTime).toBe(0);
    expect(component.startRetryAvailable()).toBeTrue();
  });

  it('holds playback at zero until backend accepts stimulus start, then resumes once', () => {
    const accepted = new Subject<CollectionRunnerState>();
    api.startStimulus.and.returnValue(accepted);
    component.applyState(runnerState({ state: 'in_progress', current_trial_id: 21, current_stimulus_id: 11, trial_state: 'rest', stimulus_start_ready: true }));
    const video = { pause: jasmine.createSpy('pause'), play: jasmine.createSpy('play').and.resolveTo(), currentTime: 5 } as unknown as HTMLVideoElement;

    component.onPlaying(video);

    expect(video.pause).toHaveBeenCalledOnceWith();
    expect(video.currentTime).toBe(0);
    expect(video.play).not.toHaveBeenCalled();
    accepted.next(runnerState({ state: 'in_progress', current_trial_id: 21, current_stimulus_id: 11, trial_state: 'stimulus' }));
    accepted.complete();
    expect(video.play).toHaveBeenCalledTimes(1);
  });

  it('interrupts backend exactly once when post-start video resume is rejected', fakeAsync(() => {
    api.startStimulus.and.returnValue(of(runnerState({ state: 'in_progress', current_trial_id: 21, current_stimulus_id: 11, trial_state: 'stimulus' })));
    api.interrupt.and.returnValue(of(runnerState({ state: 'interrupted', current_trial_id: 21, current_stimulus_id: 11, trial_state: 'interrupted', interruption_reason: 'Stimulus playback failed after Backend start' })));
    component.applyState(runnerState({ state: 'in_progress', current_trial_id: 21, current_stimulus_id: 11, trial_state: 'rest', stimulus_start_ready: true }));
    const video = {
      pause: jasmine.createSpy('pause'),
      play: jasmine.createSpy('play').and.rejectWith(new DOMException('play blocked', 'NotAllowedError')),
      currentTime: 8,
    } as unknown as HTMLVideoElement;

    component.onPlaying(video);
    flushMicrotasks();

    expect(api.startStimulus).toHaveBeenCalledOnceWith(13, 21);
    expect(api.interrupt).toHaveBeenCalledOnceWith(13, { reason: 'Stimulus playback failed after Backend start' });
    expect(api.finishStimulus).not.toHaveBeenCalled();
    expect(video.currentTime).toBe(0);
    expect(component.runnerState()?.state).toBe('interrupted');
    expect(component.error()).toContain('playback');
  }));

  it('interrupts backend when delayed playback rejection arrives during another request', fakeAsync(() => {
    let rejectPlayback!: (reason?: unknown) => void;
    const playback = new Promise<void>((_, reject) => { rejectPlayback = reject; });
    const artifactPending = new Subject<CollectionRunnerState>();
    api.startStimulus.and.returnValue(of(runnerState({ state: 'in_progress', current_trial_id: 21, current_stimulus_id: 11, trial_state: 'stimulus' })));
    api.markArtifact.and.returnValue(artifactPending);
    api.interrupt.and.returnValue(of(runnerState({ state: 'interrupted', current_trial_id: 21, current_stimulus_id: 11, trial_state: 'interrupted', interruption_reason: 'Stimulus playback failed after Backend start' })));
    component.applyState(runnerState({ state: 'in_progress', current_trial_id: 21, current_stimulus_id: 11, trial_state: 'rest', stimulus_start_ready: true }));
    const video = {
      pause: jasmine.createSpy('pause'),
      play: jasmine.createSpy('play').and.returnValue(playback),
      currentTime: 8,
    } as unknown as HTMLVideoElement;

    component.onPlaying(video);
    component.markArtifact('blink');
    expect(component.busy()).toBeTrue();
    rejectPlayback(new DOMException('decode failed', 'NotSupportedError'));
    flushMicrotasks();

    expect(api.interrupt).toHaveBeenCalledOnceWith(13, { reason: 'Stimulus playback failed after Backend start' });
    expect(video.currentTime).toBe(0);
    expect(component.runnerState()?.state).toBe('interrupted');
    expect(component.error()).toContain('playback');
  }));

  it('recovers a persisted device from a scheduled baseline state and restarts eyes-closed without reselecting', () => {
    ws.isConnected.set(true);
    component.applyState(runnerState({ state: 'baseline', active_baseline: null, total_trials: 12, sensors: measuredGoodSensors, sampling_rate_hz: 256, sampling_rate_ok: true, live_sensor_ready: true }));
    for (const key of component.sensorKeys) component.setContact(key, true);
    expect(component.devicePersisted()).toBeTrue();
    expect(component.canStartBaseline()).toBeTrue();
    component.startBaseline('eyes_closed');
    expect(api.selectDevice).not.toHaveBeenCalled();
    expect(api.startBaseline).toHaveBeenCalledOnceWith(13, 'eyes_closed');
  });

  it('does not infer a device for a pristine unscheduled preparation state', () => {
    component.applyState(runnerState({ state: 'preparation', total_trials: 0 }));
    expect(component.devicePersisted()).toBeFalse();
  });

  it('resets all contact confirmations when selecting a different Muse', () => {
    component.applyState(runnerState({ state: 'preparation', total_trials: 12, sensors: measuredGoodSensors, sampling_rate_hz: 256, sampling_rate_ok: true, live_sensor_ready: true }));
    for (const key of component.sensorKeys) component.setContact(key, true);
    ws.isConnected.set(true);
    expect(component.canStartBaseline()).toBeTrue();
    muse.connectAdmin.and.returnValue(of({ owner: { kind: 'collection', sessionId: 13 }, state: 'connected', detail: null }));
    component.connectMuse({ address: 'AA:BB:CC:DD', name: 'Muse-B' });
    for (const key of component.sensorKeys) expect(component.sensorStatus(key).state).toBe('unknown');
    expect(component.canStartBaseline()).toBeFalse();
  });

  it('creates and revokes authenticated media object URLs and blocks playback after load failure', () => {
    const create = spyOn(URL, 'createObjectURL').and.returnValue('blob:clip');
    const revoke = spyOn(URL, 'revokeObjectURL');
    component.applyState(runnerState({ state: 'in_progress', current_trial_id: 21, current_trial_order: 1, current_stimulus_id: 11, current_stimulus_title: 'Calm lake', trial_state: 'rest' }));
    expect(api.getStimulusMedia).toHaveBeenCalledWith(11);
    expect(create).toHaveBeenCalled();
    expect(component.mediaUrl()).toBe('blob:clip');
    component.onMediaError();
    component.onPlaying();
    expect(api.startStimulus).not.toHaveBeenCalled();
    fixture.destroy();
    expect(revoke).toHaveBeenCalledWith('blob:clip');
  });

  it('revokes a current object URL exactly once immediately when the video reports an error', () => {
    spyOn(URL, 'createObjectURL').and.returnValue('blob:broken');
    const revoke = spyOn(URL, 'revokeObjectURL');
    component.applyState(runnerState({ state: 'in_progress', current_trial_id: 21, current_trial_order: 1, current_stimulus_id: 11, trial_state: 'rest' }));
    const video = { pause: jasmine.createSpy('pause'), currentTime: 7 } as unknown as HTMLVideoElement;
    component.onMediaError(video);
    expect(revoke).toHaveBeenCalledOnceWith('blob:broken');
    expect(video.pause).toHaveBeenCalled();
    expect(video.currentTime).toBe(0);
    expect(component.mediaUrl()).toBeNull();
    expect(component.mediaError()).toBeTrue();
    component.ngOnDestroy();
    expect(revoke).toHaveBeenCalledTimes(1);
  });

  it('interrupts Backend exactly once when media fails after stimulus start', () => {
    spyOn(URL, 'createObjectURL').and.returnValue('blob:broken-after-start');
    api.interrupt.and.returnValue(of(runnerState({
      state: 'interrupted',
      current_trial_id: 21,
      current_stimulus_id: 11,
      trial_state: 'interrupted',
      interruption_reason: 'Stimulus playback failed after Backend start',
    })));
    component.applyState(runnerState({
      state: 'in_progress',
      current_trial_id: 21,
      current_trial_order: 1,
      current_stimulus_id: 11,
      trial_state: 'stimulus',
    }));
    const video = {
      pause: jasmine.createSpy('pause'),
      currentTime: 20,
    } as unknown as HTMLVideoElement;

    component.onMediaError(video);
    component.onMediaError(video);

    expect(api.interrupt).toHaveBeenCalledOnceWith(13, {
      reason: 'Stimulus playback failed after Backend start',
    });
    expect(component.runnerState()?.state).toBe('interrupted');
    expect(component.error()).toContain('playback');
  });

  it('shows safe Muse stream errors to the operator', () => {
    ws.streamError.set('Muse disconnected');

    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('Muse disconnected');
  });

  it('starts only after playing, finishes once on ended, and sends no browser marker payload', () => {
    component.applyState(runnerState({ state: 'in_progress', current_trial_id: 21, current_trial_order: 3, current_stimulus_id: 11, current_stimulus_title: 'Calm lake', trial_state: 'rest', stimulus_start_ready: true }));
    const video = { pause: jasmine.createSpy('pause'), play: jasmine.createSpy('play').and.resolveTo(), currentTime: 0 } as unknown as HTMLVideoElement;
    component.onPlaying(video);
    component.onPlaying(video);
    expect(api.startStimulus).toHaveBeenCalledOnceWith(13, 21);
    component.applyState(runnerState({ state: 'in_progress', current_trial_id: 21, current_trial_order: 3, current_stimulus_id: 11, current_stimulus_title: 'Calm lake', trial_state: 'stimulus' }));
    component.onEnded();
    component.onEnded();
    expect(api.finishStimulus).toHaveBeenCalledOnceWith(13, 21);
  });

  it('does not rewind a synchronized stimulus when playback resumes after buffering', () => {
    api.startStimulus.and.returnValue(of(runnerState({ state: 'in_progress', current_trial_id: 21, current_stimulus_id: 11, trial_state: 'stimulus' })));
    component.applyState(runnerState({ state: 'in_progress', current_trial_id: 21, current_stimulus_id: 11, trial_state: 'rest', stimulus_start_ready: true }));
    const video = { pause: jasmine.createSpy('pause'), play: jasmine.createSpy('play').and.resolveTo(), currentTime: 12 } as unknown as HTMLVideoElement;
    component.onPlaying(video);
    video.currentTime = 12;
    component.onPlaying(video);
    expect(video.pause).toHaveBeenCalledTimes(1);
    expect(video.currentTime).toBe(12);
    expect(api.startStimulus).toHaveBeenCalledTimes(1);
  });

  it('queues ended behind an in-flight artifact and retries a failed finish without stranding the Trial', () => {
    const artifactResult = new Subject<CollectionRunnerState>();
    const finishResult = new Subject<CollectionRunnerState>();
    api.markArtifact.and.returnValue(artifactResult);
    api.finishStimulus.and.returnValue(finishResult);
    component.applyState(runnerState({ state: 'in_progress', current_trial_id: 21, current_trial_order: 3, current_stimulus_id: 11, trial_state: 'stimulus' }));
    component.markArtifact('blink');
    component.onEnded();
    component.onEnded();
    expect(api.finishStimulus).not.toHaveBeenCalled();
    artifactResult.next(runnerState({ state: 'in_progress', current_trial_id: 21, current_trial_order: 3, current_stimulus_id: 11, trial_state: 'stimulus' }));
    artifactResult.complete();
    expect(api.finishStimulus).toHaveBeenCalledOnceWith(13, 21);
    finishResult.error({ error: { detail: 'temporary finish failure' } });
    expect(component.finishRetryAvailable()).toBeTrue();
    api.finishStimulus.and.returnValue(of(runnerState({ state: 'in_progress', current_trial_id: 21, current_trial_order: 3, current_stimulus_id: 11, trial_state: 'rating' })));
    component.retryFinish();
    expect(api.finishStimulus).toHaveBeenCalledTimes(2);
    expect(component.finishRetryAvailable()).toBeFalse();
  });

  it('allows artifact event type and note only during stimulus', () => {
    component.markArtifact('blink');
    expect(api.markArtifact).not.toHaveBeenCalled();
    component.applyState(runnerState({ state: 'in_progress', current_trial_id: 21, current_trial_order: 4, current_stimulus_id: 11, trial_state: 'stimulus' }));
    component.artifactNote = 'participant blinked';
    component.markArtifact('blink');
    expect(api.markArtifact).toHaveBeenCalledOnceWith(13, 21, { event_type: 'blink', note: 'participant blinked' });
  });

  it('disables artifact buttons while a marker is pending and preserves its note until accepted', () => {
    const pending = new Subject<CollectionRunnerState>();
    api.markArtifact.and.returnValue(pending);
    component.applyState(runnerState({ state: 'in_progress', current_trial_id: 21, current_stimulus_id: 11, trial_state: 'stimulus' }));
    component.artifactNote = 'keep this note';
    component.markArtifact('blink');
    fixture.detectChanges();
    const buttons = Array.from(fixture.nativeElement.querySelectorAll('.artifact-grid button')) as HTMLButtonElement[];
    expect(buttons.length).toBeGreaterThan(0);
    expect(buttons.every(button => button.disabled)).toBeTrue();
    component.markArtifact('cough');
    expect(api.markArtifact).toHaveBeenCalledTimes(1);
    expect(component.artifactNote).toBe('keep this note');
    pending.next(runnerState({ state: 'in_progress', current_trial_id: 21, current_stimulus_id: 11, trial_state: 'stimulus' }));
    pending.complete();
    expect(component.artifactNote).toBe('');
  });

  it('enforces 1–9, 1–9, 1–5 ratings and sends the exact request body', () => {
    component.applyState(runnerState({ state: 'in_progress', current_trial_id: 21, current_trial_order: 4, current_stimulus_id: 11, trial_state: 'rating' }));
    component.valence = 0; component.arousal = 9; component.confidence = 5; component.submitRating();
    expect(api.submitRating).not.toHaveBeenCalled();
    component.valence = 7; component.arousal = 3; component.confidence = 4; component.submitRating();
    expect(api.submitRating).toHaveBeenCalledOnceWith(13, 21, { valence: 7, arousal: 3, confidence: 4 });
  });

  it('shows Trial N/12 and a break after the sixth completed Trial', () => {
    component.applyState(runnerState({ state: 'in_progress', completed_trials: 6, next_trial_order: 7, break_required: true }));
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Trial 7 / 12');
    expect(fixture.nativeElement.querySelector('[data-stage="break"]')).not.toBeNull();
  });

  it('offers same-order restart after interruption and requires confirmation before emergency stop', () => {
    component.applyState(runnerState({ state: 'interrupted', current_trial_id: 21, current_trial_order: 5, trial_state: 'interrupted', interruption_reason: 'Muse disconnected' }));
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Trial 5');
    component.resume();
    expect(api.resume).toHaveBeenCalledOnceWith(13);
    component.applyState(runnerState({ state: 'in_progress', current_trial_id: 21, current_trial_order: 5, current_stimulus_id: 11, trial_state: 'rest' }));
    const confirm = spyOn(window, 'confirm').and.returnValues(false, true);
    component.emergencyStop();
    expect(api.interrupt).not.toHaveBeenCalled();
    component.emergencyStop();
    expect(confirm).toHaveBeenCalledTimes(2);
    expect(api.interrupt).toHaveBeenCalledOnceWith(13, { reason: 'Emergency stop confirmed by Admin' });
  });

  it('reports media fetch failure and never exposes a filesystem path or quadrant', () => {
    api.getStimulusMedia.and.returnValue(throwError(() => new Error('missing media')));
    component.applyState(runnerState({ state: 'in_progress', current_trial_id: 21, current_trial_order: 2, current_stimulus_id: 11, current_stimulus_title: 'Calm lake', trial_state: 'rest' }));
    fixture.detectChanges();
    expect(component.mediaReady()).toBeFalse();
    expect(fixture.nativeElement.textContent).toContain('โหลดคลิปไม่สำเร็จ');
    expect(fixture.nativeElement.textContent).not.toContain('file_path');
    expect(fixture.nativeElement.textContent).not.toContain('positive_low');
  });

  it('uses true 44px navigation targets in the runner and Foundation session list', () => {
    const back = fixture.nativeElement.querySelector('.back-link') as HTMLAnchorElement;
    expect(getComputedStyle(back).display).toBe('inline-flex');
    expect(getComputedStyle(back).minHeight).toBe('44px');
    api.listSessions.and.returnValue(of({ items: [
      { id: 13, participant_id: 1, device_id: 'muse', device_name: 'Muse 2', completed_trials: 0, total_trials: 12, state: 'ready', started_at: null, completed_at: null, created_at: '2026-01-01T00:00:00Z' },
      { id: 14, participant_id: 1, device_id: 'muse', device_name: 'Muse 2', completed_trials: 12, total_trials: 12, state: 'completed', started_at: null, completed_at: '2026-01-01T01:00:00Z', created_at: '2026-01-01T00:00:00Z' },
    ] }));
    const foundation = TestBed.createComponent(DatasetCollectionComponent); foundation.detectChanges();
    foundation.componentInstance.switchTab('sessions'); foundation.detectChanges();
    const buttons = Array.from(foundation.nativeElement.querySelectorAll('.list-row button')) as HTMLButtonElement[];
    expect(buttons.map(button => button.textContent?.trim())).toEqual(['Start / Resume', 'View summary']);
    expect(buttons.every(button => getComputedStyle(button).minHeight === '44px')).toBeTrue();
    foundation.destroy();
  });

  it('ignores a late initial GET after newer websocket state and cancels GET/media work on destroy', () => {
    fixture.destroy();
    const initial = new Subject<CollectionRunnerState>();
    const media = new Subject<Blob>();
    api.getRunnerState.and.returnValue(initial);
    api.getStimulusMedia.and.returnValue(media);
    const local = TestBed.createComponent(DatasetCollectionRunnerComponent);
    local.detectChanges();
    ws.state.set(runnerState({ state: 'in_progress', completed_trials: 4, next_trial_order: 5 }));
    local.detectChanges();
    initial.next(runnerState({ state: 'preparation', completed_trials: 0 }));
    expect(local.componentInstance.runnerState()?.completed_trials).toBe(4);
    local.componentInstance.applyState(runnerState({ state: 'in_progress', current_trial_id: 21, current_stimulus_id: 11, trial_state: 'rest' }));
    local.destroy();
    spyOn(URL, 'createObjectURL');
    media.next(new Blob(['late']));
    expect(URL.createObjectURL).not.toHaveBeenCalled();
  });
});
