import { Component, OnInit, signal } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { PersonaService, Persona, ArtStyle } from '../../core/services/persona.service';

interface PersonaForm {
  persona_name: string;
  age: number | null;
  gender: 'ชาย (Male)' | 'หญิง (Female)' | 'อื่นๆ (Other)';
  face_features: string;
  hairstyle: string;
  outfit: string;
  distinctive: string;
  art_style: ArtStyle;
}

import { LanguageService } from '../../core/services/language.service';

import { TranslatePipe } from '../../core/pipes/translate.pipe';

@Component({
  selector: 'app-persona',
  standalone: true,
  imports: [FormsModule, RouterLink, TranslatePipe],
  templateUrl: './persona.component.html',
  styleUrl: './persona.component.css',
})
export class PersonaComponent implements OnInit {
  personas = signal<Persona[]>([]);
  showModal = signal(false);
  editingId = signal<number | null>(null);
  saving = signal(false);
  filterStyle = signal<string | null>(null);

  readonly artStyles: ArtStyle[] = ['Manga', 'Webtoon', 'Comic', 'American Comic'];

  form: PersonaForm = this.emptyForm();

  constructor(
    private personaService: PersonaService,
    private router: Router,
    readonly lang: LanguageService,
  ) {}

  ngOnInit() { this.loadPersonas(); }

  loadPersonas() {
    this.personaService.getAll().subscribe((p) => this.personas.set(p));
  }

  filteredPersonas() {
    const f = this.filterStyle();
    return f ? this.personas().filter((p) => p.art_style === f) : this.personas();
  }

  emptyForm(): PersonaForm {
    return { persona_name: '', age: null, gender: 'ชาย (Male)', face_features: '', hairstyle: '', outfit: '', distinctive: '', art_style: 'Manga' };
  }

  openCreate() { this.form = this.emptyForm(); this.editingId.set(null); this.showModal.set(true); }

  openEdit(p: Persona) {
    const parts = (p.appearance ?? '').split('|');
    this.form = {
      persona_name: p.persona_name,
      age: null,
      gender: 'ชาย (Male)',
      face_features: parts[0] ?? '',
      hairstyle: parts[1] ?? '',
      outfit: parts[2] ?? '',
      distinctive: parts[3] ?? '',
      art_style: p.art_style as ArtStyle,
    };
    this.editingId.set(p.id);
    this.showModal.set(true);
  }

  closeModal() { this.showModal.set(false); this.editingId.set(null); }

  savePersona() {
    if (!this.form.persona_name.trim()) return;
    this.saving.set(true);
    const appearance = [this.form.face_features, this.form.hairstyle, this.form.outfit, this.form.distinctive]
      .map((s) => s.trim()).join('|');
    const body = { persona_name: this.form.persona_name.trim(), appearance, art_style: this.form.art_style };
    const req = this.editingId()
      ? this.personaService.update(this.editingId()!, body)
      : this.personaService.create(body);

    req.subscribe({ next: () => { this.loadPersonas(); this.closeModal(); this.saving.set(false); },
      error: () => this.saving.set(false) });
  }

  deletePersona(p: Persona) {
    if (!confirm(`ลบตัวละคร "${p.persona_name}"?`)) return;
    this.personaService.delete(p.id).subscribe(() => this.loadPersonas());
  }
}
