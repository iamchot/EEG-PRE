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
  wallClockSeconds = computed(() => 0);
  isConnected = signal(true);
  connect = jasmine.createSpy('connect');
  disconnect = jasmine.createSpy('disconnect');
  sendCommand = jasmine.createSpy('sendCommand');
}

describe('EegSessionComponent', () => {
  let fixture: ComponentFixture<EegSessionComponent>;
  let component: EegSessionComponent;
  let http: HttpTestingController;
  let eegWs: EegWsStub;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [EegSessionComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: EegWsService, useClass: EegWsStub },
        { provide: PersonaService, useValue: { getAll: () => of([]) } },
        { provide: ComicService, useValue: { generate: () => of({ id: 1 }) } },
        {
          provide: Router,
          useValue: { navigate: jasmine.createSpy('navigate') },
        },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(EegSessionComponent);
    component = fixture.componentInstance;
    eegWs = TestBed.inject(EegWsService) as unknown as EegWsStub;
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
      ['BASELINE', '20 seconds neutral state'],
      ['READY', 'Ready to record emotion'],
      ['RECORDING', 'Recording clean EEG'],
      ['EMOTION_CONFIRMATION', 'Confirm emotion'],
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

  it('keeps connect disabled until selection and updates radio semantics', () => {
    const devices = [
      { name: 'Muse-A9C7', address: 'AA:BB' },
      { name: 'Muse-B123', address: 'CC:DD' },
    ];
    component.discoveredDevices.set(devices);
    fixture.detectChanges();

    const element = fixture.nativeElement as HTMLElement;
    const button = element.querySelector<HTMLButtonElement>('#btn-connect');
    expect(element.querySelector('[role="radiogroup"]')).not.toBeNull();
    let radios = Array.from(element.querySelectorAll('[role="radio"]'));
    expect(radios.length).toBe(2);
    expect(radios.map((radio) => radio.getAttribute('aria-checked'))).toEqual([
      'false',
      'false',
    ]);
    expect(button?.disabled).toBeTrue();

    component.selectDevice(devices[1]);
    fixture.detectChanges();
    radios = Array.from(element.querySelectorAll('[role="radio"]'));
    expect(radios.map((radio) => radio.getAttribute('aria-checked'))).toEqual([
      'false',
      'true',
    ]);
    expect(button?.disabled).toBeFalse();
  });

  it('uses roving tabindex and arrow keys to move device selection', () => {
    const devices = [
      { name: 'Muse-A9C7', address: 'AA:BB' },
      { name: 'Muse-B123', address: 'CC:DD' },
    ];
    component.discoveredDevices.set(devices);
    fixture.detectChanges();

    let radios = Array.from(
      (fixture.nativeElement as HTMLElement).querySelectorAll<HTMLButtonElement>(
        '[role="radio"]'
      )
    );
    expect(radios.map((radio) => radio.tabIndex)).toEqual([0, -1]);

    radios[0].focus();
    radios[0].dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true }));
    fixture.detectChanges();

    radios = Array.from(
      (fixture.nativeElement as HTMLElement).querySelectorAll<HTMLButtonElement>(
        '[role="radio"]'
      )
    );
    expect(component.selectedDevice()).toEqual(devices[1]);
    expect(radios.map((radio) => radio.tabIndex)).toEqual([-1, 0]);
    expect(document.activeElement).toBe(radios[1]);

    radios[1].dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowLeft', bubbles: true }));
    fixture.detectChanges();
    expect(component.selectedDevice()).toEqual(devices[0]);
  });

  it('disables scanning while the local connection service is unavailable', () => {
    eegWs.isConnected.set(false);
    fixture.detectChanges();

    const button = (fixture.nativeElement as HTMLElement)
      .querySelector<HTMLButtonElement>('#btn-scan');
    expect(button?.disabled).toBeTrue();
  });

  it('guards direct scan attempts while the local connection service is unavailable', () => {
    eegWs.isConnected.set(false);

    component.scanDevices();

    http.expectNone(`${environment.apiUrl}/sessions/scan`);
    expect(component.scanning()).toBeFalse();
  });

  it('renders a successful scan and sends the phase transition', () => {
    const device = { name: 'Muse-A9C7', address: 'AA:BB' };

    component.scanDevices();
    http.expectOne(`${environment.apiUrl}/sessions/scan`).flush({
      devices: [device],
    });
    fixture.detectChanges();

    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(text).toContain(device.name);
    expect(text).toContain(device.address);
    expect(eegWs.sendCommand).toHaveBeenCalledOnceWith('phase_transition', {
      phase: 'DEVICE_CONFIRMATION',
    });
  });

  it('shows a retry action when a scan finds no device', () => {
    component.scanDevices();
    http.expectOne(`${environment.apiUrl}/sessions/scan`).flush({ devices: [] });
    fixture.detectChanges();

    expect(component.scanError()).not.toBe('');
    expect((fixture.nativeElement as HTMLElement).querySelector('#btn-scan'))
      .not.toBeNull();
  });

  it('shows a retry action when scanning fails', () => {
    component.scanDevices();
    http
      .expectOne(`${environment.apiUrl}/sessions/scan`)
      .flush('failed', { status: 503, statusText: 'Unavailable' });
    fixture.detectChanges();

    expect(component.scanError()).not.toBe('');
    expect(component.discoveredDevices()).toEqual([]);
    expect((fixture.nativeElement as HTMLElement).querySelector('#btn-scan'))
      .not.toBeNull();
  });

  it('uses the exact confirm-device POST contract and command', () => {
    const device = { name: 'Muse-A9C7', address: 'AA:BB' };
    component.selectDevice(device);

    component.confirmDevice();

    const request = http.expectOne(
      `${environment.apiUrl}/sessions/7/confirm-device?device_name=Muse-A9C7&device_id=AA:BB`
    );
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toBeNull();
    request.flush({});
    expect(eegWs.sendCommand).toHaveBeenCalledOnceWith('confirm_device', {
      device_name: device.name,
      device_id: device.address,
    });
  });

  it('retains selection, explains connection failure, allows retry, and sends no command on failure', () => {
    const device = { name: 'Muse-A9C7', address: 'AA:BB' };
    component.discoveredDevices.set([device]);
    component.selectDevice(device);

    component.confirmDevice();
    http
      .expectOne(
        `${environment.apiUrl}/sessions/7/confirm-device?device_name=Muse-A9C7&device_id=AA:BB`
      )
      .flush('failed', { status: 503, statusText: 'Unavailable' });
    fixture.detectChanges();

    expect(component.selectedDevice()).toEqual(device);
    expect(component.connectionError()).toContain('Muse-A9C7');
    expect((fixture.nativeElement as HTMLElement).textContent).toContain(
      component.connectionError()
    );
    expect(eegWs.sendCommand).not.toHaveBeenCalledWith(
      'confirm_device',
      jasmine.anything()
    );

    component.confirmDevice();
    http
      .expectOne(
        `${environment.apiUrl}/sessions/7/confirm-device?device_name=Muse-A9C7&device_id=AA:BB`
      )
      .flush({});
    expect(component.connectionError()).toBe('');
    expect(eegWs.sendCommand).toHaveBeenCalledOnceWith('confirm_device', {
      device_name: device.name,
      device_id: device.address,
    });
  });

  it('uses the exact start-baseline POST contract and command', () => {
    component.startBaseline();

    const request = http.expectOne(`${environment.apiUrl}/sessions/7/start-baseline`);
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual({});
    request.flush({});
    expect(eegWs.sendCommand).toHaveBeenCalledOnceWith('start_baseline');
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

  it('shows exactly three fitting instructions', () => {
    setPhase('FITTING');
    expect(
      (fixture.nativeElement as HTMLElement).querySelectorAll('.fitting-list li')
        .length
    ).toBe(3);
  });

  it('shows the complete disconnected warning copy', () => {
    eegWs.isConnected.set(false);
    fixture.detectChanges();

    const warning = (fixture.nativeElement as HTMLElement).querySelector(
      '.inline-message.warning'
    );
    expect(warning?.textContent?.replace(/\s+/g, ' ').trim()).toBe(
      'เปิดบริการเชื่อมต่อในเครื่องให้พร้อมก่อนค้นหา Muse 2'
    );
  });

  it('keeps the entertainment and non-medical note visible', () => {
    const note = (fixture.nativeElement as HTMLElement).querySelector(
      '.entertainment-note'
    );
    expect(note?.textContent).toContain('ความบันเทิง');
    expect(note?.textContent).toContain('ไม่ใช่การวินิจฉัยทางการแพทย์');
  });
});
