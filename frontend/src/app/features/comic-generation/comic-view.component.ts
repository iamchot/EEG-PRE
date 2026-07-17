import { DatePipe } from '@angular/common';
import { Component, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { ComicService, Comic } from '../../core/services/comic.service';

@Component({
  selector: 'app-comic-view',
  standalone: true,
  imports: [RouterLink, DatePipe, FormsModule],
  template: `
    <main class="comic-shell">
      @if (loading()) {
        <section class="loading-card card"><span class="spinner"></span><p>Loading your Dream Comic...</p></section>
      }

      @if (comic()) {
        <section class="result-hero card animate-fade-in">
          <div>
            <span class="eyebrow">Your Dream Comic</span>
            <h1>{{ comic()!.input_story }}</h1>
            <div class="meta-row">
              <span class="badge badge-accent">Emotion: {{ comic()!.emotion || 'N/A' }}</span>
              <span class="badge badge-neutral">Persona: {{ comic()!.persona_name || 'Default' }}</span>
              <span class="badge badge-neutral">{{ comic()!.created_at | date:'dd MMM yyyy' }}</span>
            </div>
          </div>
          <div class="result-actions">
            <a routerLink="/eeg-session" class="btn btn-primary">Generate Again</a>
            <a routerLink="/dashboard" class="btn btn-secondary">Dashboard</a>
          </div>
        </section>

        <section class="comic-board card" aria-label="4-panel comic result">
          @for (i of [1,2,3,4]; track i) {
            <article class="panel-card">
              <div class="panel-top"><span>Panel {{ i }}</span><small>{{ panelCaption(i) }}</small></div>
              @if (getPanelUrl(i)) {
                <img class="panel-image" [src]="getPanelUrl(i)!" [alt]="'Comic panel ' + i" loading="lazy" />
              } @else {
                <div class="panel-placeholder">Panel image pending</div>
              }
              @if (getPanelDialogue(i)) { <p class="dialogue">{{ getPanelDialogue(i) }}</p> }
            </article>
          }
        </section>

        <section class="detail-grid">
          <article class="card meta-card">
            <span class="eyebrow">Generation Metadata</span>
            <dl>
              <div><dt>Model</dt><dd>Counterfeit-V3.0</dd></div>
              <div><dt>Seed</dt><dd>0</dd></div>
              <div><dt>Layout</dt><dd>2 × 2 Comic Panels</dd></div>
              <div><dt>Session</dt><dd>{{ comic()!.session_id || 'No EEG session' }}</dd></div>
            </dl>
          </article>

          <article class="card rating-card">
            <span class="eyebrow">Feedback</span>
            <h2>ให้คะแนนผลงาน</h2>
            @if (!ratingSubmitted()) {
              <div class="stars" role="group" aria-label="Rating">
                @for (star of [1,2,3,4,5]; track star) {
                  <button [class.active]="rating() >= star" (click)="rating.set(star)" [attr.aria-label]="star + ' stars'">★</button>
                }
              </div>
              <textarea class="form-textarea" [(ngModel)]="feedback" placeholder="ข้อเสนอแนะเพิ่มเติม"></textarea>
              <button class="btn btn-primary" (click)="submitRating()" [disabled]="rating() === 0">Submit Rating</button>
            } @else {
              <div class="alert alert-success">ขอบคุณสำหรับ feedback — ใช้ปรับคุณภาพคอมิกต่อได้</div>
            }
          </article>
        </section>
      }
    </main>
  `,
  styles: [`
    .comic-shell { width:min(1180px, calc(100% - 32px)); margin:0 auto; padding:32px 0 56px; display:grid; gap:22px; }
    .loading-card { min-height:320px; display:grid; place-items:center; gap:12px; }
    .result-hero { padding:28px; display:flex; justify-content:space-between; align-items:flex-start; gap:20px; }
    .result-hero h1 { max-width:760px; margin:.15rem 0 .9rem; }
    .meta-row,.result-actions { display:flex; flex-wrap:wrap; gap:10px; }
    .comic-board { padding:18px; display:grid; grid-template-columns:repeat(2,1fr); gap:18px; background:linear-gradient(180deg, rgba(248,250,252,.92), rgba(226,232,240,.92)); border-color:rgba(248,250,252,.35); }
    .panel-card { overflow:hidden; border:3px solid #0B1020; border-radius:14px; background:white; color:#0B1020; box-shadow:0 16px 35px rgba(2,6,23,.2); }
    .panel-top { display:flex; justify-content:space-between; align-items:center; gap:10px; padding:10px 12px; border-bottom:3px solid #0B1020; font:800 .8rem var(--font-en); text-transform:uppercase; }
    .panel-top small { color:#475569; font:700 .72rem var(--font-base); text-transform:none; }
    .panel-image { width:100%; aspect-ratio:4/5; object-fit:cover; display:block; background:#e2e8f0; }
    .panel-placeholder { aspect-ratio:4/5; display:grid; place-items:center; color:#64748b; background:#e2e8f0; }
    .dialogue { margin:0; padding:12px 14px; color:#0F172A; background:#fff; border-top:3px solid #0B1020; font-weight:600; }
    .detail-grid { display:grid; grid-template-columns:.8fr 1.2fr; gap:22px; }
    .meta-card,.rating-card { padding:24px; display:grid; gap:16px; align-content:start; }
    dl { display:grid; gap:10px; margin:0; }
    dl div { display:flex; justify-content:space-between; gap:16px; padding-bottom:10px; border-bottom:1px solid var(--color-border); }
    dt { color:var(--color-text-muted); } dd { margin:0; font-weight:800; }
    .stars { display:flex; gap:8px; }
    .stars button { color:rgba(148,163,184,.45); background:none; border:0; font-size:2.2rem; cursor:pointer; transition:transform .14s ease,color .14s ease; }
    .stars button.active { color:var(--color-warning); } .stars button:hover { transform:scale(1.1); }
    @media (max-width:840px) { .result-hero,.detail-grid { grid-template-columns:1fr; display:grid; } .comic-board { grid-template-columns:1fr; } }
  `],
})
export class ComicViewComponent implements OnInit {
  comic = signal<Comic | null>(null);
  loading = signal(true);
  rating = signal(0);
  feedback = '';
  ratingSubmitted = signal(false);
  constructor(private route: ActivatedRoute, private comicService: ComicService) {}
  ngOnInit() { const id = Number(this.route.snapshot.paramMap.get('id')); this.comicService.getById(id).subscribe({ next: (c) => { this.comic.set(c); this.loading.set(false); }, error: () => this.loading.set(false) }); }
  getPanelUrl(n: number): string | null { return this.comic() ? (this.comic() as unknown as Record<string, string | null>)[`panel_${n}_url`] : null; }
  getPanelDialogue(n: number): string | null { return this.comic() ? (this.comic() as unknown as Record<string, string | null>)[`panel_${n}_dialogue`] : null; }
  panelCaption(n: number) { return ['Setup', 'Portal', 'Dream flight', 'Final beat'][n - 1]; }
  submitRating() { const c = this.comic(); if (!c || this.rating() === 0) return; this.comicService.submitRating({ comic_id: c.id, stars: this.rating(), feedback: this.feedback || undefined }).subscribe(() => this.ratingSubmitted.set(true)); }
}
