import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ActivatedRoute, provideRouter } from '@angular/router';
import { signal } from '@angular/core';
import { of, throwError } from 'rxjs';

import { authGuard, adminGuard } from '../../core/guards/auth.guard';
import {
  CollectionRunnerState,
  DatasetCollectionService,
} from '../../core/services/dataset-collection.service';
import { DatasetCollectionWsService } from '../../core/services/dataset-collection-ws.service';
import { routes } from '../../app.routes';
import { DatasetCollectionRunnerComponent } from './dataset-collection-runner.component';

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
  ...overrides,
});

describe('DatasetCollectionRunnerComponent', () => {
  let fixture: ComponentFixture<DatasetCollectionRunnerComponent>;
  let component: DatasetCollectionRunnerComponent;
  let api: jasmine.SpyObj<DatasetCollectionService>;
  let ws: { state: ReturnType<typeof signal<CollectionRunnerState | null>>; isConnected: ReturnType<typeof signal<boolean>>; connect: jasmine.Spy; disconnect: jasmine.Spy };

  beforeEach(async () => {
    api = jasmine.createSpyObj<DatasetCollectionService>('DatasetCollectionService', [
      'getRunnerState', 'selectDevice', 'startBaseline', 'startTrialRest', 'startStimulus',
      'finishStimulus', 'markArtifact', 'submitRating', 'interrupt', 'resume',
      'getStimulusMedia', 'createSchedule',
    ]);
    api.getRunnerState.and.returnValue(of(runnerState()));
    for (const method of ['selectDevice', 'startBaseline', 'startTrialRest', 'startStimulus', 'finishStimulus', 'markArtifact', 'submitRating', 'interrupt', 'resume'] as const) {
      api[method].and.returnValue(of(runnerState()));
    }
    api.getStimulusMedia.and.returnValue(of(new Blob(['video'], { type: 'video/mp4' })));
    ws = { state: signal<CollectionRunnerState | null>(null), isConnected: signal(false), connect: jasmine.createSpy('connect'), disconnect: jasmine.createSpy('disconnect') };

    await TestBed.configureTestingModule({
      imports: [DatasetCollectionRunnerComponent],
      providers: [
        provideRouter([]),
        { provide: ActivatedRoute, useValue: { snapshot: { paramMap: { get: (key: string) => key === 'id' ? '13' : null } } } },
        { provide: DatasetCollectionService, useValue: api },
        { provide: DatasetCollectionWsService, useValue: ws },
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
    expect(api.createSchedule).not.toHaveBeenCalled();
  });

  it('registers the runner route with both authentication and Admin guards', () => {
    const route = routes.find(item => item.path === 'admin/dataset-collection/sessions/:id/run');
    expect(route).toBeDefined();
    expect(route?.canActivate).toEqual([authGuard, adminGuard]);
  });

  it('renders Creative Headset Setup, Muse sensor points, device selection, and the non-medical notice', () => {
    const text = fixture.nativeElement.textContent;
    expect(text).toContain('Creative Headset Setup');
    expect(text).toContain('TP9');
    expect(text).toContain('AF7');
    expect(text).toContain('AF8');
    expect(text).toContain('TP10');
    expect(fixture.nativeElement.querySelector('#device-id')).not.toBeNull();
    expect(text.toLowerCase()).toContain('entertainment');
    expect(text.toLowerCase()).toContain('not medical');
  });

  it('shows eyes-open before eyes-closed with exact wall and clean targets', () => {
    component.startBaseline('eyes_closed');
    expect(api.startBaseline).not.toHaveBeenCalled();
    api.startBaseline.and.returnValue(of(runnerState({ state: 'baseline', active_baseline: 'eyes_open' })));
    component.startBaseline('eyes_open');
    expect(api.startBaseline).toHaveBeenCalledOnceWith(13, 'eyes_open');
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('60');
    expect(fixture.nativeElement.textContent).toContain('30');
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

  it('starts only after playing, finishes once on ended, and sends no browser marker payload', () => {
    component.applyState(runnerState({ state: 'in_progress', current_trial_id: 21, current_trial_order: 3, current_stimulus_id: 11, current_stimulus_title: 'Calm lake', trial_state: 'rest' }));
    component.onPlaying();
    component.onPlaying();
    expect(api.startStimulus).toHaveBeenCalledOnceWith(13, 21);
    component.applyState(runnerState({ state: 'in_progress', current_trial_id: 21, current_trial_order: 3, current_stimulus_id: 11, current_stimulus_title: 'Calm lake', trial_state: 'stimulus' }));
    component.onEnded();
    component.onEnded();
    expect(api.finishStimulus).toHaveBeenCalledOnceWith(13, 21);
  });

  it('allows artifact event type and note only during stimulus', () => {
    component.markArtifact('blink');
    expect(api.markArtifact).not.toHaveBeenCalled();
    component.applyState(runnerState({ state: 'in_progress', current_trial_id: 21, current_trial_order: 4, current_stimulus_id: 11, trial_state: 'stimulus' }));
    component.artifactNote = 'participant blinked';
    component.markArtifact('blink');
    expect(api.markArtifact).toHaveBeenCalledOnceWith(13, 21, { event_type: 'blink', note: 'participant blinked' });
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
});
