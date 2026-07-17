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

@Component({
  selector: 'app-persona',
  standalone: true,
  imports: [FormsModule, RouterLink],
  template: `
    <div class="persona-page">
      <!-- Page Header -->
      <div class="page-header">
        <a routerLink="/dashboard" class="back-btn" id="link-back-dashboard">
          <span aria-hidden="true">←</span>
        </a>
        <div>
          <h1>จัดการตัวละคร <span class="header-sub">(Persona Manager)</span></h1>
        </div>
        <button class="btn btn-primary" (click)="openCreate()" id="btn-create-persona">
          <span aria-hidden="true">👤</span> + สร้างตัวละครใหม่
        </button>
      </div>

      <!-- Art Style Filter -->
      <div class="style-filters">
        @for (s of artStyles; track s) {
          <button class="style-chip" [class.active]="filterStyle() === s" (click)="filterStyle.set(filterStyle() === s ? null : s)">
            {{ s }}
          </button>
        }
      </div>

      <!-- Persona Cards -->
      <div class="persona-grid">
        @for (p of filteredPersonas(); track p.id) {
          <div class="persona-card">
            <div class="persona-avatar">{{ p.persona_name[0].toUpperCase() }}</div>
            <div class="persona-info">
              <div class="persona-name">{{ p.persona_name }}</div>
              <div class="persona-detail">{{ p.appearance || 'ยังไม่มีรายละเอียด' }}</div>
              <div class="persona-badges">
                <span class="style-badge">{{ p.art_style }}</span>
              </div>
            </div>
            <div class="persona-actions">
              <button class="icon-btn" (click)="openEdit(p)" [id]="'btn-edit-' + p.id" title="แก้ไข">✏️</button>
              <button class="icon-btn danger" (click)="deletePersona(p)" [id]="'btn-delete-' + p.id" title="ลบ">🗑️</button>
            </div>
          </div>
        } @empty {
          <div class="empty-state">
            <div class="empty-icon">👤</div>
            <h3>ยังไม่มีตัวละคร</h3>
            <p>สร้างตัวละครเพื่อให้คอมิกมีหน้าตาสม่ำเสมอทุกช่อง</p>
            <button class="btn btn-primary" (click)="openCreate()">+ สร้างตัวละครแรก</button>
          </div>
        }
      </div>
    </div>

    <!-- ═══ Modal ═══ -->
    @if (showModal()) {
      <div class="modal-backdrop" (click)="closeModal()" role="dialog" aria-modal="true" aria-label="สร้างตัวละคร">
        <div class="modal-panel" (click)="$event.stopPropagation()">
          <!-- Modal Header -->
          <div class="modal-header">
            <div class="modal-title-row">
              <span class="modal-icon" aria-hidden="true">👤</span>
              <h2>{{ editingId() ? 'แก้ไขตัวละคร' : 'สร้างตัวละครใหม่' }}</h2>
            </div>
            <button class="close-btn" (click)="closeModal()" id="btn-modal-close" aria-label="ปิด">✕</button>
          </div>

          <form (ngSubmit)="savePersona()" novalidate class="modal-form">
            <!-- Two columns -->
            <div class="form-cols">
              <!-- Left: Basic Info -->
              <div class="form-col">
                <div class="col-title">ข้อมูลพื้นฐาน</div>

                <div class="form-group">
                  <label class="form-label" for="pf-name">ชื่อตัวละคร</label>
                  <input id="pf-name" class="form-input" [(ngModel)]="form.persona_name" name="persona_name"
                    placeholder="เช่น ฮีโร่, มานะ" required />
                </div>

                <div class="form-row-2">
                  <div class="form-group">
                    <label class="form-label" for="pf-age">อายุ</label>
                    <input id="pf-age" type="number" class="form-input" [(ngModel)]="form.age" name="age"
                      placeholder="20" min="1" max="200" />
                  </div>
                  <div class="form-group">
                    <label class="form-label" for="pf-gender">เพศ</label>
                    <select id="pf-gender" class="form-select" [(ngModel)]="form.gender" name="gender">
                      <option value="ชาย (Male)">ชาย (Male)</option>
                      <option value="หญิง (Female)">หญิง (Female)</option>
                      <option value="อื่นๆ (Other)">อื่นๆ (Other)</option>
                    </select>
                  </div>
                </div>

                <div class="col-title" style="margin-top:8px">เครื่องแต่งกายและจุดเด่น</div>

                <div class="form-group">
                  <label class="form-label" for="pf-outfit">สไตล์การแต่งตัว</label>
                  <input id="pf-outfit" class="form-input" [(ngModel)]="form.outfit" name="outfit"
                    placeholder="เช่น ชุดนักเรียน, ชุดแฟนตาซี" />
                </div>

                <div class="form-group">
                  <label class="form-label" for="pf-distinctive">จุดเด่นเฉพาะตัว</label>
                  <input id="pf-distinctive" class="form-input" [(ngModel)]="form.distinctive" name="distinctive"
                    placeholder="เช่น ใส่แว่น, เจาะหู, มีแผลเป็นที่แก้ม" />
                </div>

                <div class="form-group">
                  <label class="form-label" for="pf-style">สไตล์ภาพ (Art Style)</label>
                  <select id="pf-style" class="form-select" [(ngModel)]="form.art_style" name="art_style">
                    @for (s of artStyles; track s) {
                      <option [value]="s">{{ s }}</option>
                    }
                  </select>
                </div>
              </div>

              <!-- Right: Appearance -->
              <div class="form-col">
                <div class="col-title">รูปลักษณ์ภายนอก</div>

                <div class="form-group">
                  <label class="form-label" for="pf-face">ลักษณะหน้าตา</label>
                  <input id="pf-face" class="form-input" [(ngModel)]="form.face_features" name="face_features"
                    placeholder="เช่น ใบหน้าเรียว, ตากลมโต" />
                </div>

                <div class="form-group">
                  <label class="form-label" for="pf-hair">ทรงผม</label>
                  <input id="pf-hair" class="form-input" [(ngModel)]="form.hairstyle" name="hairstyle"
                    placeholder="เช่น ผมสั้นสีดำ, ผมยาวลอนสีทอง" />
                </div>

                <!-- Preview box -->
                @if (form.persona_name) {
                  <div class="preview-box">
                    <div class="preview-avatar">{{ form.persona_name[0].toUpperCase() }}</div>
                    <div class="preview-info">
                      <div class="preview-name">{{ form.persona_name }}</div>
                      @if (form.age) { <div class="preview-meta">อายุ {{ form.age }} · {{ form.gender }}</div> }
                      <div class="preview-style">{{ form.art_style }}</div>
                    </div>
                  </div>
                }
              </div>
            </div>

            <!-- Modal Footer -->
            <div class="modal-footer">
              <button type="button" class="btn btn-secondary" (click)="closeModal()" id="btn-cancel">ยกเลิก</button>
              <button type="submit" class="btn btn-primary" [disabled]="!form.persona_name.trim() || saving()" id="btn-save-persona">
                @if (saving()) {
                  <span class="spinner-sm"></span> กำลังบันทึก...
                } @else {
                  <span aria-hidden="true">💾</span> บันทึกตัวละคร
                }
              </button>
            </div>
          </form>
        </div>
      </div>
    }
  `,
  styles: [`
    .persona-page { padding: 32px 36px; max-width: 1100px; margin: 0 auto; display: flex; flex-direction: column; gap: 24px; }

    /* Header */
    .page-header { display: flex; align-items: center; gap: 16px; }
    .back-btn {
      width: 40px; height: 40px; border-radius: 10px;
      background: #151D35; border: 1px solid #334155;
      display: flex; align-items: center; justify-content: center;
      color: #CBD5E1; text-decoration: none; font-size: 1.1rem;
      transition: background 150ms;
    }
    .back-btn:hover { background: #1E293B; }
    .page-header h1 { font-size: 1.5rem; font-weight: 800; color: #F8FAFC; margin: 0; }
    .header-sub { color: #94A3B8; font-weight: 400; font-size: 1.125rem; }
    .page-header .btn { margin-left: auto; }

    /* Style filters */
    .style-filters { display: flex; gap: 8px; flex-wrap: wrap; }
    .style-chip {
      padding: 6px 16px; border-radius: 20px;
      border: 1px solid #334155; background: #151D35;
      color: #94A3B8; font-size: 0.875rem; cursor: pointer;
      transition: all 150ms;
    }
    .style-chip.active { background: #7C3AED; border-color: #7C3AED; color: white; }
    .style-chip:hover:not(.active) { border-color: #475569; color: #CBD5E1; }

    /* Grid */
    .persona-grid { display: flex; flex-direction: column; gap: 10px; }
    .persona-card {
      display: flex; align-items: center; gap: 16px;
      padding: 16px 20px;
      background: #151D35; border: 1px solid #1E293B;
      border-radius: 14px;
      transition: border-color 150ms;
    }
    .persona-card:hover { border-color: rgba(124,58,237,0.3); }

    .persona-avatar {
      width: 48px; height: 48px; border-radius: 14px;
      background: linear-gradient(135deg, rgba(244,114,182,0.2), rgba(167,139,250,0.2));
      border: 1px solid rgba(244,114,182,0.25);
      display: flex; align-items: center; justify-content: center;
      font-size: 1.25rem; font-weight: 700; color: #FBCFE8;
      flex-shrink: 0;
    }
    .persona-info { flex: 1; min-width: 0; }
    .persona-name { font-weight: 700; font-size: 1rem; color: #F8FAFC; }
    .persona-detail { font-size: 0.8125rem; color: #64748B; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .persona-badges { margin-top: 6px; }
    .style-badge {
      padding: 2px 10px; border-radius: 6px;
      background: rgba(124,58,237,0.15); color: #A78BFA;
      border: 1px solid rgba(124,58,237,0.25);
      font-size: 0.75rem; font-weight: 600;
    }
    .persona-actions { display: flex; gap: 8px; }
    .icon-btn {
      width: 34px; height: 34px; border-radius: 8px; border: none;
      background: rgba(30,41,59,0.8); cursor: pointer;
      display: flex; align-items: center; justify-content: center;
      font-size: 0.9rem; transition: background 150ms;
    }
    .icon-btn:hover { background: #1E293B; }
    .icon-btn.danger:hover { background: rgba(239,68,68,0.15); }

    /* Empty */
    .empty-state { text-align: center; padding: 60px 24px; border: 1px dashed #334155; border-radius: 16px; }
    .empty-icon { font-size: 3rem; margin-bottom: 12px; }
    .empty-state h3 { color: #F8FAFC; margin: 0 0 8px; }
    .empty-state p { color: #64748B; margin: 0 0 20px; }

    /* Buttons */
    .btn { display: flex; align-items: center; gap: 7px; border: none; cursor: pointer; border-radius: 9px; font-size: 0.9rem; font-weight: 600; transition: all 150ms; padding: 10px 18px; }
    .btn-primary { background: #7C3AED; color: white; }
    .btn-primary:hover:not(:disabled) { background: #6D28D9; }
    .btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }
    .btn-secondary { background: #1E293B; color: #CBD5E1; border: 1px solid #334155; }
    .btn-secondary:hover { background: #263349; }

    /* ═══ Modal ═══ */
    .modal-backdrop {
      position: fixed; inset: 0; z-index: 100;
      background: rgba(8, 13, 33, 0.75);
      backdrop-filter: blur(6px);
      display: flex; align-items: center; justify-content: center;
      padding: 24px;
    }
    .modal-panel {
      background: #0F172A;
      border: 1px solid rgba(124,58,237,0.25);
      border-radius: 20px;
      padding: 28px 32px;
      width: 100%; max-width: 680px;
      max-height: 90vh; overflow-y: auto;
      animation: slide-up 220ms ease;
    }
    @keyframes slide-up { from { opacity:0; transform:translateY(16px) } to { opacity:1; transform:translateY(0) } }

    .modal-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 24px; }
    .modal-title-row { display: flex; align-items: center; gap: 10px; }
    .modal-icon { font-size: 1.4rem; }
    .modal-header h2 { font-size: 1.125rem; font-weight: 700; color: #F8FAFC; margin: 0; }
    .close-btn {
      width: 32px; height: 32px; border-radius: 8px;
      background: #1E293B; border: 1px solid #334155;
      color: #94A3B8; cursor: pointer; font-size: 0.9rem;
      display: flex; align-items: center; justify-content: center;
      transition: all 150ms;
    }
    .close-btn:hover { background: rgba(239,68,68,0.15); color: #EF4444; }

    .modal-form { display: flex; flex-direction: column; gap: 20px; }

    .form-cols { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }
    .form-col { display: flex; flex-direction: column; gap: 14px; }

    .col-title { font-size: 0.75rem; font-weight: 700; color: #64748B; letter-spacing: 0.06em; text-transform: uppercase; }

    .form-group { display: flex; flex-direction: column; gap: 6px; }
    .form-row-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
    .form-label { font-size: 0.8125rem; font-weight: 500; color: #94A3B8; }
    .form-input, .form-select {
      padding: 10px 14px;
      background: #151D35; border: 1px solid #334155;
      border-radius: 9px; color: #F8FAFC;
      font-size: 0.875rem; transition: border-color 180ms;
      width: 100%; box-sizing: border-box;
    }
    .form-input:focus, .form-select:focus {
      outline: none; border-color: #7C3AED;
      box-shadow: 0 0 0 3px rgba(124,58,237,0.15);
    }
    .form-input::placeholder { color: #475569; }
    .form-select { appearance: none; cursor: pointer; }

    /* Preview box */
    .preview-box {
      display: flex; align-items: center; gap: 12px;
      padding: 14px; border-radius: 12px;
      background: rgba(124,58,237,0.08);
      border: 1px solid rgba(124,58,237,0.2);
      margin-top: 8px;
    }
    .preview-avatar {
      width: 44px; height: 44px; border-radius: 12px;
      background: linear-gradient(135deg, #7C3AED, #A78BFA);
      display: flex; align-items: center; justify-content: center;
      font-size: 1.25rem; font-weight: 700; color: white;
      flex-shrink: 0;
    }
    .preview-name { font-weight: 700; color: #F8FAFC; font-size: 0.9375rem; }
    .preview-meta { font-size: 0.8rem; color: #94A3B8; }
    .preview-style { font-size: 0.75rem; color: #7C3AED; font-weight: 600; margin-top: 4px; }

    /* Modal footer */
    .modal-footer {
      display: flex; justify-content: flex-end; gap: 10px;
      padding-top: 16px; border-top: 1px solid #1E293B;
    }

    .spinner-sm {
      width: 14px; height: 14px; border: 2px solid rgba(255,255,255,0.3);
      border-top-color: white; border-radius: 50%;
      animation: spin 0.7s linear infinite; display: inline-block;
    }
    @keyframes spin { to { transform: rotate(360deg); } }

    @media (max-width: 600px) {
      .form-cols { grid-template-columns: 1fr; }
      .persona-page { padding: 20px 16px; }
    }
  `],
})
export class PersonaComponent implements OnInit {
  personas = signal<Persona[]>([]);
  showModal = signal(false);
  editingId = signal<number | null>(null);
  saving = signal(false);
  filterStyle = signal<string | null>(null);

  readonly artStyles: ArtStyle[] = ['Manga', 'Webtoon', 'Comic', 'American Comic'];

  form: PersonaForm = this.emptyForm();

  constructor(private personaService: PersonaService, private router: Router) {}

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
