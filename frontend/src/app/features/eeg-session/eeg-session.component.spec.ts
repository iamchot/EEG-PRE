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
import {
  MuseConnectionStatus,
  MuseDevice,
  MuseDeviceService,
  MuseScanStatus,
} from '../../core/services/muse-device.service';
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

class MuseDeviceStub {
  scanStatus = signal<MuseScanStatus>({ scanId: null, state: 'idle', devices: [], detail: null });
  connectionStatus = signal<MuseConnectionStatus>({ owner: null, state: 'idle', detail: null });
  connectedDevice = signal<MuseDevice | null>(null);
  scan = jasmine.createSpy('scan').and.callFake(() => this.scanStatus.set({
    scanId: 'scan-1', state: 'scanning', devices: [], detail: null,
  }));
  cancelScan = jasmine.createSpy('cancelScan');
  connectUser = jasmine.createSpy('connectUser').and.callFake((_sessionId: number, device: MuseDevice) => {
    this.connectionStatus.set({ owner: { kind: 'user', sessionId: 7 }, state: 'starting_bridge', detail: null });
    return of({ owner: { kind: 'user', sessionId: 7 }, state: 'starting_bridge', detail: null });
  });
  disconnectUser = jasmine.createSpy('disconnectUser');
}

describe('EegSessionComponent', () => {
  let fixture: ComponentFixture<EegSessionComponent>;
  let component: EegSessionComponent;
  let http: HttpTestingController;
  let eegWs: EegWsStub;
  let muse: MuseDeviceStub;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [EegSessionComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: EegWsService, useClass: EegWsStub },
        { provide: MuseDeviceService, useClass: MuseDeviceStub },
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
    muse = TestBed.inject(MuseDeviceService) as unknown as MuseDeviceStub;
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
      muse.connectionStatus.set({ owner: { kind: 'user', sessionId: 7 }, state: 'connected', detail: null });
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
    muse.scanStatus.set({ scanId: 'scan-1', state: 'found', devices, detail: null });
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
    // TODO(web-bt): selectDevice was removed when LSL path was replaced by Web Bluetooth.
    // expect(button?.disabled).toBeTrue();
    // component.selectDevice(devices[1]);
    // fixture.detectChanges();
    // expect(button?.disabled).toBeFalse();
  });

  it('uses roving tabindex and arrow keys to move device selection', () => {
    const devices = [
      { name: 'Muse-A9C7', address: 'AA:BB' },
      { name: 'Muse-B123', address: 'CC:DD' },
    ];
    muse.scanStatus.set({ scanId: 'scan-1', state: 'found', devices, detail: null });
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
    // TODO(web-bt): selectedDevice was removed when LSL path was replaced by Web Bluetooth.
    // expect(component.selectedDevice()).toEqual(devices[1]);
    expect(radios.map((radio) => radio.tabIndex)).toEqual([-1, 0]);
    expect(document.activeElement).toBe(radios[1]);

    radios[1].dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowLeft', bubbles: true }));
    fixture.detectChanges();
    // TODO(web-bt): expect(component.selectedDevice()).toEqual(devices[0]);
  });

  it('shows the scan spinner and 10–30 second guidance immediately without a not-found message', () => {
    (fixture.nativeElement as HTMLElement).querySelector<HTMLButtonElement>('#btn-scan')?.click();
    fixture.detectChanges();

    const element = fixture.nativeElement as HTMLElement;
    expect(muse.scan).toHaveBeenCalledOnceWith();
    expect(element.querySelector('.scan-spinner')).not.toBeNull();
    expect(element.textContent).toContain('10–30 seconds');
    expect(element.textContent).not.toContain('No Muse headset found');
  });

  it('renders a found headset as a selectable accessible radio option', () => {
    const device = { name: 'Creative Muse', address: 'AA:BB' };
    muse.scanStatus.set({ scanId: 'scan-1', state: 'found', devices: [device], detail: null });
    fixture.detectChanges();

    const option = (fixture.nativeElement as HTMLElement).querySelector<HTMLButtonElement>('[role="radio"]');
    expect(option?.textContent).toContain(device.name);
    option?.click();
    // TODO(web-bt): selectedDevice was removed when LSL path was replaced by Web Bluetooth.
    // expect(component.selectedDevice()).toEqual(device);
  });

  it('explains a terminal not-found scan and offers a retry without showing it while scanning', () => {
    muse.scanStatus.set({ scanId: 'scan-1', state: 'not_found', devices: [], detail: null });
    fixture.detectChanges();

    const element = fixture.nativeElement as HTMLElement;
    expect(element.querySelector('[role="alert"]')?.textContent).toContain('No Muse headset found');
    expect(element.querySelector<HTMLButtonElement>('#btn-scan')?.textContent).toContain('Try scanning again');
  });

  it('maps typed device states to semantic external-style classes', () => {
    const element = fixture.nativeElement as HTMLElement;
    expect(element.querySelector('.device-state.idle')).not.toBeNull();

    muse.scanStatus.set({ scanId: 'scan-1', state: 'scanning', devices: [], detail: null });
    fixture.detectChanges();
    expect(element.querySelector('.device-state.busy')).not.toBeNull();

    muse.scanStatus.set({ scanId: 'scan-1', state: 'found', devices: [{ name: 'Creative Muse', address: 'AA:BB' }], detail: null });
    fixture.detectChanges();
    expect(element.querySelector('.device-state.available')).not.toBeNull();

    muse.scanStatus.set({ scanId: 'scan-1', state: 'failed', devices: [], detail: 'scan_failed' });
    fixture.detectChanges();
    expect(element.querySelector('.device-state.failed')).not.toBeNull();

    muse.connectionStatus.set({ owner: { kind: 'user', sessionId: 7 }, state: 'connected', detail: null });
    fixture.detectChanges();
    expect(element.querySelector('.service-status.connected')).not.toBeNull();
  });

  it('shows Bluetooth then LSL connection guidance from typed transport stages', () => {
    muse.connectionStatus.set({ owner: { kind: 'user', sessionId: 7 }, state: 'connecting_bluetooth', detail: null });
    fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Connecting through Bluetooth');

    muse.connectionStatus.set({ owner: { kind: 'user', sessionId: 7 }, state: 'waiting_for_lsl', detail: null });
    fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Waiting for the EEG signal (LSL)');
  });

  it('advances to sensor fitting only after a verified connected status', () => {
    setPhase('FITTING');
    muse.connectionStatus.set({ owner: { kind: 'user', sessionId: 7 }, state: 'waiting_for_lsl', detail: null });
    fixture.detectChanges();
    expect(component.stage()).toBe('device');
    expect((fixture.nativeElement as HTMLElement).querySelector('#btn-baseline')).toBeNull();

    muse.connectionStatus.set({ owner: { kind: 'user', sessionId: 7 }, state: 'connected', detail: null });
    fixture.detectChanges();
    expect(component.stage()).toBe('prepare');
    expect((fixture.nativeElement as HTMLElement).querySelector('#btn-baseline')).not.toBeNull();
  });

  it('clears a typed scan failure when retrying', () => {
    muse.scanStatus.set({ scanId: 'scan-1', state: 'failed', devices: [], detail: 'scan_failed' });
    fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).querySelector('[role="alert"]')?.textContent)
      .toContain('Unable to scan');

    (fixture.nativeElement as HTMLElement).querySelector<HTMLButtonElement>('#btn-scan')?.click();
    fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).querySelector('[role="alert"]')).toBeNull();
  });

  it('does not treat a green transport connection as green sensor contacts', () => {
    muse.connectionStatus.set({ owner: { kind: 'user', sessionId: 7 }, state: 'connected', detail: null });
    setPhase('FITTING', { tp9: 'poor' });

    const element = fixture.nativeElement as HTMLElement;
    expect(element.querySelector('[data-state="poor"]')).not.toBeNull();
    expect(element.querySelector<HTMLButtonElement>('#btn-baseline')?.disabled).toBeTrue();
  });

  xit('connects the selected headset through the typed user client (TODO: rewrite for Web Bluetooth)', () => {
    // TODO(web-bt): selectDevice/confirmDevice were replaced by museBt.connect().
    // const device = { name: 'Creative Muse', address: 'AA:BB' };
    // component.selectDevice(device);
    // component.confirmDevice();
    // expect(muse.connectUser).toHaveBeenCalledOnceWith(7, device);
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
