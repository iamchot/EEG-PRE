import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { environment } from '../../../environments/environment';

export interface Persona {
  id: number;
  user_id: number;
  persona_name: string;
  appearance: string | null;
  art_style: string;
  created_at: string;
  updated_at: string;
}

export type ArtStyle = 'Webtoon' | 'Manga' | 'American Comic' | 'Comic';

@Injectable({ providedIn: 'root' })
export class PersonaService {
  private readonly url = `${environment.apiUrl}/personas`;

  constructor(private http: HttpClient) {}

  getAll() {
    return this.http.get<Persona[]>(this.url);
  }

  getById(id: number) {
    return this.http.get<Persona>(`${this.url}/${id}`);
  }

  create(body: { persona_name: string; appearance?: string; art_style: ArtStyle }) {
    return this.http.post<Persona>(this.url, body);
  }

  update(id: number, body: Partial<{ persona_name: string; appearance: string; art_style: ArtStyle }>) {
    return this.http.patch<Persona>(`${this.url}/${id}`, body);
  }

  delete(id: number) {
    return this.http.delete(`${this.url}/${id}`);
  }
}
