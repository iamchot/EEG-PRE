import { ComponentFixture, TestBed } from '@angular/core/testing';
import { signal } from '@angular/core';
import { provideRouter } from '@angular/router';

import { AppComponent } from './app.component';
import { AuthService } from './core/services/auth.service';
import { MuseDeviceService } from './core/services/muse-device.service';
import { MuseWebBluetoothService, MuseWebBtState } from './core/services/muse-web-bluetooth.service';

describe('AppComponent Muse status', () => {
  let fixture: ComponentFixture<AppComponent>;
  let muse: {
    connectionStatus: ReturnType<typeof signal>;
    connectedDevice: ReturnType<typeof signal>;
  };
  let museWebBt: {
    state: ReturnType<typeof signal<MuseWebBtState>>;
    deviceName: ReturnType<typeof signal<string | null>>;
    disconnect: jasmine.Spy;
  };

  beforeEach(async () => {
    muse = {
      connectionStatus: signal({ owner: null, state: 'idle', detail: null }),
      connectedDevice: signal(null),
    };
    museWebBt = {
      state: signal<MuseWebBtState>('idle'),
      deviceName: signal<string | null>(null),
      disconnect: jasmine.createSpy('disconnect').and.resolveTo(),
    };
    await TestBed.configureTestingModule({
      imports: [AppComponent],
      providers: [
        provideRouter([]),
        {
          provide: AuthService,
          useValue: {
            isLoggedIn: () => true,
            isAdmin: () => false,
            currentUser: signal({ id: 7, username: 'Mira', email: 'mira@example.test', role: 'user' }),
            logout: jasmine.createSpy('logout'),
          },
        },
        { provide: MuseDeviceService, useValue: muse },
        { provide: MuseWebBluetoothService, useValue: museWebBt },
      ],
    }).compileComponents();
    fixture = TestBed.createComponent(AppComponent);
  });

  it('renders a neutral no-Muse status instead of a mock headset', () => {
    fixture.detectChanges();

    const status = fixture.nativeElement.querySelector('[data-testid="muse-status"]') as HTMLElement;
    expect(status.textContent).toContain('No Muse connected');
    expect(status.textContent).not.toContain('Mock EEG');
    expect(status.classList).not.toContain('connected');
  });

  it('shows only the actual connected device name and keeps failed status non-green', () => {
    muse.connectionStatus.set({ owner: { kind: 'user', sessionId: 7 }, state: 'connected', detail: null });
    muse.connectedDevice.set({ address: 'AA:BB:CC:DD', name: 'Studio Muse' });
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('[data-testid="muse-status"]').textContent).toContain('Studio Muse');

    muse.connectionStatus.set({ owner: { kind: 'user', sessionId: 7 }, state: 'failed', detail: 'bridge_failed' });
    fixture.detectChanges();
    const failed = fixture.nativeElement.querySelector('[data-testid="muse-status"]') as HTMLElement;
    expect(failed.textContent).toContain('Muse connection unavailable');
    expect(failed.classList).not.toContain('connected');
  });

  it('shows the current Muse stage while the connection is busy', () => {
    muse.connectionStatus.set({ owner: { kind: 'user', sessionId: 7 }, state: 'waiting_for_lsl', detail: null });
    fixture.detectChanges();

    const status = fixture.nativeElement.querySelector('[data-testid="muse-status"]') as HTMLElement;
    expect(status.textContent).toContain('Waiting for LSL');
    expect(status.classList).toContain('busy');
  });

  it('shows Web Bluetooth connected device and status tone', () => {
    museWebBt.state.set('streaming');
    museWebBt.deviceName.set('Muse-2-Live');
    fixture.detectChanges();

    const status = fixture.nativeElement.querySelector('[data-testid="muse-status"]') as HTMLElement;
    expect(status.textContent).toContain('Muse-2-Live');
    expect(status.classList).toContain('connected');
  });

  it('shows Web Bluetooth busy state while connecting', () => {
    museWebBt.state.set('connecting');
    fixture.detectChanges();

    const status = fixture.nativeElement.querySelector('[data-testid="muse-status"]') as HTMLElement;
    expect(status.textContent).toContain('Connecting Muse 2…');
    expect(status.classList).toContain('busy');
  });
});

