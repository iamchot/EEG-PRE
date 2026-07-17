import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of } from 'rxjs';

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

  [45, 60].forEach((duration) => it(`accepts a ${duration}-second stimulus`, () => {
    component.stimulus.duration_seconds = duration;
    expect(component.isStimulusDurationValid()).toBeTrue();
  }));

  [44, 61].forEach((duration) => it(`rejects a ${duration}-second stimulus`, () => {
    component.stimulus.duration_seconds = duration;
    expect(component.isStimulusDurationValid()).toBeFalse();
  }));

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

  it('shows an entertainment-only non-medical notice', () => {
    const notice = fixture.nativeElement.querySelector('[data-testid="non-medical-notice"]');
    expect(notice.textContent.toLowerCase()).toContain('entertainment');
    expect(notice.textContent.toLowerCase()).toContain('not medical');
  });

  it('loads component styles from styleUrl metadata', () => {
    const definition = (DatasetCollectionComponent as unknown as { ɵcmp: { styles: string[] } }).ɵcmp;
    expect(definition.styles.join(' ')).toMatch(/max-width:\s*1200px/);
  });
});
