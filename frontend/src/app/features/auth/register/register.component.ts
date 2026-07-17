import { Component, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { AuthService } from '../../../core/services/auth.service';

@Component({
  selector: 'app-register',
  standalone: true,
  imports: [FormsModule, RouterLink],
  template: `
    <div class="auth-page">
      <div class="auth-bg" aria-hidden="true">
        <div class="bg-orb bg-orb-1"></div>
        <div class="bg-orb bg-orb-2"></div>
      </div>

      <div class="auth-card card animate-fade-in">
        <div class="auth-header">
          <div class="auth-logo" aria-hidden="true">🧠</div>
          <h1>สร้างบัญชีใหม่</h1>
          <p>เริ่มสร้างการ์ตูนจากคลื่นสมองของคุณ</p>
        </div>

        <form (ngSubmit)="onSubmit()" novalidate>
          <div class="form-group">
            <label class="form-label" for="reg-username">ชื่อผู้ใช้</label>
            <input id="reg-username" type="text" class="form-input" [(ngModel)]="username" name="username"
                   placeholder="ชื่อผู้ใช้ (อย่างน้อย 3 ตัวอักษร)" required autocomplete="username"/>
          </div>

          <div class="form-group">
            <label class="form-label" for="reg-email">อีเมล</label>
            <input id="reg-email" type="email" class="form-input" [(ngModel)]="email" name="email"
                   placeholder="your@email.com" required autocomplete="email"/>
          </div>

          <div class="form-group">
            <label class="form-label" for="reg-password">รหัสผ่าน</label>
            <input id="reg-password" type="password" class="form-input" [(ngModel)]="password" name="password"
                   placeholder="อย่างน้อย 8 ตัวอักษร" required autocomplete="new-password"/>
          </div>

          @if (error()) {
            <div class="alert alert-error" role="alert" aria-live="polite">
              <span aria-hidden="true">⚠️</span> {{ error() }}
            </div>
          }

          @if (success()) {
            <div class="alert alert-success" role="alert">
              <span aria-hidden="true">✓</span> สมัครสมาชิกสำเร็จ! กำลังพาไปหน้าเข้าสู่ระบบ...
            </div>
          }

          <button type="submit" class="btn btn-primary" id="btn-register" style="width:100%" [disabled]="loading()">
            @if (loading()) {
              <span class="spinner" aria-hidden="true"></span> กำลังสมัคร...
            } @else {
              สมัครสมาชิก
            }
          </button>
        </form>

        <div class="auth-footer">
          <p>มีบัญชีแล้ว? <a routerLink="/login" id="link-login">เข้าสู่ระบบ</a></p>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .auth-page { min-height:100vh; display:flex; align-items:center; justify-content:center; padding:24px; position:relative; overflow:hidden; }
    .auth-bg { position:fixed; inset:0; pointer-events:none; }
    .bg-orb { position:absolute; border-radius:50%; filter:blur(80px); opacity:.15; }
    .bg-orb-1 { width:400px; height:400px; background:var(--color-primary); top:-100px; right:-100px; }
    .bg-orb-2 { width:300px; height:300px; background:var(--color-secondary); bottom:-50px; left:-50px; }
    .auth-card { width:100%; max-width:440px; position:relative; z-index:1; display:flex; flex-direction:column; gap:24px; background:rgba(21,29,53,.9); backdrop-filter:blur(16px); }
    .auth-header { text-align:center; }
    .auth-logo { font-size:3rem; margin-bottom:12px; display:block; }
    .auth-header h1 { font-size:1.75rem; margin-bottom:8px; }
    .auth-header p  { color:var(--color-text-muted); }
    form { display:flex; flex-direction:column; gap:16px; }
    .auth-footer { text-align:center; }
    .auth-footer p { color:var(--color-text-muted); }
    .auth-footer a { color:var(--color-secondary); text-decoration:none; font-weight:600; }
  `],
})
export class RegisterComponent {
  username = '';
  email = '';
  password = '';
  loading = signal(false);
  error = signal('');
  success = signal(false);

  constructor(private authService: AuthService, private router: Router) {}

  onSubmit() {
    if (!this.username || !this.email || !this.password) return;
    this.loading.set(true);
    this.error.set('');
    this.authService.register({ username: this.username, email: this.email, password: this.password }).subscribe({
      next: () => {
        this.success.set(true);
        setTimeout(() => this.router.navigate(['/login']), 1500);
      },
      error: (err: { error?: { detail?: string } }) => {
        this.error.set(err?.error?.detail ?? 'สมัครสมาชิกไม่สำเร็จ');
        this.loading.set(false);
      },
    });
  }
}
