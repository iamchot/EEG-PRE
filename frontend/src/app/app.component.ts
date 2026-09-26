import { Component, computed } from '@angular/core';
import { RouterOutlet, RouterLink, RouterLinkActive } from '@angular/router';

import { AuthService } from './core/services/auth.service';
import { MuseDeviceService } from './core/services/muse-device.service';
import { MuseWebBluetoothService } from './core/services/muse-web-bluetooth.service';

import { LanguageService } from './core/services/language.service';

import { TranslatePipe } from './core/pipes/translate.pipe';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet, RouterLink, RouterLinkActive, TranslatePipe],
  templateUrl: './app.component.html',
  styleUrl: './app.component.css',
})
export class AppComponent {
  constructor(
    readonly auth: AuthService,
    readonly muse: MuseDeviceService,
    readonly langService: LanguageService,
    readonly museWebBt: MuseWebBluetoothService,
  ) {}

  toggleLang(): void {
    this.langService.toggleLanguage();
  }

  userInitial = computed(() => (this.auth.currentUser()?.username?.[0] ?? 'U').toUpperCase());

  logout(): void {
    this.muse.resetState();
    void this.museWebBt.disconnect();
    this.auth.logout();
  }

  museStatusLabel(): string {
    const webBtState = this.museWebBt.state();
    if (webBtState === 'streaming' || webBtState === 'connected') {
      return this.museWebBt.deviceName() ?? 'Muse 2';
    }
    if (webBtState === 'connecting' || webBtState === 'requesting') {
      return 'Connecting Muse 2…';
    }
    if (webBtState === 'failed') {
      return 'Muse connection unavailable';
    }

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
    const webBtState = this.museWebBt.state();
    if (webBtState === 'streaming' || webBtState === 'connected') {
      return 'connected';
    }
    if (webBtState === 'connecting' || webBtState === 'requesting') {
      return 'busy';
    }
    if (webBtState === 'failed') {
      return 'failed';
    }

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

