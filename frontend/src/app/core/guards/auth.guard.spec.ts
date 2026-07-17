import { TestBed } from '@angular/core/testing';
import { HttpClient } from '@angular/common/http';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { Router } from '@angular/router';
import { firstValueFrom, isObservable } from 'rxjs';
import { signal } from '@angular/core';

import { environment } from '../../../environments/environment';
import { AuthService, UserPublic } from '../services/auth.service';
import { adminGuard, guestGuard, userGuard } from './auth.guard';

describe('role-aware guards', () => {
  const user: UserPublic = { id: 1, username: 'user', email: 'u@test.dev', role: 'user' };
  const admin: UserPublic = { id: 2, username: 'admin', email: 'a@test.dev', role: 'admin' };
  let auth: {
    currentUser: ReturnType<typeof signal<UserPublic | null>>;
    getToken: jasmine.Spy;
    clearSession: jasmine.Spy;
  };
  let http: HttpTestingController;

  beforeEach(() => {
    auth = {
      currentUser: signal<UserPublic | null>(null),
      getToken: jasmine.createSpy('getToken').and.returnValue('token'),
      clearSession: jasmine.createSpy('clearSession'),
    };
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: AuthService, useValue: auth },
        { provide: Router, useValue: { createUrlTree: (commands: string[]) => commands.join('') } },
      ],
    });
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  function run(guard: typeof userGuard): unknown {
    return TestBed.runInInjectionContext(() => guard({} as never, {} as never)) as unknown;
  }

  async function resolve(result: unknown): Promise<unknown> {
    return isObservable(result) ? firstValueFrom(result) : result;
  }

  it('routes loaded users only to user pages', () => {
    auth.currentUser.set(user);
    expect(run(userGuard)).toBeTrue();
    expect(run(adminGuard)).toBe('/dashboard');
    expect(run(guestGuard)).toBe('/dashboard');
  });

  it('routes loaded admins only to admin pages', () => {
    auth.currentUser.set(admin);
    expect(run(adminGuard)).toBeTrue();
    expect(run(userGuard)).toBe('/admin');
    expect(run(guestGuard)).toBe('/admin');
  });

  for (const [name, guard, fetched, expected] of [
    ['user guard', userGuard, user, true],
    ['admin guard', adminGuard, admin, true],
    ['guest guard', guestGuard, admin, '/admin'],
  ] as const) {
    it(`${name} fetches /auth/me before deciding after refresh`, async () => {
      const pending = resolve(run(guard));
      http.expectOne(`${environment.apiUrl}/auth/me`).flush(fetched);
      expect(await pending).toBe(expected);
      expect(auth.currentUser()).toEqual(fetched);
    });
  }

  it('handles missing tokens for protected and guest routes', () => {
    auth.getToken.and.returnValue(null);
    expect(run(userGuard)).toBe('/login');
    expect(run(adminGuard)).toBe('/login');
    expect(run(guestGuard)).toBeTrue();
  });

  for (const role of [undefined, 'editor']) {
    it(`clears a loaded ${role ?? 'missing'} role and applies safe redirects`, () => {
      auth.currentUser.set({ ...user, role: role as string });
      expect(run(userGuard)).toBe('/login');
      expect(run(adminGuard)).toBe('/login');
      expect(run(guestGuard)).toBeTrue();
      expect(auth.clearSession).toHaveBeenCalledTimes(3);
    });
  }

  for (const [name, guard, expected] of [
    ['user guard', userGuard, '/login'],
    ['admin guard', adminGuard, '/login'],
    ['guest guard', guestGuard, true],
  ] as const) {
    it(`${name} clears the session when /auth/me fails`, async () => {
      const pending = resolve(run(guard));
      http.expectOne(`${environment.apiUrl}/auth/me`).flush('nope', { status: 401, statusText: 'Unauthorized' });
      expect(await pending).toBe(expected);
      expect(auth.clearSession).toHaveBeenCalled();
    });
  }
});
