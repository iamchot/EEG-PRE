import { Component, computed } from '@angular/core';
import { RouterOutlet, RouterLink, RouterLinkActive } from '@angular/router';
import { AuthService } from './core/services/auth.service';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
  template: `
    @if (auth.isLoggedIn()) {
      <div class="app-layout">
        <!-- Sidebar -->
        <nav class="sidebar" aria-label="เมนูหลัก">
          <!-- Brand -->
          <div class="sidebar-brand">
            <div class="brand-icon-wrap" aria-hidden="true">🧠</div>
            <div class="brand-name">Dream<br>Comicverse</div>
          </div>

          <!-- Navigation -->
          <ul class="nav-list" role="list">
            @if (auth.isAdmin()) {
              <!-- Admin: only Admin Panel -->
              <li>
                <a routerLink="/admin" routerLinkActive="active" class="nav-link" id="nav-admin">
                  <span class="nav-icon" aria-hidden="true">🛡️</span>
                  <span>Admin Panel</span>
                </a>
              </li>
            } @else {
              <!-- User: full menu -->
              <li>
                <a routerLink="/dashboard" routerLinkActive="active" class="nav-link" id="nav-dashboard">
                  <span class="nav-icon" aria-hidden="true">⊞</span>
                  <span>Dashboard</span>
                </a>
              </li>
              <li>
                <a routerLink="/persona" routerLinkActive="active" class="nav-link" id="nav-persona">
                  <span class="nav-icon" aria-hidden="true">◎</span>
                  <span>Personas</span>
                </a>
              </li>
              <li>
                <a routerLink="/eeg-session" routerLinkActive="active" class="nav-link" id="nav-create">
                  <span class="nav-icon" aria-hidden="true">✦</span>
                  <span>Create Dream</span>
                </a>
              </li>
              <li>
                <a routerLink="/history" routerLinkActive="active" class="nav-link" id="nav-history">
                  <span class="nav-icon" aria-hidden="true">◷</span>
                  <span>Timeline</span>
                </a>
              </li>
            }
          </ul>

          <!-- Spacer -->
          <div style="flex:1"></div>

          <!-- Device Status (user only) -->
          @if (!auth.isAdmin()) {
            <div class="device-status">
              <span class="device-label">CONNECTED DEVICE</span>
              <div class="device-row">
                <span class="device-dot"></span>
                <span class="device-name">Mock EEG Headset</span>
              </div>
            </div>
          }

          <!-- User Info + Logout -->
          <div class="sidebar-footer">
            <div class="user-row">
              <div class="user-avatar" aria-hidden="true">{{ userInitial() }}</div>
              <div class="user-info">
                <div class="user-name">{{ auth.currentUser()?.username }}</div>
                <div class="user-role">{{ auth.currentUser()?.role }}</div>
              </div>
              <button class="logout-btn" (click)="auth.logout()" title="ออกจากระบบ" id="btn-logout">→</button>
            </div>
          </div>
        </nav>

        <!-- Main content -->
        <main class="main-content" id="main-content">
          <router-outlet />
        </main>
      </div>
    } @else {
      <router-outlet />
    }
  `,
  styles: [`
    .app-layout {
      display: flex;
      min-height: 100vh;
      background: #080D21;
    }

    /* ─── Sidebar ─── */
    .sidebar {
      width: 200px;
      flex-shrink: 0;
      background: #0B1224;
      border-right: 1px solid rgba(51, 65, 85, 0.6);
      display: flex;
      flex-direction: column;
      padding: 20px 12px 16px;
      gap: 8px;
      position: sticky;
      top: 0;
      height: 100vh;
      overflow-y: auto;
    }

    /* Brand */
    .sidebar-brand {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 6px 8px 16px;
      border-bottom: 1px solid rgba(51, 65, 85, 0.4);
      margin-bottom: 8px;
    }
    .brand-icon-wrap {
      width: 36px; height: 36px;
      border-radius: 10px;
      background: linear-gradient(135deg, #7C3AED, #A78BFA);
      display: flex; align-items: center; justify-content: center;
      font-size: 1.25rem;
      flex-shrink: 0;
    }
    .brand-name {
      font-size: 0.9rem;
      font-weight: 700;
      line-height: 1.25;
      color: #F8FAFC;
    }

    /* Nav */
    .nav-list {
      list-style: none;
      display: flex;
      flex-direction: column;
      gap: 2px;
      padding: 0; margin: 0;
    }
    .nav-link {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 10px 12px;
      border-radius: 10px;
      color: #64748B;
      text-decoration: none;
      font-size: 0.9rem;
      font-weight: 500;
      transition: background 140ms ease, color 140ms ease;
    }
    .nav-icon { font-size: 1rem; width: 20px; text-align: center; }
    .nav-link:hover { background: rgba(30, 41, 59, 0.8); color: #CBD5E1; }
    .nav-link.active {
      background: #7C3AED;
      color: white;
      font-weight: 600;
    }
    .nav-link:focus-visible { outline: 2px solid #C4B5FD; }

    /* Device Status */
    .device-status {
      padding: 10px 12px;
      border-top: 1px solid rgba(51, 65, 85, 0.4);
      display: flex;
      flex-direction: column;
      gap: 6px;
    }
    .device-label { font-size: 0.7rem; font-weight: 700; color: #475569; letter-spacing: 0.06em; }
    .device-row { display: flex; align-items: center; gap: 6px; }
    .device-dot {
      width: 7px; height: 7px; border-radius: 50%;
      background: #22C55E;
      box-shadow: 0 0 0 3px rgba(34, 197, 94, 0.2);
      flex-shrink: 0;
    }
    .device-name { font-size: 0.8125rem; color: #94A3B8; font-weight: 500; }

    /* Footer */
    .sidebar-footer {
      padding-top: 12px;
      border-top: 1px solid rgba(51, 65, 85, 0.4);
      margin-top: 4px;
    }
    .user-row { display: flex; align-items: center; gap: 8px; }
    .user-avatar {
      width: 32px; height: 32px; border-radius: 50%;
      background: linear-gradient(135deg, #7C3AED, #A78BFA);
      display: flex; align-items: center; justify-content: center;
      font-weight: 700; font-size: 0.875rem; color: white;
      flex-shrink: 0;
    }
    .user-info { flex: 1; min-width: 0; }
    .user-name { font-weight: 600; font-size: 0.8125rem; color: #F8FAFC; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .user-role { font-size: 0.7rem; color: #64748B; }

    .logout-btn {
      width: 28px; height: 28px; border-radius: 8px;
      background: rgba(30, 41, 59, 0.8);
      border: 1px solid #334155;
      color: #94A3B8;
      cursor: pointer;
      display: flex; align-items: center; justify-content: center;
      font-size: 0.9rem;
      transition: background 150ms, color 150ms;
      flex-shrink: 0;
    }
    .logout-btn:hover { background: rgba(239, 68, 68, 0.15); color: #EF4444; border-color: #EF4444; }

    /* Main */
    .main-content { flex: 1; overflow: auto; background: #080D21; }

    @media (max-width: 768px) {
      .sidebar { display: none; }
      .main-content { width: 100%; }
    }
  `],
})
export class AppComponent {
  constructor(readonly auth: AuthService) {}
  userInitial = computed(() => (this.auth.currentUser()?.username?.[0] ?? 'U').toUpperCase());
}
