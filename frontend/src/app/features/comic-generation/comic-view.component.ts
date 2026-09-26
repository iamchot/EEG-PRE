import { DatePipe } from '@angular/common';
import { Component, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { ComicService, Comic } from '../../core/services/comic.service';

@Component({
  selector: 'app-comic-view',
  standalone: true,
  imports: [RouterLink, DatePipe, FormsModule],
  templateUrl: './comic-view.component.html',
  styleUrl: './comic-view.component.css',
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
