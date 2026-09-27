import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of, Subject, throwError } from 'rxjs';

import { DatasetCollectionService } from '../../core/services/dataset-collection.service';
import { DatasetCollectionComponent } from './dataset-collection.component';

describe('DatasetCollectionComponent', () => {
  let fixture: ComponentFixture<DatasetCollectionComponent>;
  let component: DatasetCollectionComponent;
  let service: jasmine.SpyObj<DatasetCollectionService>;

  beforeEach(async () => {
    service = jasmine.createSpyObj<DatasetCollectionService>('DatasetCollectionService', [
      'getOverview', 'listParticipants', 'createParticipant', 'listStimuli',
      'createStimulus', 'listSessions', 'createSession',
      'withdrawParticipant', 'updateStimulusApproval', 'getAvailableStimuliFiles', 'inspectStimulusFile', 'uploadStimulusFile',
      'uploadAndCreateStimulus',
    ]);
    service.getOverview.and.returnValue(of({
      participants: 12,
      sessions: 7,
      trials: 48,
      review_counts: { pending: 3, accepted: 40, rejected: 5 },
      quadrant_counts: { positive_low: 10, positive_high: 12, negative_low: 14, negative_high: 12 },
    }));
    service.listParticipants.and.returnValue(of({ items: [] }));
    service.listStimuli.and.returnValue(of({ items: [] }));
    service.listSessions.and.returnValue(of({ items: [] }));
    service.createParticipant.and.returnValue(of({ id: 1, participant_code: 'P001', consent_confirmed_at: '2026-01-01T00:00:00Z', state: 'active', withdrawn_at: null, created_at: '2026-01-01T00:00:00Z' }));
    service.createStimulus.and.returnValue(of({ id: 1, ...({ title: 'Clip', file_path: '/media/clip.mp4', checksum: 'a'.repeat(64), duration_seconds: 45, target_quadrant: 'positive_low', approval_state: 'draft', stimulus_set_version: 'v1' } as const), created_at: '2026-01-01T00:00:00Z' }));
    service.createSession.and.returnValue(of({ id: 1, participant_id: 1, device_id: null, device_name: null, completed_trials: 0, total_trials: 0, state: 'preparation', started_at: null, completed_at: null, created_at: '2026-01-01T00:00:00Z' }));
    service.getAvailableStimuliFiles.and.returnValue(of({ files: ['relax/relax1.mp4', 'excited/excited1.mp4'], count: 2 }));
    service.withdrawParticipant.and.returnValue(of({ id: 1, participant_code: 'P001', consent_confirmed_at: '2026-01-01T00:00:00Z', state: 'withdrawn', withdrawn_at: '2026-03-01T10:00:00Z', created_at: '2026-01-01T00:00:00Z' }));
    service.updateStimulusApproval.and.returnValue(of({ id: 1, title: 'Clip', file_path: '/media/clip.mp4', checksum: 'a'.repeat(64), duration_seconds: 45, target_quadrant: 'positive_low', approval_state: 'approved', stimulus_set_version: 'v1', created_at: '2026-01-01T00:00:00Z' }));
    service.inspectStimulusFile.and.returnValue(of({ file_path: 'relax/relax1.mp4', checksum: 'b'.repeat(64), duration_seconds: 59.86, file_size_bytes: 1024, suggested_quadrant: 'positive_low', is_valid_duration: true }));
    service.uploadStimulusFile.and.returnValue(of({ file_path: 'relax/uploaded_relax.mp4', checksum: 'c'.repeat(64), duration_seconds: 55.0, file_size_bytes: 2048, suggested_quadrant: 'positive_low', is_valid_duration: true }));
    service.uploadAndCreateStimulus.and.returnValue(of({ id: 2, title: 'Uploaded Relax', file_path: 'relax/uploaded_relax.mp4', checksum: 'c'.repeat(64), duration_seconds: 55.0, target_quadrant: 'positive_low', approval_state: 'draft', stimulus_set_version: 'v1', created_at: '2026-01-01T00:00:00Z' }));

    await TestBed.configureTestingModule({
      imports: [DatasetCollectionComponent],
      providers: [provideRouter([]), { provide: DatasetCollectionService, useValue: service }],
    }).compileComponents();

    fixture = TestBed.createComponent(DatasetCollectionComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('loads the overview and renders its counts', () => {
    expect(service.getOverview).toHaveBeenCalled();
    const text = fixture.nativeElement.textContent;
    expect(text).toContain('12');
    expect(text).toContain('7');
    expect(text).toContain('48');
  });

  it('clears overview loading and renders an unavailable state after an overview error', () => {
    service.getOverview.and.returnValue(throwError(() => ({ error: { detail: 'Overview unavailable' } })));
    const local = TestBed.createComponent(DatasetCollectionComponent); local.detectChanges();
    expect(local.componentInstance.overviewLoading()).toBeFalse();
    expect(local.nativeElement.textContent).toContain('Overview unavailable');
    expect(local.nativeElement.textContent).toContain('Overview data is unavailable');
    expect(local.nativeElement.textContent).not.toContain('Loading overview');
    local.componentInstance.switchTab('participants'); local.detectChanges();
    expect(local.nativeElement.textContent).toContain('Overview unavailable');
  });

  it('never asks participants for name, email, or phone data', () => {
    component.switchTab('participants');
    fixture.detectChanges();
    const form: HTMLFormElement = fixture.nativeElement.querySelector('#participant-form');
    expect(form.querySelector('[name="name"], [name="email"], [name="phone"]')).toBeNull();
    expect(form.textContent?.toLowerCase()).not.toMatch(/name|email|phone/);
  });

  it('requires consent before participant submission', () => {
    component.switchTab('participants');
    fixture.detectChanges();
    const consent: HTMLInputElement = fixture.nativeElement.querySelector('#consent-confirmed');
    const submit: HTMLButtonElement = fixture.nativeElement.querySelector('#register-participant');
    expect(consent.required).toBeTrue();
    expect(submit.disabled).toBeTrue();
    component.consentConfirmed = true;
    fixture.detectChanges();
    expect(submit.disabled).toBeFalse();
  });

  it('blocks participant creation at the action boundary and sends the exact consent body', () => {
    component.registerParticipant();
    expect(service.createParticipant).not.toHaveBeenCalled();
    component.consentConfirmed = true;
    component.registerParticipant();
    const body = service.createParticipant.calls.mostRecent().args[0];
    expect(Object.keys(body)).toEqual(['consent_confirmed_at']);
    expect(new Date(body.consent_confirmed_at).toISOString()).toBe(body.consent_confirmed_at);
  });

  [45, 60].forEach((duration) => it(`accepts a ${duration}-second stimulus`, () => {
    component.stimulus.duration_seconds = duration;
    expect(component.isStimulusDurationValid()).toBeTrue();
  }));

  [44, 61].forEach((duration) => it(`rejects a ${duration}-second stimulus`, () => {
    component.stimulus.duration_seconds = duration;
    expect(component.isStimulusDurationValid()).toBeFalse();
  }));

  it('blocks invalid stimulus submissions and sends the exact valid body at both duration boundaries', () => {
    const base = { title: 'Clip', file_path: '/media/clip.mp4', checksum: 'a'.repeat(64), target_quadrant: 'negative_high' as const, approval_state: 'approved' as const, stimulus_set_version: 'set-2' };
    for (const duration_seconds of [44, 61]) { component.stimulus = { ...base, duration_seconds }; component.registerStimulus(); }
    expect(service.createStimulus).not.toHaveBeenCalled();
    for (const duration_seconds of [45, 60]) {
      component.stimulus = { ...base, duration_seconds }; component.registerStimulus();
      expect(service.createStimulus).toHaveBeenCalledWith({ ...base, duration_seconds });
    }
  });

  it('renders exactly the four supported quadrant options', () => {
    component.switchTab('stimuli');
    fixture.detectChanges();
    const values = Array.from(fixture.nativeElement.querySelectorAll('#target-quadrant option'))
      .map((option) => (option as HTMLOptionElement).value);
    expect(values).toEqual(['positive_low', 'positive_high', 'negative_low', 'negative_high']);
  });

  it('requires an active participant to start a session', () => {
    component.switchTab('sessions');
    fixture.detectChanges();
    const submit: HTMLButtonElement = fixture.nativeElement.querySelector('#create-session');
    expect(submit.disabled).toBeTrue();
  });

  it('does not create a session for a withdrawn participant id', () => {
    component.participants.set([{ id: 9, participant_code: 'P009', state: 'withdrawn', consent_confirmed_at: '2026-01-01T00:00:00Z', withdrawn_at: '2026-02-01T00:00:00Z', created_at: '2026-01-01T00:00:00Z' }]);
    component.sessionParticipantId = 9;
    component.createSession();
    expect(service.createSession).not.toHaveBeenCalled();
  });

  it('creates a session with the exact body for an active participant', () => {
    component.participants.set([{ id: 1, participant_code: 'P001', state: 'active', consent_confirmed_at: '2026-01-01T00:00:00Z', withdrawn_at: null, created_at: '2026-01-01T00:00:00Z' }]);
    component.sessionParticipantId = 1; component.deviceId = ' muse-1 '; component.deviceName = ' Lab Muse ';
    component.createSession();
    expect(service.createSession).toHaveBeenCalledWith({ participant_id: 1, device_id: 'muse-1', device_name: 'Lab Muse' });
  });

  it('guards duplicate participant submissions', () => {
    const pending = new Subject<never>(); service.createParticipant.and.returnValue(pending);
    component.consentConfirmed = true; component.registerParticipant(); component.registerParticipant();
    expect(service.createParticipant).toHaveBeenCalledTimes(1);
  });

  it('shows resource loading before empty content and clears loading after completion', () => {
    const participants = new Subject<any>(); service.listParticipants.and.returnValue(participants);
    const local = TestBed.createComponent(DatasetCollectionComponent); local.detectChanges();
    local.componentInstance.switchTab('participants'); local.detectChanges();
    expect(local.nativeElement.textContent).toContain('Loading participants');
    expect(local.nativeElement.textContent).not.toContain('No participants registered');
    participants.next({ items: [] }); participants.complete(); local.detectChanges();
    expect(local.nativeElement.textContent).toContain('No participants registered');
  });

  it('keeps stimuli and session empty messages hidden until each request completes', () => {
    const stimuli = new Subject<any>(); const sessions = new Subject<any>();
    service.listStimuli.and.returnValue(stimuli); service.listSessions.and.returnValue(sessions);
    const local = TestBed.createComponent(DatasetCollectionComponent); local.detectChanges();
    local.componentInstance.switchTab('stimuli'); local.detectChanges();
    expect(local.nativeElement.textContent).toContain('Loading stimuli');
    expect(local.nativeElement.textContent).not.toContain('No stimuli registered');
    stimuli.next({ items: [] }); stimuli.complete(); local.detectChanges();
    expect(local.nativeElement.textContent).toContain('No stimuli registered');
    local.componentInstance.switchTab('sessions'); local.detectChanges();
    expect(local.nativeElement.textContent).toContain('Loading sessions');
    sessions.next({ items: [] }); sessions.complete(); local.detectChanges();
    expect(local.nativeElement.textContent).toContain('No sessions created');
  });

  it('clears resource loading and renders the server error on failure', () => {
    service.listParticipants.and.returnValue(throwError(() => ({ error: { detail: 'Participants unavailable' } })));
    const local = TestBed.createComponent(DatasetCollectionComponent); local.detectChanges();
    local.componentInstance.switchTab('participants'); local.detectChanges();
    expect(local.componentInstance.participantsLoading()).toBeFalse();
    expect(local.nativeElement.textContent).toContain('Participants unavailable');
  });

  it('links tabs and panels and moves focus with keyboard navigation', () => {
    const tabs = Array.from(fixture.nativeElement.querySelectorAll('[role="tab"]')) as HTMLButtonElement[];
    expect(tabs[0].id).toBe('collection-tab-overview');
    expect(tabs[0].getAttribute('aria-controls')).toBe('collection-panel-overview');
    expect(tabs[0].tabIndex).toBe(0); expect(tabs[1].tabIndex).toBe(-1);
    tabs[0].dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight' })); fixture.detectChanges();
    expect(document.activeElement).toBe(tabs[1]);
    expect(fixture.nativeElement.querySelector('[role="tabpanel"]').getAttribute('aria-labelledby')).toBe('collection-tab-participants');
    tabs[1].dispatchEvent(new KeyboardEvent('keydown', { key: 'End' })); fixture.detectChanges();
    expect(document.activeElement).toBe(tabs[3]);
    tabs[3].dispatchEvent(new KeyboardEvent('keydown', { key: 'Home' })); fixture.detectChanges();
    expect(document.activeElement).toBe(tabs[0]);
    tabs[0].dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowLeft' })); fixture.detectChanges();
    expect(document.activeElement).toBe(tabs[3]);
  });

  it('shows an entertainment-only non-medical notice', () => {
    component.lang.setLanguage('en');
    fixture.detectChanges();
    const notice = fixture.nativeElement.querySelector('[data-testid="non-medical-notice"]');
    expect(notice.textContent.toLowerCase()).toContain('entertainment');
    expect(notice.textContent.toLowerCase()).toContain('not medical');
  });

  it('loads component styles from styleUrl metadata', () => {
    const definition = (DatasetCollectionComponent as unknown as { ɵcmp: { styles: string[] } }).ɵcmp;
    expect(definition.styles.join(' ')).toMatch(/max-width:\s*1200px/);
  });

  it('opens withdraw modal and confirms participant withdrawal', () => {
    const activeP = { id: 1, participant_code: 'P001', state: 'active' as const, consent_confirmed_at: '2026-01-01T00:00:00Z', withdrawn_at: null, created_at: '2026-01-01T00:00:00Z' };
    component.participants.set([activeP]);
    component.switchTab('participants');
    fixture.detectChanges();

    const withdrawBtn = fixture.nativeElement.querySelector('.btn-action-withdraw') as HTMLButtonElement;
    expect(withdrawBtn).toBeTruthy();
    withdrawBtn.click();
    fixture.detectChanges();

    expect(component.participantToWithdraw()).toEqual(activeP);
    const modal = fixture.nativeElement.querySelector('.modal-card');
    expect(modal).toBeTruthy();
    expect(modal.textContent).toContain('P001');

    component.confirmWithdraw();
    expect(service.withdrawParticipant).toHaveBeenCalledWith(1);
    expect(component.participantToWithdraw()).toBeNull();
    expect(component.participants()[0].state).toBe('withdrawn');
  });

  it('auto-detects stimulus file checksum and duration', () => {
    component.switchTab('stimuli');
    fixture.detectChanges();

    component.stimulus.file_path = 'relax/relax1.mp4';
    component.autoDetectStimulus();

    expect(service.inspectStimulusFile).toHaveBeenCalledWith('relax/relax1.mp4');
    expect(component.stimulus.checksum).toBe('b'.repeat(64));
    expect(component.stimulus.duration_seconds).toBe(59.86);
    expect(component.stimulus.target_quadrant).toBe('positive_low');
  });

  it('updates stimulus approval state through action buttons', () => {
    const draftStim = {
      id: 10,
      title: 'Relaxing Stream',
      file_path: 'relax/relax1.mp4',
      checksum: 'c'.repeat(64),
      duration_seconds: 59.86,
      target_quadrant: 'positive_low' as const,
      approval_state: 'draft' as const,
      stimulus_set_version: 'v1',
      created_at: '2026-01-01T00:00:00Z',
    };
    component.stimuli.set([draftStim]);
    component.switchTab('stimuli');
    fixture.detectChanges();

    component.updateStimulusApproval(draftStim, 'approved');
    expect(service.updateStimulusApproval).toHaveBeenCalledWith(10, 'approved');
  });

  it('handles direct video file selection deferred until registration', async () => {
    component.switchTab('stimuli');
    fixture.detectChanges();

    const file = new File(['fake content'], 'uploaded_relax.mp4', { type: 'video/mp4' });
    const event = { target: { files: [file], value: 'uploaded_relax.mp4' } } as unknown as Event;

    await component.onFileSelected(event);

    expect(component.pendingUploadFile()).toBe(file);
    expect(component.stimulus.file_path).toBe('positive_low/uploaded_relax.mp4');
    // Verify file is NOT uploaded immediately (deferred to prevent orphan files)
    expect(service.uploadStimulusFile).not.toHaveBeenCalled();

    // Now submit registration
    component.registerStimulus();
    expect(service.uploadAndCreateStimulus).toHaveBeenCalled();
    const calledArgs = service.uploadAndCreateStimulus.calls.mostRecent().args;
    expect(calledArgs[0]).toBe(file);
    expect(calledArgs[1].title).toBe('Uploaded relax');
    expect(calledArgs[1].target_quadrant).toBe('positive_low');
  });

  it('allows clearing pending uploaded file', async () => {
    component.switchTab('stimuli');
    fixture.detectChanges();

    const file = new File(['fake content'], 'uploaded_relax.mp4', { type: 'video/mp4' });
    const event = { target: { files: [file], value: 'uploaded_relax.mp4' } } as unknown as Event;

    await component.onFileSelected(event);
    expect(component.pendingUploadFile()).toBe(file);

    component.clearPendingFile();
    expect(component.pendingUploadFile()).toBeNull();
    expect(component.stimulus.file_path).toBe('');
  });

  it('selects file from library dropdown and triggers inspection', () => {
    component.switchTab('stimuli');
    fixture.detectChanges();

    const event = { target: { value: 'excited/excited1.mp4' } } as unknown as Event;
    component.onSelectLibraryFile(event);

    expect(component.stimulus.file_path).toBe('excited/excited1.mp4');
    expect(service.inspectStimulusFile).toHaveBeenCalledWith('excited/excited1.mp4');
  });
});
