import { TestBed, fakeAsync, tick } from '@angular/core/testing';
import { of } from 'rxjs';

import { environment } from '../../../environments/environment';
import { AuthService } from './auth.service';
import { DatasetCollectionService, CollectionRunnerState } from './dataset-collection.service';
import { DatasetCollectionWsService } from './dataset-collection-ws.service';

class FakeWebSocket {
  static readonly OPEN = 1;
  static instances: FakeWebSocket[] = [];
  readonly url: string;
  readyState = 0;
  onopen: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  closeCalls = 0;

  constructor(url: string) {
    this.url = url;
    FakeWebSocket.instances.push(this);
  }

  open(): void {
    this.readyState = FakeWebSocket.OPEN;
    this.onopen?.(new Event('open'));
  }

  message(data: string): void {
    this.onmessage?.({ data } as MessageEvent);
  }

  unexpectedClose(): void {
    this.readyState = 3;
    this.onclose?.({ code: 1006 } as CloseEvent);
  }

  close(): void {
    this.closeCalls += 1;
    this.readyState = 3;
    this.onclose?.({ code: 1000 } as CloseEvent);
  }
}

describe('DatasetCollectionWsService', () => {
  const nativeWebSocket = globalThis.WebSocket;
  const state: CollectionRunnerState = {
    session_id: 13, state: 'in_progress', active_baseline: null,
    current_trial_id: 21, current_trial_order: 1, current_stimulus_id: 11,
    current_stimulus_title: 'Calm lake', trial_state: 'stimulus', completed_trials: 0,
    total_trials: 12, next_trial_order: null, next_trial_id: null,
    next_stimulus_id: null, next_stimulus_title: null, break_required: false,
    interruption_reason: null, accepted_clean_seconds: 12.5, wall_clock_seconds: 18,
    file_recovery_required: false,
  };
  let service: DatasetCollectionWsService;
  let runnerApi: jasmine.SpyObj<DatasetCollectionService>;

  beforeEach(() => {
    FakeWebSocket.instances = [];
    runnerApi = jasmine.createSpyObj<DatasetCollectionService>('DatasetCollectionService', ['getRunnerState']);
    runnerApi.getRunnerState.and.returnValue(of(state));
    TestBed.configureTestingModule({
      providers: [
        DatasetCollectionWsService,
        { provide: AuthService, useValue: { getToken: () => 'jwt +/=' } },
        { provide: DatasetCollectionService, useValue: runnerApi },
      ],
    });
    service = TestBed.inject(DatasetCollectionWsService);
    (globalThis as unknown as { WebSocket: typeof WebSocket }).WebSocket = FakeWebSocket as unknown as typeof WebSocket;
  });

  afterEach(() => {
    service.ngOnDestroy();
    globalThis.WebSocket = nativeWebSocket;
  });

  it('connects with an encoded JWT query and tracks the open state', () => {
    service.connect(13);
    const socket = FakeWebSocket.instances[0];
    expect(socket.url).toBe(`${environment.wsUrl}/admin/dataset-collection/ws/13?token=jwt%20%2B%2F%3D`);
    expect(service.isConnected()).toBeFalse();
    socket.open();
    expect(service.isConnected()).toBeTrue();
    expect(runnerApi.getRunnerState).not.toHaveBeenCalled();
  });

  it('accepts only valid state messages with an increasing sequence', () => {
    service.connect(13);
    const socket = FakeWebSocket.instances[0];
    socket.message(JSON.stringify({ sequence: 2, ...state }));
    expect(service.state()).toEqual(state);

    socket.message(JSON.stringify({ sequence: 2, ...state, completed_trials: 7 }));
    socket.message(JSON.stringify({ sequence: 1, ...state, completed_trials: 8 }));
    expect(service.state()?.completed_trials).toBe(0);

    socket.message(JSON.stringify({ sequence: 3, ...state, completed_trials: 1 }));
    expect(service.state()?.completed_trials).toBe(1);
  });

  it('rejects invalid JSON and schema-invalid messages', () => {
    service.connect(13);
    const socket = FakeWebSocket.instances[0];
    socket.message('{');
    socket.message(JSON.stringify({ sequence: 1, ...state, completed_trials: 'one' }));
    socket.message(JSON.stringify({ sequence: 2, ...state, invented_field: true }));
    expect(service.state()).toBeNull();
  });

  it('schedules only one reconnect after unexpected closes and refreshes persisted state after reopening', fakeAsync(() => {
    service.connect(13);
    FakeWebSocket.instances[0].unexpectedClose();
    FakeWebSocket.instances[0].unexpectedClose();
    tick(2999);
    expect(FakeWebSocket.instances.length).toBe(1);
    tick(1);
    expect(FakeWebSocket.instances.length).toBe(2);
    FakeWebSocket.instances[1].open();
    expect(runnerApi.getRunnerState).toHaveBeenCalledOnceWith(13);
    expect(service.state()).toEqual(state);
  }));

  it('starts a fresh monotonic sequence after reconnecting to a restarted backend', fakeAsync(() => {
    service.connect(13);
    FakeWebSocket.instances[0].message(JSON.stringify({ sequence: 9, ...state, completed_trials: 1 }));
    FakeWebSocket.instances[0].unexpectedClose();
    tick(3000);
    FakeWebSocket.instances[1].open();
    FakeWebSocket.instances[1].message(JSON.stringify({ sequence: 1, ...state, completed_trials: 2 }));
    expect(service.state()?.completed_trials).toBe(2);
  }));

  it('explicit disconnect cancels a pending reconnect', fakeAsync(() => {
    service.connect(13);
    FakeWebSocket.instances[0].unexpectedClose();
    service.disconnect();
    tick(3000);
    expect(FakeWebSocket.instances.length).toBe(1);
    expect(service.isConnected()).toBeFalse();
  }));

  it('destroy closes the socket and cancels reconnection', fakeAsync(() => {
    service.connect(13);
    const socket = FakeWebSocket.instances[0];
    service.ngOnDestroy();
    expect(socket.closeCalls).toBe(1);
    tick(3000);
    expect(FakeWebSocket.instances.length).toBe(1);
  }));
});
