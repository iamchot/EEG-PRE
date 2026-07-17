import { Component, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { AuthService } from '../../../core/services/auth.service';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [FormsModule, RouterLink],
  template: `
    <div class="auth-page">
      <div class="auth-bg" aria-hidden="true">
        <div class="bg-orb bg-orb-1"></div><div class="bg-orb bg-orb-2"></div>
      </div>
      <div class="auth-card animate-fade-in">
        <div class="auth-header">
          <div class="auth-logo-wrap" aria-hidden="true"><span class="auth-logo">🧠</span></div>
          <h1>Dream Comicverse</h1><p>Login to explore your subconscious</p>
        </div>
        <form (ngSubmit)="onSubmit()" novalidate>
          <div class="form-group">
            <label class="form-label" for="login-email">Email Address</label>
            <div class="input-wrap"><span class="input-icon" aria-hidden="true">👤</span>
              <input id="login-email" type="email" class="form-input" [(ngModel)]="email" name="email"
                placeholder="you@example.com" required autocomplete="email" />
            </div>
          </div>
          <div class="form-group">
            <label class="form-label" for="login-password">Password</label>
            <div class="input-wrap"><span class="input-icon" aria-hidden="true">🔒</span>
              <input id="login-password" type="password" class="form-input" [(ngModel)]="password" name="password"
                placeholder="••••••••" required autocomplete="current-password" />
            </div>
          </div>
          @if (error()) {
            <div class="alert-error" role="alert" aria-live="polite"><span aria-hidden="true">⚠️</span><span>{{ error() }}</span></div>
          }
          <button type="submit" class="btn btn-login" [disabled]="loading()">
            @if (loading()) { <span class="spinner" aria-hidden="true"></span> }
            <span>{{ loading() ? 'กำลังเข้าสู่ระบบ...' : 'เข้าสู่ระบบ' }}</span>
          </button>
        </form>
        <div class="auth-footer"><p>ยังไม่มีบัญชี? <a routerLink="/register" id="link-register">สมัครสมาชิก</a></p></div>
      </div>
    </div>
  `,
  styleUrl: './login.component.css',
})
export class LoginComponent {
  email = '';
  password = '';
  loading = signal(false);
  error = signal('');

  constructor(private authService: AuthService, private router: Router) {}

  onSubmit(): void {
    if (!this.email || !this.password || this.loading()) return;
    this.loading.set(true);
    this.error.set('');
    this.authService.login({ email: this.email, password: this.password }).subscribe({
      next: (response) => {
        if (response.role === 'user') {
          this.router.navigate(['/dashboard']);
        } else if (response.role === 'admin') {
          this.router.navigate(['/admin']);
        } else {
          this.authService.clearSession();
          this.error.set('บัญชีนี้ไม่มีสิทธิ์เข้าใช้งานระบบ');
          this.loading.set(false);
        }
      },
      error: (err: { error?: { detail?: string } }) => {
        this.error.set(err?.error?.detail ?? 'เข้าสู่ระบบไม่สำเร็จ กรุณาตรวจสอบอีเมลและรหัสผ่าน');
        this.loading.set(false);
      },
    });
  }
}
