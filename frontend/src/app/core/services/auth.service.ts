import { Injectable, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { environment } from '../../../environments/environment';
import { tap } from 'rxjs/operators';

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  username: string;
  email: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  role: string;
}

export interface UserPublic {
  id: number;
  username: string;
  email: string;
  role: string;
}

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly apiUrl = environment.apiUrl;
  readonly currentUser = signal<UserPublic | null>(null);

  constructor(private http: HttpClient, private router: Router) {
    this._loadStoredUser();
  }

  login(body: LoginRequest) {
    return this.http.post<TokenResponse>(`${this.apiUrl}/auth/login`, body).pipe(
      tap((res) => {
        localStorage.setItem('access_token', res.access_token);
        localStorage.setItem('refresh_token', res.refresh_token);
        this._fetchMe();
      })
    );
  }

  register(body: RegisterRequest) {
    return this.http.post<UserPublic>(`${this.apiUrl}/auth/register`, body);
  }

  logout() {
    this.clearSession();
    this.router.navigate(['/login']);
  }

  clearSession(): void {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    this.currentUser.set(null);
  }

  getToken(): string | null {
    return localStorage.getItem('access_token');
  }

  isLoggedIn(): boolean {
    return !!this.getToken();
  }

  isAdmin(): boolean {
    return this.currentUser()?.role === 'admin';
  }

  private _fetchMe() {
    this.http.get<UserPublic>(`${this.apiUrl}/auth/me`).subscribe({
      next: (user) => this.currentUser.set(user),
      error: () => this.logout(),
    });
  }

  private _loadStoredUser() {
    if (this.getToken()) {
      this._fetchMe();
    }
  }
}
