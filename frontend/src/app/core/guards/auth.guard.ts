import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthService, UserPublic } from '../services/auth.service';
import { map, catchError, of } from 'rxjs';
import { HttpClient } from '@angular/common/http';
import { environment } from '../../../environments/environment';

export const authGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  const router = inject(Router);
  if (auth.isLoggedIn()) return true;
  return router.createUrlTree(['/login']);
};

/**
 * adminGuard — waits for /auth/me on page reload before deciding access.
 * Handles the race condition where currentUser signal is null right after reload.
 */
type GuardAudience = 'user' | 'admin' | 'guest';

function roleGuard(audience: GuardAudience): ReturnType<CanActivateFn> {
  const auth = inject(AuthService);
  const http = inject(HttpClient);
  const router = inject(Router);

  if (!auth.getToken()) {
    return audience === 'guest' ? true : router.createUrlTree(['/login']);
  }

  const decide = (user: UserPublic) => {
    if (user.role !== 'user' && user.role !== 'admin') {
      auth.clearSession();
      return audience === 'guest' ? true : router.createUrlTree(['/login']);
    }

    if (audience === 'guest') {
      return router.createUrlTree([user.role === 'admin' ? '/admin' : '/dashboard']);
    }
    if (audience === user.role) return true;
    return router.createUrlTree([user.role === 'admin' ? '/admin' : '/dashboard']);
  };

  // Already fetched (SPA navigation, not reload)
  const user = auth.currentUser();
  if (user) return decide(user);

  // Page reload — currentUser not yet set, fetch it first
  return http.get<UserPublic>(`${environment.apiUrl}/auth/me`).pipe(
    map((u) => {
      auth.currentUser.set(u);
      return decide(u);
    }),
    catchError((err) => {
      if (err?.status === 401 || err?.status === 403) {
        auth.clearSession();
      }
      return of(audience === 'guest' ? true : router.createUrlTree(['/login']));
    }),
  );
}

export const userGuard: CanActivateFn = () => roleGuard('user');

export const adminGuard: CanActivateFn = () => roleGuard('admin');

export const guestGuard: CanActivateFn = () => {
  return roleGuard('guest');
};
