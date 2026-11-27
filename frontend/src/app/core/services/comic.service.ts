import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { map } from 'rxjs/operators';
import { environment } from '../../../environments/environment';

export interface Comic {
  id: number;
  user_id: number;
  session_id: number | null;
  persona_id: number | null;
  input_story: string;
  generated_prompt: string | null;
  panel_1_url: string | null;
  panel_2_url: string | null;
  panel_3_url: string | null;
  panel_4_url: string | null;
  panel_1_dialogue: string | null;
  panel_2_dialogue: string | null;
  panel_3_dialogue: string | null;
  panel_4_dialogue: string | null;
  emotion: string | null;
  persona_name: string | null;
  created_at: string;
}

export interface ComicGenerateRequest {
  session_id: number;
  persona_id?: number;
  input_story: string;
  art_style: string;
}

export interface RatingCreate {
  comic_id: number;
  stars: number;
  feedback?: string;
}

@Injectable({ providedIn: 'root' })
export class ComicService {
  private readonly url = `${environment.apiUrl}/comics`;
  private readonly backendOrigin = (() => {
    try {
      return new URL(environment.apiUrl).origin;
    } catch {
      return '';
    }
  })();

  constructor(private http: HttpClient) {}

  private resolvePanelUrl(path: string | null): string | null {
    if (!path || !path.startsWith('/') || !this.backendOrigin) return path;
    return `${this.backendOrigin}${path}`;
  }

  private normalizeComic = (c: Comic): Comic => ({
    ...c,
    panel_1_url: this.resolvePanelUrl(c.panel_1_url),
    panel_2_url: this.resolvePanelUrl(c.panel_2_url),
    panel_3_url: this.resolvePanelUrl(c.panel_3_url),
    panel_4_url: this.resolvePanelUrl(c.panel_4_url),
  });

  generate(body: ComicGenerateRequest) {
    return this.http.post<Comic>(`${this.url}/generate`, body).pipe(map(this.normalizeComic));
  }

  getAll(skip = 0, limit = 20) {
    return this.http
      .get<Comic[]>(this.url, { params: { skip, limit } })
      .pipe(map((list) => list.map(this.normalizeComic)));
  }

  getById(id: number) {
    return this.http.get<Comic>(`${this.url}/${id}`).pipe(map(this.normalizeComic));
  }

  submitRating(body: RatingCreate) {
    return this.http.post(`${this.url}/ratings`, body);
  }
}
