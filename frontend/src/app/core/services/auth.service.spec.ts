import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideRouter } from '@angular/router';
import { Router } from '@angular/router';
import { AuthService, TokenResponse } from './auth.service';
import { environment } from '../../../environments/environment';

describe('AuthService', () => {
  let service: AuthService;
  let http: HttpTestingController;

  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    });
    service = TestBed.inject(AuthService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    http.verify();
    localStorage.clear();
  });

  it('posts exactly the credentials, emits the complete response, stores tokens, and refreshes the user', () => {
    const response: TokenResponse = {
      access_token: 'access', refresh_token: 'refresh', token_type: 'bearer', role: 'admin',
    };
    let received: TokenResponse | undefined;

    service.login({ email: 'person@example.com', password: 'secret' }).subscribe(value => received = value);

    const login = http.expectOne(`${environment.apiUrl}/auth/login`);
    expect(login.request.method).toBe('POST');
    expect(login.request.body).toEqual({ email: 'person@example.com', password: 'secret' });
    login.flush(response);

    expect(received).toEqual(response);
    expect(localStorage.getItem('access_token')).toBe('access');
    expect(localStorage.getItem('refresh_token')).toBe('refresh');
    const me = http.expectOne(`${environment.apiUrl}/auth/me`);
    expect(me.request.method).toBe('GET');
    me.flush({ id: 1, username: 'person', email: 'person@example.com', role: 'admin' });
  });

  it('clearSession removes both tokens and clears the current user', () => {
    localStorage.setItem('access_token', 'access');
    localStorage.setItem('refresh_token', 'refresh');
    service.currentUser.set({ id: 1, username: 'person', email: 'person@example.com', role: 'user' });

    service.clearSession();

    expect(localStorage.getItem('access_token')).toBeNull();
    expect(localStorage.getItem('refresh_token')).toBeNull();
    expect(service.currentUser()).toBeNull();
  });

  it('logout clears the session before navigating to login', () => {
    const router = TestBed.inject(Router);
    const calls: string[] = [];
    const clearSession = spyOn(service, 'clearSession').and.callFake(() => calls.push('clear'));
    const navigate = spyOn(router, 'navigate').and.callFake(() => {
      calls.push('navigate');
      return Promise.resolve(true);
    });

    service.logout();

    expect(clearSession).toHaveBeenCalledTimes(1);
    expect(navigate).toHaveBeenCalledOnceWith(['/login']);
    expect(calls).toEqual(['clear', 'navigate']);
  });
});
