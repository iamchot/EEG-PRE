import { Component, OnInit, signal, computed } from '@angular/core';
import { RouterLink } from '@angular/router';
import { AuthService } from '../../core/services/auth.service';
import { PersonaService, Persona } from '../../core/services/persona.service';
import { ComicService, Comic } from '../../core/services/comic.service';
import { ServiceHealth, SystemHealthState, SystemHealthService } from '../../core/services/system-health.service';

import { LanguageService } from '../../core/services/language.service';

import { TranslatePipe } from '../../core/pipes/translate.pipe';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [RouterLink, TranslatePipe],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.css',
})
export class DashboardComponent implements OnInit {
  personas = signal<Persona[]>([]);
  recentComics = signal<Comic[]>([]);
  readonly comicsPageSize = 3;
  readonly comicsPage = signal(1);
  readonly totalComicsPages = computed(() =>
    Math.max(1, Math.ceil(this.recentComics().length / this.comicsPageSize))
  );
  readonly paginatedComics = computed(() => {
    const start = (this.comicsPage() - 1) * this.comicsPageSize;
    return this.recentComics().slice(start, start + this.comicsPageSize);
  });

  readonly systemStatus = computed(() => {
    this.lang.currentLang(); // Track signal reactivity
    return this.systemStatusFromHealth();
  });
  readonly heroStatus = computed(() => this.systemStatus().filter((status) => status.label !== 'API'));

  constructor(
    readonly auth: AuthService,
    private personaService: PersonaService,
    private comicService: ComicService,
    private systemHealth: SystemHealthService,
    readonly lang: LanguageService,
  ) {}

  ngOnInit() { this.loadPersonas(); this.comicService.getAll(0, 12).subscribe((c) => { this.recentComics.set(c); this.comicsPage.set(1); }); this.systemHealth.refresh(); }
  prevComicsPage() { this.comicsPage.update((p) => Math.max(1, p - 1)); }
  nextComicsPage() { this.comicsPage.update((p) => Math.min(this.totalComicsPages(), p + 1)); }
  loadPersonas() { this.personaService.getAll().subscribe((p) => this.personas.set(p)); }
  formatAppearance(p: Persona): string {
    return (p.appearance ?? '')
      .split('|')
      .map((s) => s.trim())
      .filter(Boolean)
      .join(' · ');
  }
  getPanels(c: Comic) { return [c.panel_1_url, c.panel_2_url, c.panel_3_url, c.panel_4_url].filter(Boolean) as string[]; }
  emotionLabel(e: string | null) {
    if (!e) return this.lang.currentLang() === 'th' ? 'รอผลอารมณ์' : 'Emotion pending';
    if (this.lang.currentLang() === 'th') {
      const thMap: Record<string, string> = { happy: 'มีความสุข', sad: 'เศร้า', stressed: 'เครียด', excited: 'ตื่นเต้น' };
      return thMap[e] ?? e;
    }
    return `Emotion: ${e}`;
  }
  stateLabel(state: SystemHealthState) {
    if (state === 'available') return this.lang.t('dashboard.available');
    if (state === 'unavailable' || state === 'degraded') return this.lang.t('dashboard.unavailable');
    return state.charAt(0).toUpperCase() + state.slice(1);
  }

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
    const detail = state === 'unavailable' ? this.lang.t('dashboard.unavailable') : this.lang.t('dashboard.checked');
    return ['API', 'ComfyUI', 'Muse', 'Gemini'].map((label) => ({ label, state, detail, checkedAt: null }));
  }

  private toDashboardStatus(label: string, health: ServiceHealth): DashboardSystemStatus {
    const translatedDetail = health.state === 'available' ? this.lang.t('dashboard.available') : (health.state === 'unavailable' || health.state === 'degraded' ? this.lang.t('dashboard.unavailable') : health.detail);
    return { label, state: health.state, detail: translatedDetail, checkedAt: health.checked_at };
  }
}

interface DashboardSystemStatus {
  label: string;
  state: SystemHealthState;
  detail: string;
  checkedAt: string | null;
}
