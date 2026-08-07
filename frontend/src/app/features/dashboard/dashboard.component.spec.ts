import { HttpErrorResponse } from '@angular/common/http';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of } from 'rxjs';
import { signal } from '@angular/core';
import { AuthService } from '../../core/services/auth.service';
import { ComicService } from '../../core/services/comic.service';
import { PersonaService } from '../../core/services/persona.service';
import { SystemHealth, SystemHealthService } from '../../core/services/system-health.service';
import { DashboardComponent } from './dashboard.component';

const health: SystemHealth = {
  api: { state: 'available', detail: 'API is responding', checked_at: '2026-07-29T10:15:30.123Z', latency_ms: 12 },
  comfyui: { state: 'degraded', detail: 'Queue is slow', checked_at: '2026-07-29T10:15:31.456Z', latency_ms: 820 },
  gemini: { state: 'unavailable', detail: 'Credential rejected', checked_at: '2026-07-29T10:15:32.789Z', latency_ms: null },
  muse: { state: 'checking', detail: 'Waiting for a session', checked_at: '2026-07-29T10:15:33.000Z', latency_ms: null },
};

describe('DashboardComponent system health', () => {
  let fixture: ComponentFixture<DashboardComponent>;
  const healthState = signal<SystemHealth | null>(null);
  const loading = signal(false);
  const error = signal<HttpErrorResponse | null>(null);
  const healthService = { health: healthState, loading, error, refresh: jasmine.createSpy('refresh') };

  beforeEach(async () => {
    healthState.set(null);
    loading.set(false);
    error.set(null);
    healthService.refresh.calls.reset();

    await TestBed.configureTestingModule({
      imports: [DashboardComponent],
      providers: [
        provideRouter([]),
        { provide: AuthService, useValue: {} },
        { provide: PersonaService, useValue: { getAll: () => of([]) } },
        { provide: ComicService, useValue: { getAll: () => of([]) } },
        { provide: SystemHealthService, useValue: healthService },
      ],
    }).compileComponents();
    fixture = TestBed.createComponent(DashboardComponent);
  });

  it('renders the exact backend health state, detail, and timestamp with semantic dot classes', () => {
    healthState.set(health);

    fixture.detectChanges();

    const api = fixture.nativeElement.querySelector('[data-health-service="API"]');
    const comfyui = fixture.nativeElement.querySelector('[data-health-service="ComfyUI"]');
    const gemini = fixture.nativeElement.querySelector('[data-health-service="Gemini"]');
    const muse = fixture.nativeElement.querySelector('[data-health-service="Muse"]');
    expect(api.textContent).toContain('API is responding');
    expect(api.textContent).toContain('2026-07-29T10:15:30.123Z');
    expect(api.querySelector('.dot.available')).not.toBeNull();
    expect(comfyui.textContent).toContain('Queue is slow');
    expect(comfyui.querySelector('.dot.degraded')).not.toBeNull();
    expect(gemini.textContent).toContain('Credential rejected');
    expect(gemini.querySelector('.dot.unavailable')).not.toBeNull();
    expect(muse.textContent).toContain('Waiting for a session');
    expect(muse.querySelector('.dot.checking')).not.toBeNull();
    expect(healthService.refresh).toHaveBeenCalledTimes(1);
  });

  it('keeps all system cards unknown before checking and unavailable after a failed health request', () => {
    fixture.detectChanges();
    let cards = [...fixture.nativeElement.querySelectorAll('[data-health-service]')];
    expect(cards).toHaveSize(4);
    expect(cards.every((card: Element) => card.querySelector('.dot.unknown') !== null)).toBeTrue();

    loading.set(true);
    fixture.detectChanges();
    cards = [...fixture.nativeElement.querySelectorAll('[data-health-service]')];
    expect(cards.every((card: Element) => card.querySelector('.dot.checking') !== null)).toBeTrue();

    loading.set(false);
    error.set(new HttpErrorResponse({ status: 503, statusText: 'Service Unavailable' }));
    fixture.detectChanges();

    cards = [...fixture.nativeElement.querySelectorAll('[data-health-service]')];
    expect(cards).toHaveSize(4);
    expect(cards.every((card: Element) => card.querySelector('.dot.unavailable') !== null)).toBeTrue();
    expect(fixture.nativeElement.textContent).not.toContain('Ready for comic panels');
    expect(fixture.nativeElement.textContent).not.toContain('Prompt pipeline enabled');
  });
});
