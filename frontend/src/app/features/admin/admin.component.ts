import { Component, OnInit, signal, computed } from '@angular/core';
import { DatePipe, DecimalPipe } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { environment } from '../../../environments/environment';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

interface ActivityBar {
  day: string;
  count: number;
}

interface AdminStats {
  total_users: number;
  total_comics: number;
  emotion_distribution: Record<string, number>;
  average_rating: number;
  active_users?: number;
  eeg_samples?: number;
  daily_activity?: ActivityBar[];
}

interface AdminUser {
  id: number;
  username: string;
  email: string;
  role: string;
  is_active: boolean;
  created_at: string;
}

import { LanguageService } from '../../core/services/language.service';

import { TranslatePipe } from '../../core/pipes/translate.pipe';

@Component({
  selector: 'app-admin',
  standalone: true,
  imports: [DatePipe, DecimalPipe, FormsModule, RouterLink, TranslatePipe],
  templateUrl: './admin.component.html',
  styleUrl: './admin.component.css',
})
export class AdminComponent implements OnInit {
  activeTab = signal('stats');
  stats = signal<AdminStats | null>(null);
  users = signal<AdminUser[]>([]);
  showAddUser = signal(false);

  constructor(
    private http: HttpClient,
    readonly lang: LanguageService,
  ) {}

  readonly tabs = computed(() => {
    this.lang.currentLang();
    return [
      { key: 'stats',   icon: '', label: this.lang.t('admin.tab_stats') },
      { key: 'users',   icon: '', label: this.lang.t('admin.tab_users') },
      { key: 'dataset', icon: '', label: this.lang.t('admin.tab_dataset') },
    ];
  });

  activityBars = computed(() => {
    const raw = this.stats()?.daily_activity;
    if (raw && raw.length > 0) {
      return raw.map((item) => ({ day: item.day, val: item.count }));
    }
    return [
      { day: 'Mon', val: 0 }, { day: 'Tue', val: 0 }, { day: 'Wed', val: 0 },
      { day: 'Thu', val: 0 }, { day: 'Fri', val: 0 }, { day: 'Sat', val: 0 }, { day: 'Sun', val: 0 },
    ];
  });

  maxActivity = computed(() => {
    const maxVal = Math.max(...this.activityBars().map((b) => b.val), 0);
    return maxVal > 0 ? Math.ceil(maxVal * 1.2) : 10;
  });

  ngOnInit() {
    this.loadStats();
    this.loadUsers();
  }

  switchTab(key: string) { this.activeTab.set(key); }

  loadStats() {
    this.http.get<AdminStats>(`${environment.apiUrl}/admin/stats`).subscribe((s) => this.stats.set(s));
  }

  loadUsers() {
    this.http.get<AdminUser[]>(`${environment.apiUrl}/admin/users`).subscribe((u) => this.users.set(u));
  }

  deactivateUser(user: AdminUser) {
    this.http.patch(`${environment.apiUrl}/admin/users/${user.id}/deactivate`, {}).subscribe(() => this.loadUsers());
  }

  activateUser(user: AdminUser) {
    this.http.patch(`${environment.apiUrl}/admin/users/${user.id}/activate`, {}).subscribe(() => this.loadUsers());
  }

  deleteUser(user: AdminUser) {
    if (!confirm(`ลบผู้ใช้ "${user.username}"?`)) return;
    this.http.delete(`${environment.apiUrl}/admin/users/${user.id}`).subscribe(() => this.loadUsers());
  }

  totalEmotions = computed(() => this.emotionItems().reduce((s, i) => s + i.count, 0));

  emotionItems(): { key: string; count: number }[] {
    const dist = this.stats()?.emotion_distribution ?? {};
    return Object.entries(dist).map(([key, count]) => ({ key, count }));
  }

  donutStyle = computed(() => {
    const items = this.emotionItems();
    const total = this.totalEmotions() || 1;
    const colors: Record<string, string> = {
      happy: '#EC4899', excited: '#06B6D4', sad: '#8B5CF6', stressed: '#F59E0B',
    };
    let deg = 0;
    const segments = items.map(({ key, count }) => {
      const pct = (count / total) * 100;
      const color = colors[key] ?? '#7C3AED';
      const start = deg;
      deg += pct * 3.6;
      return `${color} ${start}deg ${deg}deg`;
    });
    if (segments.length === 0) return `background: conic-gradient(#334155 0% 100%)`;
    return `background: conic-gradient(${segments.join(', ')})`;
  });

  emotionColor(key: string): string {
    const map: Record<string, string> = { happy: '#EC4899', excited: '#06B6D4', sad: '#8B5CF6', stressed: '#F59E0B' };
    return map[key] ?? '#7C3AED';
  }

  emotionThai(key: string): string {
    const map: Record<string, string> = { happy: 'มีความสุข', sad: 'เศร้า', stressed: 'เครียด', excited: 'ตื่นเต้น' };
    return map[key] ?? key;
  }

  avatarColor(name: string): string {
    const colors = ['#7C3AED', '#0EA5E9', '#10B981', '#F59E0B', '#EF4444', '#EC4899'];
    return colors[name.charCodeAt(0) % colors.length];
  }
}
