import { Component, OnInit, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { computed } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { AuthService } from '../../core/services/auth.service';
import { PersonaService, Persona, ArtStyle } from '../../core/services/persona.service';
import { ComicService, Comic } from '../../core/services/comic.service';
import { ServiceHealth, SystemHealthState, SystemHealthService } from '../../core/services/system-health.service';

import { LanguageService } from '../../core/services/language.service';

import { TranslatePipe } from '../../core/pipes/translate.pipe';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [RouterLink, FormsModule, TranslatePipe],
  templateUrl: './dashboard.component.html',
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
