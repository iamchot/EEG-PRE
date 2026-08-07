import { HttpErrorResponse, HttpClient } from '@angular/common/http';
import { Injectable, signal } from '@angular/core';
import { EMPTY, finalize, tap } from 'rxjs';
import { catchError } from 'rxjs/operators';
import { environment } from '../../../environments/environment';

export type SystemHealthState = 'unknown' | 'checking' | 'available' | 'degraded' | 'unavailable';

export interface ServiceHealth {
  state: SystemHealthState;
  detail: string;
  checked_at: string;
  latency_ms: number | null;
}

export interface SystemHealth {
  api: ServiceHealth;
  comfyui: ServiceHealth;
  gemini: ServiceHealth;
  muse: ServiceHealth;
}

@Injectable({ providedIn: 'root' })
export class SystemHealthService {
  readonly loading = signal(false);
  readonly health = signal<SystemHealth | null>(null);
  readonly error = signal<HttpErrorResponse | null>(null);

  constructor(private readonly http: HttpClient) {}

  refresh(): void {
    this.loading.set(true);
    this.health.set(null);
    this.error.set(null);

    this.http.get<SystemHealth>(`${environment.apiUrl}/system/health`).pipe(
      tap((health) => this.health.set(health)),
      catchError((error: HttpErrorResponse) => {
        this.health.set(null);
        this.error.set(error);
        return EMPTY;
      }),
      finalize(() => this.loading.set(false)),
    ).subscribe();
  }
}
