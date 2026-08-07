import { Component, OnInit, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { computed } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { AuthService } from '../../core/services/auth.service';
import { PersonaService, Persona, ArtStyle } from '../../core/services/persona.service';
import { ComicService, Comic } from '../../core/services/comic.service';
import { ServiceHealth, SystemHealthState, SystemHealthService } from '../../core/services/system-health.service';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [RouterLink, FormsModule],
  template: `
    <main class="dashboard-shell">
      <section class="hero card">
        <div class="hero-copy">
          <span class="eyebrow">Dream Lab / Comic Studio</span>
          <h1>Brainwave to Comic Studio</h1>
          <p>สร้างคอมิก 4 ช่องจากอารมณ์ที่วิเคราะห์ผ่านคลื่นสมอง โดยคุมทุกขั้นตอนผ่าน Local FastAPI, Muse 2 และ ComfyUI</p>
          <div class="hero-actions">
            <a routerLink="/eeg-session" class="btn btn-primary btn-lg" id="btn-start-session">Start EEG Session</a>
            <a routerLink="/history" class="btn btn-secondary btn-lg">View History</a>
          </div>
        </div>
        <div class="hero-panel" aria-label="Studio status summary">
          <div class="studio-orb">DC</div>
          @for (item of heroStatus(); track item.label) {
            <div class="mini-status"><span class="dot" [class]="item.state"></span><div><strong>{{ item.label }}</strong><small>{{ item.detail }}</small></div></div>
          }
        </div>
      </section>

      <section class="status-grid" aria-label="System status">
        @for (item of systemStatus(); track item.label) {
          <article class="status-card card" [attr.data-health-service]="item.label" [attr.data-health-state]="item.state">
            <div class="status-top"><span class="dot" [class]="item.state"></span><span>{{ item.label }}</span></div>
            <strong>{{ stateLabel(item.state) }}</strong>
            <small>{{ item.detail }}</small>
            <small>Checked: {{ item.checkedAt || 'Not checked yet' }}</small>
          </article>
        }
      </section>

      <section class="content-grid">
        <article class="card studio-card">
          <div class="section-title">
            <div><span class="eyebrow">Persona</span><h2>Character Studio</h2></div>
            <button class="btn btn-secondary btn-sm" (click)="showPersonaForm.set(true)" id="btn-add-persona">+ Add Persona</button>
          </div>

          @if (showPersonaForm()) {
            <div class="persona-form animate-fade-in">
              <div class="form-group">
                <label class="form-label" for="persona-name">Character name</label>
                <input id="persona-name" class="form-input" [(ngModel)]="personaName" placeholder="เช่น Mew, Luna, Nira" />
              </div>
              <div class="form-group">
                <label class="form-label" for="persona-appearance">Persona detail</label>
                <textarea id="persona-appearance" class="form-textarea" [(ngModel)]="personaAppearance" placeholder="ทรงผม ชุด สีหลัก บุคลิก และจุดเด่นที่ต้องคงไว้ทุกช่อง"></textarea>
              </div>
              <div class="form-group">
                <label class="form-label" for="persona-style">Art style</label>
                <select id="persona-style" class="form-select" [(ngModel)]="personaStyle">
                  <option value="Manga">Manga</option>
                  <option value="Webtoon">Webtoon</option>
                  <option value="Comic">Comic</option>
                  <option value="American Comic">American Comic</option>
                </select>
              </div>
              <div class="inline-actions">
                <button class="btn btn-primary" (click)="savePersona()" [disabled]="!personaName.trim()">Save Persona</button>
                <button class="btn btn-secondary" (click)="cancelPersona()">Cancel</button>
              </div>
            </div>
          }

          <div class="persona-list">
            @for (persona of personas(); track persona.id) {
              <div class="persona-row">
                <div class="avatar">{{ persona.persona_name.slice(0, 1).toUpperCase() }}</div>
                <div class="persona-main">
                  <strong>{{ persona.persona_name }}</strong>
                  <span>{{ persona.appearance || 'ยังไม่มีรายละเอียด persona' }}</span>
                </div>
                <span class="badge badge-accent">{{ persona.art_style }}</span>
                <button class="btn btn-secondary btn-sm" (click)="editPersona(persona)">Edit</button>
              </div>
            } @empty {
              <div class="empty-box">ยังไม่มีตัวละคร — เพิ่ม persona เพื่อให้คอมิกคุมหน้าตาและชุดได้สม่ำเสมอ</div>
            }
          </div>
        </article>

        <article class="card studio-card">
          <div class="section-title">
            <div><span class="eyebrow">Latest Comic</span><h2>Recent Results</h2></div>
            <a routerLink="/history" class="btn btn-secondary btn-sm">All comics</a>
          </div>
          <div class="comic-list">
            @for (comic of recentComics(); track comic.id) {
              <a class="comic-row" [routerLink]="['/comic', comic.id]">
                <div class="thumb-grid">
                  @for (url of getPanels(comic); track url) { <img [src]="url" alt="comic panel" loading="lazy" /> }
                </div>
                <div>
                  <strong>{{ comic.input_story }}</strong>
                  <span>{{ emotionLabel(comic.emotion) }} · {{ comic.persona_name || 'No persona' }}</span>
                </div>
              </a>
            } @empty {
              <div class="empty-box">ยังไม่มีผลงานล่าสุด กด Start EEG Session เพื่อสร้างคอมิกแรก</div>
            }
          </div>
        </article>
      </section>
    </main>
  `,
  styleUrl: './dashboard.component.css',
})
export class DashboardComponent implements OnInit {
  personas = signal<Persona[]>([]);
  recentComics = signal<Comic[]>([]);
  showPersonaForm = signal(false);
  editingPersona = signal<Persona | null>(null);
  personaName = '';
  personaAppearance = '';
  personaStyle: ArtStyle = 'Manga';

  readonly systemStatus = computed(() => this.systemStatusFromHealth());
  readonly heroStatus = computed(() => this.systemStatus().filter((status) => status.label !== 'API'));

  constructor(
    readonly auth: AuthService,
    private personaService: PersonaService,
    private comicService: ComicService,
    private systemHealth: SystemHealthService,
  ) {}

  ngOnInit() { this.loadPersonas(); this.comicService.getAll(0, 6).subscribe((c) => this.recentComics.set(c)); this.systemHealth.refresh(); }
  loadPersonas() { this.personaService.getAll().subscribe((p) => this.personas.set(p)); }
  savePersona() {
    const body = { persona_name: this.personaName.trim(), appearance: this.personaAppearance.trim(), art_style: this.personaStyle };
    const request = this.editingPersona() ? this.personaService.update(this.editingPersona()!.id, body) : this.personaService.create(body);
    request.subscribe(() => { this.loadPersonas(); this.cancelPersona(); });
  }
  editPersona(p: Persona) { this.editingPersona.set(p); this.personaName = p.persona_name; this.personaAppearance = p.appearance ?? ''; this.personaStyle = p.art_style as ArtStyle; this.showPersonaForm.set(true); }
  cancelPersona() { this.showPersonaForm.set(false); this.editingPersona.set(null); this.personaName = ''; this.personaAppearance = ''; this.personaStyle = 'Manga'; }
  getPanels(c: Comic) { return [c.panel_1_url, c.panel_2_url, c.panel_3_url, c.panel_4_url].filter(Boolean) as string[]; }
  emotionLabel(e: string | null) { return e ? `Emotion: ${e}` : 'Emotion pending'; }
  stateLabel(state: SystemHealthState) { return state.charAt(0).toUpperCase() + state.slice(1); }

  private systemStatusFromHealth(): DashboardSystemStatus[] {
    const health = this.systemHealth.health();
    if (health) {
      return [
        this.toDashboardStatus('API', health.api),
        this.toDashboardStatus('ComfyUI', health.comfyui),
        this.toDashboardStatus('Muse', health.muse),
        this.toDashboardStatus('Gemini', health.gemini),
      ];
    }

    const state: SystemHealthState = this.systemHealth.loading()
      ? 'checking'
      : this.systemHealth.error()
        ? 'unavailable'
        : 'unknown';
    const detail = state === 'unavailable' ? 'Health check failed' : state === 'checking' ? 'Checking system health' : 'Not checked yet';
    return ['API', 'ComfyUI', 'Muse', 'Gemini'].map((label) => ({ label, state, detail, checkedAt: null }));
  }

  private toDashboardStatus(label: string, health: ServiceHealth): DashboardSystemStatus {
    return { label, state: health.state, detail: health.detail, checkedAt: health.checked_at };
  }
}

interface DashboardSystemStatus {
  label: string;
  state: SystemHealthState;
  detail: string;
  checkedAt: string | null;
}
