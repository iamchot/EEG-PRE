import { provideHttpClient } from '@angular/common/http';
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing';
import { computed, signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Router } from '@angular/router';
import { of } from 'rxjs';
import { environment } from '../../../environments/environment';
import { ComicService } from '../../core/services/comic.service';
import {
  EEGMessage,
  EegWsService,
  SensorStatus,
} from '../../core/services/eeg-ws.service';
import { LanguageService } from '../../core/services/language.service';
import { MuseWebBluetoothService, MuseWebBtState } from '../../core/services/muse-web-bluetooth.service';
import { PersonaService } from '../../core/services/persona.service';
import { EegSessionComponent } from './eeg-session.component';

const sensor = (state: SensorStatus['state']): SensorStatus => ({
  state,
  quality_score: state === 'good' ? 100 : 0,
  timestamp: 0,
  sequence: 0,
});

class EegWsStub {
  latestMessage = signal<EEGMessage | null>(null);
  phase = computed(() => this.latestMessage()?.phase ?? 'DISCOVERING');
  sensors = computed(() => ({
    tp9: this.latestMessage()?.tp9 ?? sensor('unknown'),
    af7: this.latestMessage()?.af7 ?? sensor('unknown'),
    af8: this.latestMessage()?.af8 ?? sensor('unknown'),
    tp10: this.latestMessage()?.tp10 ?? sensor('unknown'),
  }));
  allSensorsGood = computed(() =>
    Object.values(this.sensors()).every((item) => item.state === 'good')
  );
  acceptedSeconds = computed(() => 0);
  baselineSeconds = computed(() => 0);
  baselineSubphase = computed(() => 'eyes_open' as const);
  baselineCleanSeconds = computed(() => 0);
  baselineWallSeconds = computed(() => 0);
  eyesOpenComplete = computed(() => false);
  eyesClosedComplete = computed(() => false);
  wallClockSeconds = computed(() => 0);
  isConnected = signal(true);
  connect = jasmine.createSpy('connect');
  disconnect = jasmine.createSpy('disconnect');
  sendCommand = jasmine.createSpy('sendCommand');
  sendEegSample = jasmine.createSpy('sendEegSample');
}

class MuseWebBtStub {
  state = signal<MuseWebBtState>('idle');
  error = signal('');
  deviceName = signal<string | null>(null);
  deviceId = signal<string | null>(null);
  isSupported = true;
  connect = jasmine.createSpy('connect').and.resolveTo('Muse-TEST');
  disconnect = jasmine.createSpy('disconnect');
}

describe('EegSessionComponent', () => {
  let fixture: ComponentFixture<EegSessionComponent>;
  let component: EegSessionComponent;
  let http: HttpTestingController;
  let eegWs: EegWsStub;
  let museBt: MuseWebBtStub;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [EegSessionComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: EegWsService, useClass: EegWsStub },
        { provide: MuseWebBluetoothService, useClass: MuseWebBtStub },
        { provide: PersonaService, useValue: { getAll: () => of([]) } },
        { provide: ComicService, useValue: { generate: () => of({ id: 1 }) } },
        {
          provide: Router,
          useValue: { navigate: jasmine.createSpy('navigate') },
        },
      ],
    }).compileComponents();

    TestBed.inject(LanguageService).setLanguage('en');
    fixture = TestBed.createComponent(EegSessionComponent);
    component = fixture.componentInstance;
    eegWs = TestBed.inject(EegWsService) as unknown as EegWsStub;
    museBt = TestBed.inject(MuseWebBluetoothService) as unknown as MuseWebBtStub;
    http = TestBed.inject(HttpTestingController);
    fixture.detectChanges();
    http.expectOne(`${environment.apiUrl}/sessions`).flush({ id: 7 });
    fixture.detectChanges();
  });

  afterEach(() => http.verify());

  function setPhase(
    phase: EEGMessage['phase'],
    states: Partial<
      Record<'tp9' | 'af7' | 'af8' | 'tp10', SensorStatus['state']>
    > = {}
  ) {
    if (!['DISCOVERING', 'DEVICE_CONFIRMATION', 'CONNECTING'].includes(phase)) {
      museBt.state.set('streaming');
    }
    eegWs.latestMessage.set({
      phase,
      tp9: sensor(states.tp9 ?? 'good'),
      af7: sensor(states.af7 ?? 'good'),
      af8: sensor(states.af8 ?? 'good'),
      tp10: sensor(states.tp10 ?? 'good'),
    } as EEGMessage);
    fixture.detectChanges();
  }

  it('presents a four-step entertainment-focused setup', () => {
    const element = fixture.nativeElement as HTMLElement;
    const text = element.textContent ?? '';

    expect(element.querySelectorAll('.step').length).toBe(4);
    expect(text).toContain('Muse 2');
    expect(element.querySelector('.entertainment-note')?.textContent?.trim())
      .toBeTruthy();
    expect(text).not.toContain('Dream Lab');
    expect(text).not.toContain('WebSocket');
  });

  it('maps every backend phase across the four setup steps', () => {
    const expectations: Array<[EEGMessage['phase'], string, string]> = [
      ['DISCOVERING', 'device', 'connect'],
      ['DEVICE_CONFIRMATION', 'device', 'connect'],
      ['CONNECTING', 'device', 'connect'],
      ['PREPARATION', 'prepare', 'signal'],
      ['FITTING', 'prepare', 'signal'],
      ['BASELINE', 'baseline', 'signal'],
      ['READY', 'ready', 'emotion'],
      ['RECORDING', 'record', 'emotion'],
      ['PAUSED_SIGNAL_QUALITY', 'record', 'emotion'],
      ['EMOTION_CONFIRMATION', 'emotion', 'emotion'],
      ['COMPLETED', 'emotion', 'emotion'],
    ];

    expectations.forEach(([phase, stage, step]) => {
      setPhase(phase);
      expect(component.stage()).withContext(phase).toBe(stage);
      expect(component.activeStepKey()).withContext(phase).toBe(step);
    });

    component.generating.set(true);
    fixture.detectChanges();
    expect(component.stage()).toBe('generate');
    expect(component.activeStepKey()).toBe('comic');
  });

  it('keeps content for baseline, ready, record, emotion, and generate stages', () => {
    const expectations: Array<[EEGMessage['phase'], string]> = [
      ['BASELINE', 'Baseline 1 of 2 : Eyes Open'],
      ['READY', 'Ready to record EEG stream'],
      ['RECORDING', 'Recording 30s Clean EEG'],
      ['EMOTION_CONFIRMATION', 'Confirm Emotion Classification'],
    ];

    expectations.forEach(([phase, content]) => {
      setPhase(phase);
      expect((fixture.nativeElement as HTMLElement).textContent)
        .withContext(phase)
        .toContain(content);
    });

    component.generating.set(true);
    fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain(
      'Creating your Dream Comic'
    );
  });

  it('connects headset via Web Bluetooth and sends confirm_device command', async () => {
    await component.scanDevices();
    expect(museBt.connect).toHaveBeenCalledOnceWith(jasmine.any(Function));
    expect(eegWs.sendCommand).toHaveBeenCalledWith('confirm_device', {
      device_name: 'Muse-TEST',
      device_id: 'Muse-TEST',
    });
  });

  it('shows connection spinner and guidance while Web Bluetooth is connecting', () => {
    museBt.state.set('connecting');
    fixture.detectChanges();

    const element = fixture.nativeElement as HTMLElement;
    expect(element.querySelector('.spinner')).not.toBeNull();
    expect(element.querySelector('.device-status.busy')).not.toBeNull();
    expect(element.querySelector<HTMLButtonElement>('#btn-scan')).toBeNull();
  });

  it('explains unsupported browser warning when Web Bluetooth is not supported', () => {
    museBt.isSupported = false;
    fixture.detectChanges();

    const warning = (fixture.nativeElement as HTMLElement).querySelector('.inline-message.warning');
    expect(warning?.textContent).toContain('Web Bluetooth');
  });

  it('maps typed device states to semantic classes', () => {
    const element = fixture.nativeElement as HTMLElement;
    expect(element.querySelector('.device-state.idle')).not.toBeNull();

    museBt.state.set('connecting');
    fixture.detectChanges();
    expect(element.querySelector('.device-state.busy')).not.toBeNull();

    museBt.state.set('failed');
    fixture.detectChanges();
    expect(element.querySelector('.device-state.failed')).not.toBeNull();

    museBt.state.set('streaming');
    fixture.detectChanges();
    expect(element.querySelector('.service-status.connected')).not.toBeNull();
  });

  it('advances to sensor fitting only after a verified streaming status', () => {
    setPhase('FITTING');
    museBt.state.set('connecting');
    fixture.detectChanges();
    expect(component.stage()).toBe('device');
    expect((fixture.nativeElement as HTMLElement).querySelector('#btn-baseline')).toBeNull();

    museBt.state.set('streaming');
    fixture.detectChanges();
    expect(component.stage()).toBe('prepare');
    expect((fixture.nativeElement as HTMLElement).querySelector('#btn-baseline')).not.toBeNull();
  });

  it('clears a typed connection failure when retrying', async () => {
    component.connectError.set('Connection error');
    fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).querySelector('[role="alert"]')?.textContent)
      .toContain('Connection error');

    await component.scanDevices();
    fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).querySelector('[role="alert"]')).toBeNull();
  });

  it('does not treat a green transport connection as green sensor contacts', () => {
    museBt.state.set('streaming');
    setPhase('FITTING', { tp9: 'poor' });

    const element = fixture.nativeElement as HTMLElement;
    expect(element.querySelector('[data-state="poor"]')).not.toBeNull();
    expect(element.querySelector<HTMLButtonElement>('#btn-baseline')?.disabled).toBeTrue();
  });

  it('uses the exact start-baseline POST contract and command', () => {
    component.startBaseline('eyes_open');

    const request = http.expectOne(`${environment.apiUrl}/sessions/7/start-baseline?subphase=eyes_open`);
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual({});
    request.flush({});
    expect(eegWs.sendCommand).toHaveBeenCalledOnceWith('start_baseline', { subphase: 'eyes_open' });
  });

  ['tp9', 'af7', 'af8', 'tp10'].forEach((sensorName) => {
    it(`keeps Baseline disabled when only ${sensorName.toUpperCase()} is not good`, () => {
      setPhase('FITTING', {
        [sensorName]: 'poor',
      } as Partial<
        Record<'tp9' | 'af7' | 'af8' | 'tp10', SensorStatus['state']>
      >);

      const button = (
        fixture.nativeElement as HTMLElement
      ).querySelector<HTMLButtonElement>('#btn-baseline');
      expect(button?.disabled).toBeTrue();
    });
  });

  it('enables Baseline only when all four sensors are good', () => {
    setPhase('FITTING');
    const button = (
      fixture.nativeElement as HTMLElement
    ).querySelector<HTMLButtonElement>('#btn-baseline');
    expect(button?.disabled).toBeFalse();
  });

  it('renders all four sensor pills with percentage scores and quality labels in step 2', () => {
    setPhase('FITTING', { tp9: 'good', af7: 'poor' });
    museBt.state.set('streaming');
    fixture.detectChanges();

    const pills = (fixture.nativeElement as HTMLElement).querySelectorAll('.sensor-pill');
    expect(pills.length).toBe(4);
    expect(component.sensorQualityScore('tp9')).toBe('100%');
    expect(component.sensorQualityLabel('tp9')).toBe('Good Contact');
    expect(component.sensorQualityLabel('af7')).toBe('Poor Contact');
  });

  it('renders centered SVG checkmarks for completed steps', () => {
    setPhase('BASELINE');
    museBt.state.set('streaming');
    fixture.detectChanges();

    const stepChecks = (fixture.nativeElement as HTMLElement).querySelectorAll('.step.done svg.step-check');
    expect(stepChecks.length).toBeGreaterThan(0);
    stepChecks.forEach(svg => {
      expect(svg.getAttribute('viewBox')).toBe('0 0 14 14');
    });
  });

  it('displays two-step baseline duration and clean signal progress', () => {
    setPhase('BASELINE');
    museBt.state.set('streaming');
    fixture.detectChanges();

    const element = fixture.nativeElement as HTMLElement;
    const progress = element.querySelector<HTMLProgressElement>('.session-progress');
    expect(progress?.getAttribute('max')).toBe('30');
    expect(element.textContent).toContain('Baseline 1 of 2 : Eyes Open');
    expect(element.textContent).toContain('60');
    expect(element.textContent).toContain('/ 30');
  });

  it('shows exactly three fitting instructions', () => {
    setPhase('FITTING');
    expect(
      (fixture.nativeElement as HTMLElement).querySelectorAll('.fitting-list li')
        .length
    ).toBe(3);
  });

  it('keeps the entertainment and non-medical note visible', () => {
    const note = (fixture.nativeElement as HTMLElement).querySelector(
      '.entertainment-note'
    );
    expect(note?.textContent).toContain('comic story generation');
    expect(note?.textContent).toContain('not medical diagnosis');
  });
});
