import { Component, OnInit, signal, computed } from '@angular/core';
import { DatePipe, DecimalPipe } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { environment } from '../../../environments/environment';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

interface AdminStats {
  total_users: number;
  total_comics: number;
  emotion_distribution: Record<string, number>;
  average_rating: number;
  active_users?: number;
  eeg_samples?: number;
}

interface AdminUser {
  id: number;
  username: string;
  email: string;
  role: string;
  is_active: boolean;
  created_at: string;
}

@Component({
  selector: 'app-admin',
  standalone: true,
  imports: [DatePipe, DecimalPipe, FormsModule, RouterLink],
  template: `
    <div class="admin-page">
      <!-- Header -->
      <div class="admin-header">
        <div class="header-title">
          <span class="shield-icon">🛡️</span>
          <div>
            <h1>Admin Dashboard <span>🔒</span></h1>
            <p>System management and subconscious data analytics</p>
          </div>
        </div>
      </div>

      <!-- Tab Bar -->
      <div class="tab-bar" role="tablist">
        @for (tab of tabs; track tab.key) {
          <button
            class="tab-btn"
            [class.active]="activeTab() === tab.key"
            (click)="switchTab(tab.key)"
            role="tab"
            [id]="'tab-' + tab.key"
            [attr.aria-selected]="activeTab() === tab.key"
          >
            <span aria-hidden="true">{{ tab.icon }}</span>
            {{ tab.label }}
          </button>
        }
      </div>

      <!-- ═══ CHECK STATISTICS ═══ -->
      @if (activeTab() === 'stats') {
        <div class="tab-content animate-fade-in" role="tabpanel">
          <!-- Stat Cards -->
          @if (stats()) {
            <div class="stat-grid">
              <div class="stat-card">
                <div class="stat-icon-wrap" style="background:rgba(124,58,237,0.15);color:#A78BFA">📖</div>
                <div class="stat-body">
                  <div class="stat-label">Total Comics</div>
                  <div class="stat-value">{{ stats()!.total_comics }}</div>
                  <div class="stat-growth">+12% from last month</div>
                </div>
              </div>
              <div class="stat-card">
                <div class="stat-icon-wrap" style="background:rgba(245,158,11,0.15);color:#F59E0B">⭐</div>
                <div class="stat-body">
                  <div class="stat-label">Avg Satisfaction</div>
                  <div class="stat-value">{{ stats()!.average_rating | number:'1.1-1' }}/5.0</div>
                  <div class="stat-hint">Based on {{ stats()!.total_comics }} reviews</div>
                </div>
              </div>
              <div class="stat-card">
                <div class="stat-icon-wrap" style="background:rgba(34,197,94,0.15);color:#22C55E">👥</div>
                <div class="stat-body">
                  <div class="stat-label">Active Users</div>
                  <div class="stat-value">{{ stats()!.active_users ?? stats()!.total_users }}</div>
                  <div class="stat-hint">Total {{ stats()!.total_users }} registered</div>
                </div>
              </div>
              <div class="stat-card">
                <div class="stat-icon-wrap" style="background:rgba(167,139,250,0.15);color:#7C3AED">🧠</div>
                <div class="stat-body">
                  <div class="stat-label">EEG Samples</div>
                  <div class="stat-value">{{ stats()!.eeg_samples ?? 0 }}</div>
                  <div class="stat-ready">Ready for training</div>
                </div>
              </div>
            </div>

            <!-- Charts Row -->
            <div class="charts-row">
              <!-- Donut Chart (CSS-based) -->
              <div class="chart-card">
                <h2><span>😊</span> Emotion Distribution</h2>
                <div class="donut-wrap">
                  <div class="donut" [style]="donutStyle()"></div>
                  <div class="donut-center">{{ totalEmotions() }}</div>
                </div>
                <div class="legend">
                  @for (item of emotionItems(); track item.key) {
                    <div class="legend-item">
                      <span class="legend-dot" [style.background]="emotionColor(item.key)"></span>
                      <span>{{ emotionThai(item.key) }}: {{ item.count }}</span>
                    </div>
                  }
                </div>
              </div>

              <!-- Bar Chart (CSS-based) -->
              <div class="chart-card">
                <h2><span>📊</span> System Activity</h2>
                <div class="bar-chart">
                  @for (bar of activityBars; track bar.day) {
                    <div class="bar-col">
                      <div class="bar-fill" [style.height.%]="(bar.val / maxActivity) * 100"></div>
                      <span class="bar-label">{{ bar.day }}</span>
                    </div>
                  }
                </div>
                <div class="bar-y-labels">
                  <span>16</span><span>12</span><span>8</span><span>4</span><span>0</span>
                </div>
              </div>
            </div>
          } @else {
            <div class="loading-wrap">
              <div class="spinner" style="width:40px;height:40px;border-width:3px" aria-label="กำลังโหลด"></div>
            </div>
          }
        </div>
      }

      <!-- ═══ MANAGE USERS ═══ -->
      @if (activeTab() === 'users') {
        <div class="tab-content animate-fade-in" role="tabpanel">
          <div class="section-header">
            <h2><span>👥</span> Manage Users</h2>
            <button class="btn btn-primary btn-sm" (click)="showAddUser.set(true)" id="btn-add-user">
              <span aria-hidden="true">👤+</span> Add User
            </button>
          </div>

          <div class="table-card">
            <table class="data-table" aria-label="รายการผู้ใช้">
              <thead>
                <tr>
                  <th scope="col">USER</th>
                  <th scope="col">ROLE</th>
                  <th scope="col">STATUS</th>
                  <th scope="col">JOINED</th>
                  <th scope="col">ACTIONS</th>
                </tr>
              </thead>
              <tbody>
                @for (user of users(); track user.id) {
                  <tr>
                    <td class="user-cell">
                      <div class="user-avatar-sm" [style.background]="avatarColor(user.username)">
                        {{ user.username[0].toUpperCase() }}
                      </div>
                      <div>
                        <div class="user-name-text">{{ user.username }}</div>
                        <div class="user-email-text">{{ user.email }}</div>
                      </div>
                    </td>
                    <td>
                      <span class="role-badge" [class.role-admin]="user.role === 'admin'" [class.role-user]="user.role === 'user'">
                        {{ user.role.toUpperCase() }}
                      </span>
                    </td>
                    <td>
                      @if (user.is_active) {
                        <span class="status-dot active"><span class="dot-circle"></span>active</span>
                      } @else {
                        <span class="status-dot suspended"><span class="dot-circle"></span>suspended</span>
                      }
                    </td>
                    <td class="date-cell">{{ user.created_at | date:'M/d/yyyy' }}</td>
                    <td class="actions-cell">
                      @if (user.is_active) {
                        <button class="icon-btn" title="Suspend user" (click)="deactivateUser(user)" [id]="'btn-suspend-' + user.id">👤-</button>
                      } @else {
                        <button class="icon-btn" title="Activate user" (click)="activateUser(user)" [id]="'btn-activate-' + user.id">👤+</button>
                      }
                      <button class="icon-btn danger" title="Delete user" (click)="deleteUser(user)" [id]="'btn-delete-' + user.id">🗑️</button>
                    </td>
                  </tr>
                } @empty {
                  <tr><td colspan="5" class="empty-td">ไม่มีผู้ใช้ในระบบ</td></tr>
                }
              </tbody>
            </table>
          </div>
        </div>
      }

      <!-- ═══ MANAGE EEG DATASET ═══ -->
      @if (activeTab() === 'dataset') {
        <div class="tab-content animate-fade-in" role="tabpanel">
          <div class="section-header">
            <h2><span>🧠</span> EEG Dataset Management</h2>
          </div>
          <div class="table-card" style="padding:24px">
            <p>Manage pseudonymous participants, approved stimuli, and collection sessions.</p>
            <a class="btn btn-primary btn-sm" routerLink="/admin/dataset-collection" id="btn-open-dataset-collection">
              Open Dataset Collection
            </a>
          </div>
        </div>
      }
    </div>
  `,
  styleUrl: './admin.component.css',
})
export class AdminComponent implements OnInit {
  activeTab = signal('stats');
  stats = signal<AdminStats | null>(null);
  users = signal<AdminUser[]>([]);
  showAddUser = signal(false);

  readonly tabs = [
    { key: 'stats',   icon: '📊', label: 'Check Statistics' },
    { key: 'users',   icon: '👥', label: 'Manage Users' },
    { key: 'dataset', icon: '🧠', label: 'Manage EEG Dataset' },
  ];

  readonly activityBars = [
    { day: 'Tue', val: 5 }, { day: 'Wed', val: 7 }, { day: 'Thu', val: 9 },
    { day: 'Fri', val: 11 }, { day: 'Sat', val: 13 }, { day: 'Sun', val: 10 },
  ];
  readonly maxActivity = 16;

  constructor(private http: HttpClient) {}

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
