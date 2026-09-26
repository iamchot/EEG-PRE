import { ApplicationConfig, provideZoneChangeDetection, APP_INITIALIZER } from '@angular/core';
import { provideRouter } from '@angular/router';
import { provideHttpClient, withInterceptors, HttpClient } from '@angular/common/http';
import { routes } from './app.routes';
import { jwtInterceptor } from './core/interceptors/jwt.interceptor';
import { AuthService } from './core/services/auth.service';
import { firstValueFrom, catchError, of } from 'rxjs';
import { environment } from '../environments/environment';
import { UserPublic } from './core/services/auth.service';

/**
 * APP_INITIALIZER — runs before any route guard.
 * If a JWT token exists, fetches /auth/me so currentUser signal is populated
 * before the router evaluates guards (prevents admin redirect on page reload).
 */
function initAuth(auth: AuthService, http: HttpClient) {
  return () => {
    if (!auth.getToken()) return Promise.resolve();
    return firstValueFrom(
      http.get<UserPublic>(`${environment.apiUrl}/auth/me`).pipe(
        catchError((err) => {
          if (err?.status === 401 || err?.status === 403) {
            auth.logout();
          }
          return of(null);
        }),
      ),
    ).then((user) => {
      if (user) auth.currentUser.set(user);
    });
  };
}

export const appConfig: ApplicationConfig = {
  providers: [
    provideZoneChangeDetection({ eventCoalescing: true }),
    provideRouter(routes),
    provideHttpClient(withInterceptors([jwtInterceptor])),
    {
      provide: APP_INITIALIZER,
      useFactory: (auth: AuthService, http: HttpClient) => initAuth(auth, http),
      deps: [AuthService, HttpClient],
      multi: true,
    },
  ],
};
