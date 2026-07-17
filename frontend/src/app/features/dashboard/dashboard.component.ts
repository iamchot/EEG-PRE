import { Component, OnInit, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { AuthService } from '../../core/services/auth.service';
import { PersonaService, Persona, ArtStyle } from '../../core/services/persona.service';
import { ComicService, Comic } from '../../core/services/comic.service';

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
          <div class="mini-status"><span class="dot good"></span><div><strong>ComfyUI Engine</strong><small>Ready for comic panels</small></div></div>
          <div class="mini-status"><span class="dot warn"></span><div><strong>Muse 2 Device</strong><small>Connect during session</small></div></div>
          <div class="mini-status"><span class="dot good"></span><div><strong>Gemini Story</strong><small>Prompt pipeline enabled</small></div></div>
        </div>
      </section>

      <section class="status-grid" aria-label="System status">
        @for (item of systemStatus; track item.label) {
          <article class="status-card card">
            <div class="status-top"><span class="dot" [class.good]="item.state === 'good'" [class.warn]="item.state === 'warn'"></span><span>{{ item.label }}</span></div>
            <strong>{{ item.value }}</strong>
            <small>{{ item.hint }}</small>
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
  styles: [`
    .dashboard-shell { width:min(1180px, calc(100% - 32px)); margin:0 auto; padding:32px 0 56px; display:grid; gap:24px; }
    .hero { padding:34px; display:grid; grid-template-columns:1.3fr .7fr; gap:28px; overflow:hidden; position:relative; }
    .hero::after { content:''; position:absolute; inset:auto -12% -38% 38%; height:260px; background:radial-gradient(circle, rgba(244,114,182,.18), transparent 70%); pointer-events:none; }
    .eyebrow { color:var(--color-secondary); text-transform:uppercase; letter-spacing:.14em; font-weight:800; font-size:.72rem; }
    .hero-copy p { max-width:720px; font-size:1.08rem; }
    .hero-actions { display:flex; gap:12px; flex-wrap:wrap; margin-top:22px; }
    .hero-panel { border:1px solid var(--color-border); border-radius:22px; background:rgba(11,16,32,.55); padding:20px; display:grid; gap:14px; align-content:center; }
    .studio-orb { width:88px; height:88px; border-radius:28px; display:grid; place-items:center; font:800 1.6rem var(--font-en); background:linear-gradient(135deg,var(--color-primary),var(--color-accent-pink)); box-shadow:0 24px 70px rgba(139,92,246,.32); }
    .mini-status, .status-top { display:flex; align-items:center; gap:10px; }
    .mini-status small, .status-card small, .persona-main span, .comic-row span { display:block; color:var(--color-text-muted); font-size:.82rem; }
    .dot { width:10px; height:10px; border-radius:50%; background:var(--color-neutral); flex:0 0 auto; }
    .dot.good { background:var(--color-success); box-shadow:0 0 0 5px rgba(34,197,94,.12); }
    .dot.warn { background:var(--color-warning); box-shadow:0 0 0 5px rgba(245,158,11,.12); }
    .status-grid { display:grid; grid-template-columns:repeat(4,1fr); gap:14px; }
    .status-card { padding:18px; display:grid; gap:8px; }
    .status-card strong { font:800 1.15rem var(--font-en); }
    .content-grid { display:grid; grid-template-columns:1fr 1fr; gap:24px; }
    .studio-card { padding:24px; display:grid; gap:18px; align-content:start; }
    .section-title { display:flex; justify-content:space-between; align-items:flex-start; gap:16px; }
    .section-title h2 { margin:.2rem 0 0; }
    .persona-form { display:grid; gap:14px; padding:16px; border:1px solid var(--color-border); border-radius:16px; background:rgba(15,23,42,.58); }
    .inline-actions { display:flex; gap:10px; flex-wrap:wrap; }
    .persona-list, .comic-list { display:grid; gap:10px; }
    .persona-row { display:grid; grid-template-columns:auto 1fr auto auto; align-items:center; gap:12px; padding:12px; border:1px solid var(--color-border); border-radius:16px; background:rgba(11,16,32,.45); }
    .avatar { width:42px; height:42px; border-radius:14px; display:grid; place-items:center; font:800 1rem var(--font-en); background:rgba(244,114,182,.16); color:#FBCFE8; }
    .persona-main { min-width:0; }
    .persona-main span { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
    .comic-row { display:grid; grid-template-columns:90px 1fr; gap:12px; align-items:center; padding:12px; border:1px solid var(--color-border); border-radius:16px; text-decoration:none; background:rgba(11,16,32,.45); transition:transform .16s ease,border-color .16s ease; }
    .comic-row:hover { transform:translateY(-2px); border-color:rgba(167,139,250,.55); }
    .thumb-grid { display:grid; grid-template-columns:repeat(2,1fr); gap:3px; }
    .thumb-grid img { width:100%; aspect-ratio:1; object-fit:cover; border-radius:6px; background:var(--color-surface-soft); }
    .empty-box { padding:24px; border:1px dashed var(--color-border-strong); border-radius:16px; color:var(--color-text-muted); text-align:center; background:rgba(15,23,42,.35); }
    @media (max-width:920px) { .hero,.content-grid { grid-template-columns:1fr; } .status-grid { grid-template-columns:repeat(2,1fr); } }
    @media (max-width:560px) { .status-grid { grid-template-columns:1fr; } .persona-row { grid-template-columns:auto 1fr; } .persona-row .badge,.persona-row button { grid-column:2; justify-self:start; } }
  `],
})
export class DashboardComponent implements OnInit {
  personas = signal<Persona[]>([]);
  recentComics = signal<Comic[]>([]);
  showPersonaForm = signal(false);
  editingPersona = signal<Persona | null>(null);
  personaName = '';
  personaAppearance = '';
  personaStyle: ArtStyle = 'Manga';

  readonly systemStatus = [
    { label: 'Muse 2 Device', value: 'Session controlled', hint: 'เชื่อมต่อในขั้น Device', state: 'warn' },
    { label: 'ComfyUI Engine', value: 'Local ready', hint: 'ใช้ checkpoint เดียวเพื่อความนิ่ง', state: 'good' },
    { label: 'Gemini API', value: 'Story service', hint: 'สร้าง prompt และบทบรรยาย', state: 'good' },
    { label: 'Database', value: 'History saved', hint: 'เก็บ session และ comic result', state: 'good' },
  ];

  constructor(readonly auth: AuthService, private personaService: PersonaService, private comicService: ComicService) {}

  ngOnInit() { this.loadPersonas(); this.comicService.getAll(0, 6).subscribe((c) => this.recentComics.set(c)); }
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
}
