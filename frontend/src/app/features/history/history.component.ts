import { Component, OnInit, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { ComicService, Comic } from '../../core/services/comic.service';
import { DatePipe } from '@angular/common';

@Component({
  selector: 'app-history',
  standalone: true,
  imports: [RouterLink, DatePipe],
  template: `
    <div class="history-page">
      <div class="page-header">
        <h1>ประวัติผลงาน</h1>
        <a routerLink="/eeg-session" class="btn btn-primary" id="btn-new-comic">
          + สร้างการ์ตูนใหม่
        </a>
      </div>

      @if (loading()) {
        <div class="loading-center">
          <div class="spinner" style="width:40px;height:40px;border-width:3px"></div>
        </div>
      }

      <div class="gallery-grid">
        @for (comic of comics(); track comic.id) {
          <a routerLink="/comic/{{ comic.id }}" class="gallery-card card" [id]="'gallery-' + comic.id">
            <div class="panels-preview">
              @for (url of getPanels(comic); track url) {
                <img [src]="url" [alt]="'Panel'" class="panel-mini" loading="lazy"/>
              }
              @if (getPanels(comic).length === 0) {
                <div class="no-panels">🎨</div>
              }
            </div>
            <div class="gallery-info">
              <p class="story-text">{{ comic.input_story }}</p>
              <div class="gallery-tags">
                @if (comic.emotion) {
                  <span class="badge badge-accent">{{ emotionEmoji(comic.emotion) }} {{ emotionThai(comic.emotion) }}</span>
                }
                @if (comic.persona_name) {
                  <span class="badge badge-neutral">{{ comic.persona_name }}</span>
                }
              </div>
              <time class="comic-date" [attr.datetime]="comic.created_at">
                {{ comic.created_at | date:'d MMM yyyy HH:mm' }}
              </time>
            </div>
          </a>
        } @empty {
          @if (!loading()) {
            <div class="empty-state">
              <span aria-hidden="true">🎨</span>
              <h2>ยังไม่มีผลงาน</h2>
              <p>เริ่มสร้างการ์ตูนจากคลื่นสมองของคุณ</p>
              <a routerLink="/eeg-session" class="btn btn-primary" id="btn-start-first">เริ่มเลย!</a>
            </div>
          }
        }
      </div>

      @if (hasMore()) {
        <div class="load-more">
          <button class="btn btn-secondary" (click)="loadMore()" [disabled]="loading()" id="btn-load-more">
            โหลดเพิ่มเติม
          </button>
        </div>
      }
    </div>
  `,
  styles: [`
    .history-page { padding: 32px; max-width: 1200px; margin: 0 auto; display: flex; flex-direction: column; gap: 24px; }
    .page-header { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 16px; }
    .loading-center { display: flex; justify-content: center; padding: 40px; }

    .gallery-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 20px; }

    .gallery-card { text-decoration: none; display: flex; flex-direction: column; gap: 12px; transition: transform 200ms ease; cursor: pointer; }
    .gallery-card:hover { transform: translateY(-4px); }
    .gallery-card:focus-visible { outline: 3px solid var(--color-focus); }

    .panels-preview { display: grid; grid-template-columns: repeat(2, 1fr); gap: 3px; border-radius: 8px; overflow: hidden; background: var(--color-surface-elevated); aspect-ratio: 1; }
    .panel-mini { width: 100%; height: 100%; object-fit: cover; }
    .no-panels { display: flex; align-items: center; justify-content: center; font-size: 3rem; grid-column: 1/-1; }

    .gallery-info { display: flex; flex-direction: column; gap: 8px; }
    .story-text { font-size: 0.875rem; color: var(--color-text-secondary); display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
    .gallery-tags { display: flex; gap: 6px; flex-wrap: wrap; }
    .comic-date { font-size: 0.75rem; color: var(--color-text-muted); }

    .empty-state { grid-column: 1/-1; display: flex; flex-direction: column; align-items: center; gap: 16px; padding: 80px 24px; text-align: center; }
    .empty-state span { font-size: 4rem; }
    .load-more { display: flex; justify-content: center; padding-top: 8px; }

    @media (max-width: 480px) { .gallery-grid { grid-template-columns: 1fr; } }
  `],
})
export class HistoryComponent implements OnInit {
  comics = signal<Comic[]>([]);
  loading = signal(true);
  hasMore = signal(false);
  private page = 0;
  private readonly PAGE_SIZE = 12;

  constructor(private comicService: ComicService) {}

  ngOnInit() { this.loadMore(); }

  loadMore() {
    this.loading.set(true);
    this.comicService.getAll(this.page * this.PAGE_SIZE, this.PAGE_SIZE).subscribe({
      next: (items) => {
        this.comics.update((c) => [...c, ...items]);
        this.hasMore.set(items.length === this.PAGE_SIZE);
        this.page++;
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }

  getPanels(c: Comic) { return [c.panel_1_url, c.panel_2_url, c.panel_3_url, c.panel_4_url].filter(Boolean) as string[]; }
  emotionEmoji(e: string) { return ({ happy:'😊', sad:'😢', stressed:'😤', excited:'🎉' })[e] ?? '🧠'; }
  emotionThai(e: string) { return ({ happy:'มีความสุข', sad:'เศร้า', stressed:'เครียด', excited:'ตื่นเต้น' })[e] ?? e; }
}
