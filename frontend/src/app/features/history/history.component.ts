import { Component, OnInit, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { ComicService, Comic } from '../../core/services/comic.service';
import { DatePipe } from '@angular/common';
import { LanguageService } from '../../core/services/language.service';

import { TranslatePipe } from '../../core/pipes/translate.pipe';

@Component({
  selector: 'app-history',
  standalone: true,
  imports: [RouterLink, DatePipe, TranslatePipe],
  templateUrl: './history.component.html',
  styleUrl: './history.component.css',
})
export class HistoryComponent implements OnInit {
  comics = signal<Comic[]>([]);
  loading = signal(true);
  hasMore = signal(false);
  private page = 0;
  private readonly PAGE_SIZE = 12;

  constructor(
    private comicService: ComicService,
    readonly lang: LanguageService,
  ) {}

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
  emotionEmoji(e: string) { return this.emotionThai(e); }
  emotionThai(e: string) { return ({ happy:'มีความสุข', sad:'เศร้า', stressed:'เครียด', excited:'ตื่นเต้น' })[e] ?? (e || '-'); }
}
