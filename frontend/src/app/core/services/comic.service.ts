import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
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

  constructor(private http: HttpClient) {}

  generate(body: ComicGenerateRequest) {
    return this.http.post<Comic>(`${this.url}/generate`, body);
  }

  getAll(skip = 0, limit = 20) {
    return this.http.get<Comic[]>(this.url, { params: { skip, limit } });
  }

  getById(id: number) {
    return this.http.get<Comic>(`${this.url}/${id}`);
  }

  submitRating(body: RatingCreate) {
    return this.http.post(`${this.url}/ratings`, body);
  }
}
