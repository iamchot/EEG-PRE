import { Component, computed } from '@angular/core';
import { RouterOutlet, RouterLink, RouterLinkActive } from '@angular/router';

import { AuthService } from './core/services/auth.service';
import { MuseDeviceService } from './core/services/muse-device.service';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
  template: `
    @if (auth.isLoggedIn()) {
      <div class="app-layout">
        <nav class="sidebar" aria-label="Main menu">
          <div class="sidebar-brand">
            <div class="brand-icon-wrap" aria-hidden="true">🧠</div>
            <div class="brand-name">Dream<br>Comicverse</div>
          </div>

          <ul class="nav-list" role="list">
            @if (auth.isAdmin()) {
              <li><a routerLink="/admin" routerLinkActive="active" class="nav-link" id="nav-admin"><span class="nav-icon" aria-hidden="true">🛡️</span><span>Admin Panel</span></a></li>
            } @else {
              <li><a routerLink="/dashboard" routerLinkActive="active" class="nav-link" id="nav-dashboard"><span class="nav-icon" aria-hidden="true">⊞</span><span>Dashboard</span></a></li>
              <li><a routerLink="/persona" routerLinkActive="active" class="nav-link" id="nav-persona"><span class="nav-icon" aria-hidden="true">◎</span><span>Personas</span></a></li>
              <li><a routerLink="/eeg-session" routerLinkActive="active" class="nav-link" id="nav-create"><span class="nav-icon" aria-hidden="true">✦</span><span>Create Dream</span></a></li>
              <li><a routerLink="/history" routerLinkActive="active" class="nav-link" id="nav-history"><span class="nav-icon" aria-hidden="true">◷</span><span>Timeline</span></a></li>
            }
          </ul>

          <div class="sidebar-spacer"></div>

          <div class="device-status" data-testid="muse-status" [class.connected]="museStatusTone() === 'connected'" [class.busy]="museStatusTone() === 'busy'" [class.failed]="museStatusTone() === 'failed'">
            <span class="device-label">MUSE STATUS</span>
            <div class="device-row"><span class="device-dot"></span><span class="device-name">{{ museStatusLabel() }}</span></div>
          </div>

          <div class="sidebar-footer">
            <div class="user-row">
              <div class="user-avatar" aria-hidden="true">{{ userInitial() }}</div>
              <div class="user-info"><div class="user-name">{{ auth.currentUser()?.username }}</div><div class="user-role">{{ auth.currentUser()?.role }}</div></div>
              <button class="logout-btn" (click)="logout()" title="ออกจากระบบ" id="btn-logout">→</button>
            </div>
          </div>
        </nav>
        <main class="main-content" id="main-content"><router-outlet /></main>
      </div>
    } @else {
      <router-outlet />
    }
  `,
  styleUrl: './app.component.css',
})
export class AppComponent {
  constructor(readonly auth: AuthService, readonly muse: MuseDeviceService) {}

  userInitial = computed(() => (this.auth.currentUser()?.username?.[0] ?? 'U').toUpperCase());

  logout(): void {
    this.muse.resetState();
    this.auth.logout();
  }

  museStatusLabel(): string {
    const connection = this.muse.connectionStatus();
    const device = this.muse.connectedDevice();
    const expectedKind = this.auth.isAdmin() ? 'collection' : 'user';
    if (!connection.owner || connection.owner.kind !== expectedKind) {
      return 'No Muse connected';
    }
    if (connection.state === 'connected' && device) return device.name;
    if (connection.state === 'starting_bridge') return 'Starting Muse bridge';
    if (connection.state === 'connecting_bluetooth') return 'Connecting Bluetooth';
    if (connection.state === 'waiting_for_lsl') return 'Waiting for LSL';
    if (connection.state === 'disconnecting') return 'Disconnecting Muse';
    if (connection.state === 'failed') return 'Muse connection unavailable';
    return 'No Muse connected';
  }

  museStatusTone(): 'neutral' | 'busy' | 'connected' | 'failed' {
    const connection = this.muse.connectionStatus();
    const expectedKind = this.auth.isAdmin() ? 'collection' : 'user';
    if (!connection.owner || connection.owner.kind !== expectedKind) {
      return 'neutral';
    }
    if (connection.state === 'connected' && this.muse.connectedDevice()) return 'connected';
    if (connection.state === 'failed') return 'failed';
    if (['starting_bridge', 'connecting_bluetooth', 'waiting_for_lsl', 'disconnecting'].includes(connection.state)) return 'busy';
    return 'neutral';
  }
}
