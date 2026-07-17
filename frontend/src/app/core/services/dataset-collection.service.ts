import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';

export type EmotionQuadrant = 'positive_low' | 'positive_high' | 'negative_low' | 'negative_high';
export type StimulusApprovalState = 'draft' | 'approved' | 'retired';

export interface CollectionOverview {
  participants: number;
  sessions: number;
  trials: number;
  review_counts: Record<'pending' | 'accepted' | 'rejected', number>;
  quadrant_counts: Record<EmotionQuadrant, number>;
}

export interface DatasetParticipant {
  id: number;
  participant_code: string;
  consent_confirmed_at: string;
  state: 'active' | 'withdrawn';
  withdrawn_at: string | null;
  created_at: string;
}

export interface EmotionStimulus {
  id: number;
  title: string;
  file_path: string;
  checksum: string;
  duration_seconds: number;
  target_quadrant: EmotionQuadrant;
  approval_state: StimulusApprovalState;
  stimulus_set_version: string;
  created_at: string;
}

export interface CollectionSession {
  id: number;
  participant_id: number;
  device_id: string | null;
  device_name: string | null;
  completed_trials: number;
  total_trials: number;
  state: 'preparation' | 'baseline' | 'ready' | 'in_progress' | 'completed' | 'interrupted' | 'withdrawn' | 'failed';
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface ParticipantCreate { consent_confirmed_at: string; }

export interface StimulusCreate {
  title: string;
  file_path: string;
  checksum: string;
  duration_seconds: number;
  target_quadrant: EmotionQuadrant;
  approval_state: StimulusApprovalState;
  stimulus_set_version: string;
}

export interface CollectionSessionCreate {
  participant_id: number;
  device_id?: string | null;
  device_name?: string | null;
}

export interface CollectionList<T> { items: T[]; }

@Injectable({ providedIn: 'root' })
export class DatasetCollectionService {
  private readonly baseUrl = `${environment.apiUrl}/admin/dataset-collection`;

  constructor(private readonly http: HttpClient) {}

  getOverview(): Observable<CollectionOverview> {
    return this.http.get<CollectionOverview>(`${this.baseUrl}/overview`);
  }

  listParticipants(skip = 0, limit = 50): Observable<CollectionList<DatasetParticipant>> {
    return this.http.get<CollectionList<DatasetParticipant>>(`${this.baseUrl}/participants`, { params: this.pagination(skip, limit) });
  }

  createParticipant(body: ParticipantCreate): Observable<DatasetParticipant> {
    return this.http.post<DatasetParticipant>(`${this.baseUrl}/participants`, body);
  }

  listStimuli(skip = 0, limit = 50): Observable<CollectionList<EmotionStimulus>> {
    return this.http.get<CollectionList<EmotionStimulus>>(`${this.baseUrl}/stimuli`, { params: this.pagination(skip, limit) });
  }

  createStimulus(body: StimulusCreate): Observable<EmotionStimulus> {
    return this.http.post<EmotionStimulus>(`${this.baseUrl}/stimuli`, body);
  }

  listSessions(skip = 0, limit = 50): Observable<CollectionList<CollectionSession>> {
    return this.http.get<CollectionList<CollectionSession>>(`${this.baseUrl}/sessions`, { params: this.pagination(skip, limit) });
  }

  createSession(body: CollectionSessionCreate): Observable<CollectionSession> {
    return this.http.post<CollectionSession>(`${this.baseUrl}/sessions`, body);
  }

  private pagination(skip: number, limit: number): HttpParams {
    return new HttpParams().set('skip', skip).set('limit', limit);
  }
}
