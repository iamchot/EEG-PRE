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
    expect(element.querySelectorAll('button[type="submit"]').length).toBe(1);
    expect(element.textContent).not.toContain('Login as User');
    expect(element.textContent).not.toContain('Login as Admin');
  });

  for (const [role, destination] of [['user', '/dashboard'], ['admin', '/admin']] as const) {
    it(`routes a ${role} response to ${destination}`, () => {
      submitWith(role);
      expect(router.navigate).toHaveBeenCalledOnceWith([destination]);
    });
  }

  it('clears an unsupported session, avoids protected navigation, and shows the access error', () => {
    submitWith('guest');
    fixture.detectChanges();
    expect(auth.clearSession).toHaveBeenCalled();
    expect(router.navigate).not.toHaveBeenCalled();
    expect(component.error()).toBe('à¸šà¸±à¸à¸Šà¸µà¸™à¸µà¹‰à¹„à¸¡à¹ˆà¸¡à¸µà¸ªà¸´à¸—à¸˜à¸´à¹Œà¹€à¸‚à¹‰à¸²à¹ƒà¸Šà¹‰à¸‡à¸²à¸™à¸£à¸°à¸šà¸š');
    expect(fixture.nativeElement.textContent).toContain(component.error());
    expect(component.loading()).toBeFalse();
  });

  function submitWith(role: string): void {
    const response: TokenResponse = {
      access_token: 'access', refresh_token: 'refresh', token_type: 'bearer', role,
    };
    auth.login.and.returnValue(of(response));
    component.email = 'person@example.com';
    component.password = 'secret';
    component.onSubmit();
  }
});
