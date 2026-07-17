import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Router } from '@angular/router';
import { of } from 'rxjs';
import { AuthService, TokenResponse } from '../../../core/services/auth.service';
import { LoginComponent } from './login.component';

describe('LoginComponent', () => {
  let fixture: ComponentFixture<LoginComponent>;
  let component: LoginComponent;
  let auth: jasmine.SpyObj<AuthService>;
  let router: jasmine.SpyObj<Router>;

  beforeEach(async () => {
    auth = jasmine.createSpyObj<AuthService>('AuthService', ['login', 'clearSession']);
    router = jasmine.createSpyObj<Router>('Router', ['navigate']);
    await TestBed.configureTestingModule({
      imports: [LoginComponent],
      providers: [
        { provide: AuthService, useValue: auth },
        { provide: Router, useValue: router },
      ],
    }).compileComponents();
    fixture = TestBed.createComponent(LoginComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('renders exactly one submit button without role-specific login text', () => {
    const element: HTMLElement = fixture.nativeElement;
    const buttons = element.querySelectorAll<HTMLButtonElement>('button[type="submit"]');
    expect(buttons.length).toBe(1);
    expect(buttons[0].textContent?.trim()).toBe('เข้าสู่ระบบ');
    expect(element.textContent).not.toContain('Login as User');
    expect(element.textContent).not.toContain('Login as Admin');
  });

  for (const [role, destination] of [['user', '/dashboard'], ['admin', '/admin']] as const) {
    it(`routes a ${role} response to ${destination}`, () => {
      submitWith(role);
      expect(router.navigate).toHaveBeenCalledOnceWith([destination]);
    });
  }

  for (const role of ['guest', undefined]) {
    it(`clears a ${role ?? 'missing'} role session, avoids protected navigation, and shows the access error`, () => {
      submitWith(role);
      fixture.detectChanges();
      expect(auth.clearSession).toHaveBeenCalled();
      expect(router.navigate).not.toHaveBeenCalled();
      expect(component.error()).toBe('บัญชีนี้ไม่มีสิทธิ์เข้าใช้งานระบบ');
      expect(fixture.nativeElement.textContent).toContain('บัญชีนี้ไม่มีสิทธิ์เข้าใช้งานระบบ');
      expect(component.loading()).toBeFalse();
    });
  }

  it('does nothing with empty credentials', () => {
    component.onSubmit();
    expect(auth.login).not.toHaveBeenCalled();
    expect(router.navigate).not.toHaveBeenCalled();
  });

  it('does nothing while already loading', () => {
    component.email = 'person@example.com';
    component.password = 'secret';
    component.loading.set(true);
    component.onSubmit();
    expect(auth.login).not.toHaveBeenCalled();
    expect(router.navigate).not.toHaveBeenCalled();
  });

  function submitWith(role: string | undefined): void {
    const response = {
      access_token: 'access', refresh_token: 'refresh', token_type: 'bearer', role,
    } as TokenResponse;
    auth.login.and.returnValue(of(response));
    component.email = 'person@example.com';
    component.password = 'secret';
    component.onSubmit();
  }
});
