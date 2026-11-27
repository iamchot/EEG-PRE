import { Component, OnInit, computed, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { PersonaService, Persona } from '../../core/services/persona.service';
import { AppSelectComponent, AppSelectOption } from '../../shared/components/app-select/app-select.component';

interface PersonaForm {
  persona_name: string;
  age: number | null;
  gender: string;
  face_features: string;
  hairstyle: string;
  outfit: string;
  distinctive: string;
}

import { LanguageService } from '../../core/services/language.service';

import { TranslatePipe } from '../../core/pipes/translate.pipe';

@Component({
  selector: 'app-persona',
  standalone: true,
  imports: [FormsModule, RouterLink, TranslatePipe, AppSelectComponent],
  templateUrl: './persona.component.html',
  styleUrl: './persona.component.css',
})
export class PersonaComponent implements OnInit {
  personas = signal<Persona[]>([]);
  showModal = signal(false);
  editingId = signal<number | null>(null);
  saving = signal(false);

  form: PersonaForm = this.emptyForm();
  readonly genderOptions = computed<AppSelectOption<string>[]>(() => {
    const isTh = this.lang.currentLang() === 'th';
    return [
      { value: 'Male', label: isTh ? 'ชาย' : 'Male' },
      { value: 'Female', label: isTh ? 'หญิง' : 'Female' },
      { value: 'Other', label: isTh ? 'อื่นๆ' : 'Other' },
    ];
  });

  constructor(
    private personaService: PersonaService,
    readonly lang: LanguageService,
  ) {}

  ngOnInit() { this.loadPersonas(); }

  loadPersonas() {
    this.personaService.getAll().subscribe((p) => this.personas.set(p));
  }

  formatAppearance(p: Persona): string {
    return (p.appearance ?? '')
      .split('|')
      .map((s) => s.trim())
      .filter(Boolean)
      .join(' · ');
  }

  emptyForm(): PersonaForm {
    return { persona_name: '', age: null, gender: 'Male', face_features: '', hairstyle: '', outfit: '', distinctive: '' };
  }

  openCreate() { this.form = this.emptyForm(); this.editingId.set(null); this.showModal.set(true); }

  openEdit(p: Persona) {
    const parts = (p.appearance ?? '').split('|').map((s) => s.trim());
    const hasGenderPrefix = parts.length >= 6 || ['Male', 'Female', 'Other'].includes(parts[0] ?? '');
    if (hasGenderPrefix) {
      const ageMatch = (parts[1] ?? '').match(/\d+/);
      this.form = {
        persona_name: p.persona_name,
        gender: parts[0] || 'Male',
        age: ageMatch ? Number(ageMatch[0]) : null,
        face_features: parts[2] ?? '',
        hairstyle: parts[3] ?? '',
        outfit: parts[4] ?? '',
        distinctive: parts[5] ?? '',
      };
    } else {
      this.form = {
        persona_name: p.persona_name,
        age: null,
        gender: 'Male',
        face_features: parts[0] ?? '',
        hairstyle: parts[1] ?? '',
        outfit: parts[2] ?? '',
        distinctive: parts[3] ?? '',
      };
    }
    this.editingId.set(p.id);
    this.showModal.set(true);
  }

  closeModal() { this.showModal.set(false); this.editingId.set(null); }

  savePersona() {
    if (!this.form.persona_name.trim()) return;
    this.saving.set(true);
    const ageText = this.form.age ? `age ${this.form.age}` : '';
    const appearance = [
      this.form.gender,
      ageText,
      this.form.face_features,
      this.form.hairstyle,
      this.form.outfit,
      this.form.distinctive,
    ]
      .map((s) => s.trim())
      .join('|');
    const body = { persona_name: this.form.persona_name.trim(), appearance, art_style: 'Manga' as const };
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
