import { Component, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { AuthService } from '../../../core/services/auth.service';
import { toThaiError } from '../../../core/services/language.service';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [FormsModule, RouterLink],
  templateUrl: './login.component.html',
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
      error: (err: unknown) => {
        this.error.set(toThaiError(err) || 'เข้าสู่ระบบไม่สำเร็จ กรุณาตรวจสอบอีเมลและรหัสผ่าน');
        this.loading.set(false);
      },
    });
  }
}
