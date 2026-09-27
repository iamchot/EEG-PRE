import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import { SensorStatus } from './eeg-ws.service';

export type EmotionQuadrant = 'positive_low' | 'positive_high' | 'negative_low' | 'negative_high';
export type StimulusApprovalState = 'draft' | 'approved' | 'retired';
export type BaselineKind = 'eyes_open' | 'eyes_closed';
export type TrialState = 'scheduled' | 'rest' | 'stimulus' | 'rating' | 'completed' | 'interrupted' | 'failed';
export type CollectionSessionState = 'preparation' | 'baseline' | 'ready' | 'in_progress' | 'completed' | 'interrupted' | 'withdrawn' | 'failed';

export interface TrialRatingPoint {
  trial_id: number;
  session_id: number;
  participant_code?: string;
  stimulus_title: string;
  target_quadrant: string;
  valence: number;
  arousal: number;
  confidence: number;
  eeg_file_path?: string | null;
  raw_size_bytes?: number | null;
}

export interface QuadrantStat {
  target_count: number;
  avg_valence: number | null;
  avg_arousal: number | null;
}

export interface CollectionOverview {
  participants: number;
  sessions: number;
  trials: number;
  completed_trials?: number;
  scheduled_trials?: number;
  total_eeg_bytes?: number;
  review_counts: Record<'pending' | 'accepted' | 'rejected', number>;
  quadrant_counts: Record<EmotionQuadrant, number>;
  sessions_by_state?: Record<string, number>;
  ratings_distribution?: TrialRatingPoint[];
  quadrant_stats?: Record<string, QuadrantStat>;
}

export interface SessionTrialItem {
  id: number;
  randomized_order: number;
  stimulus_id: number;
  stimulus_title: string;
  target_quadrant: EmotionQuadrant;
  state: TrialState;
  review_state: string;
  valence_rating?: number | null;
  arousal_rating?: number | null;
  confidence?: number | null;
  eeg_file_path?: string | null;
  eeg_checksum?: string | null;
  raw_size_bytes?: number | null;
  duration_seconds?: number | null;
  started_at?: string | null;
  completed_at?: string | null;
}

export interface SessionTrialsDetail {
  session_id: number;
  participant_id: number;
  participant_code: string;
  device_id?: string | null;
  device_name?: string | null;
  state: CollectionSessionState;
  completed_trials: number;
  total_trials: number;
  total_eeg_bytes: number;
  avg_valence?: number | null;
  avg_arousal?: number | null;
  items: SessionTrialItem[];
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
  state: CollectionSessionState;
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

export interface DeviceSelectionRequest {
  device_id: string;
  device_name: string;
}

export interface ArtifactRequest {
  event_type: string;
  note?: string | null;
}

export interface RatingRequest {
  valence: number;
  arousal: number;
  confidence: number;
}

export interface InterruptRequest { reason: string; }

export interface CollectionRunnerState {
  session_id: number;
  state: CollectionSessionState;
  active_baseline: BaselineKind | null;
  current_trial_id: number | null;
  current_trial_order: number | null;
  current_stimulus_id: number | null;
  current_stimulus_title: string | null;
  trial_state: TrialState | null;
  completed_trials: number;
  total_trials: number;
  next_trial_order: number | null;
  next_trial_id: number | null;
  next_stimulus_id: number | null;
  next_stimulus_title: string | null;
  break_required: boolean;
  interruption_reason: string | null;
  accepted_clean_seconds: number;
  wall_clock_seconds: number;
  file_recovery_required: boolean;
  sensors: Record<'tp9' | 'af7' | 'af8' | 'tp10', SensorStatus>;
  sampling_rate_hz: number | null;
  sampling_rate_ok: boolean;
  live_sensor_ready: boolean;
  stimulus_start_ready: boolean;
  eyes_open_complete?: boolean;
  eyes_closed_complete?: boolean;
  quality_source: 'derived_eeg_window';
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

  createSchedule(sessionId: number): Observable<CollectionRunnerState> {
    return this.runnerPost(sessionId, '/schedule');
  }

  selectDevice(sessionId: number, body: DeviceSelectionRequest): Observable<CollectionRunnerState> {
    return this.runnerPost(sessionId, '/device', body);
  }

  startBaseline(sessionId: number, kind: BaselineKind): Observable<CollectionRunnerState> {
    return this.runnerPost(sessionId, `/baseline/${kind}/start`);
  }

  startTrialRest(sessionId: number, trialId: number): Observable<CollectionRunnerState> {
    return this.runnerPost(sessionId, `/trials/${trialId}/rest/start`);
  }

  startStimulus(sessionId: number, trialId: number): Observable<CollectionRunnerState> {
    return this.runnerPost(sessionId, `/trials/${trialId}/stimulus/start`);
  }

  markArtifact(sessionId: number, trialId: number, body: ArtifactRequest): Observable<CollectionRunnerState> {
    return this.runnerPost(sessionId, `/trials/${trialId}/artifacts`, body);
  }

  finishStimulus(sessionId: number, trialId: number): Observable<CollectionRunnerState> {
    return this.runnerPost(sessionId, `/trials/${trialId}/stimulus/finish`);
  }

  submitRating(sessionId: number, trialId: number, body: RatingRequest): Observable<CollectionRunnerState> {
    return this.runnerPost(sessionId, `/trials/${trialId}/rating`, body);
  }

  interrupt(sessionId: number, body: InterruptRequest): Observable<CollectionRunnerState> {
    return this.runnerPost(sessionId, '/interrupt', body);
  }

  resume(sessionId: number): Observable<CollectionRunnerState> {
    return this.runnerPost(sessionId, '/resume');
  }

  getRunnerState(sessionId: number): Observable<CollectionRunnerState> {
    return this.http.get<CollectionRunnerState>(`${this.baseUrl}/sessions/${sessionId}/runner-state`);
  }

  getSessionTrials(sessionId: number): Observable<SessionTrialsDetail> {
    return this.http.get<SessionTrialsDetail>(`${this.baseUrl}/sessions/${sessionId}/trials`);
  }

  getStimulusMedia(stimulusId: number): Observable<Blob> {
    return this.http.get(`${this.baseUrl}/stimuli/${stimulusId}/media`, { responseType: 'blob' });
  }

  private pagination(skip: number, limit: number): HttpParams {
    return new HttpParams().set('skip', skip).set('limit', limit);
  }

  private runnerPost(sessionId: number, path: string, body: object | null = null): Observable<CollectionRunnerState> {
    return this.http.post<CollectionRunnerState>(`${this.baseUrl}/sessions/${sessionId}${path}`, body);
  }
}
