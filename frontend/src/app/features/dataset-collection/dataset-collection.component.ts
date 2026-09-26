import { CommonModule } from '@angular/common';
import { Component, OnInit, computed, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

import {
  CollectionOverview,
  CollectionSession,
  DatasetCollectionService,
  DatasetParticipant,
  EmotionQuadrant,
  EmotionStimulus,
  StimulusApprovalState,
} from '../../core/services/dataset-collection.service';

type CollectionTab = 'overview' | 'participants' | 'stimuli' | 'sessions';

import { LanguageService, toThaiError } from '../../core/services/language.service';
import { TranslatePipe } from '../../core/pipes/translate.pipe';

@Component({
  selector: 'app-dataset-collection',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink, TranslatePipe],
  templateUrl: './dataset-collection.component.html',
  styleUrl: './dataset-collection.component.css',
})
export class DatasetCollectionComponent implements OnInit {
  constructor(
    private readonly api: DatasetCollectionService,
    readonly lang: LanguageService,
  ) {}

  readonly tabs = computed(() => {
    this.lang.currentLang();
    return [
      { key: 'overview' as CollectionTab, label: this.lang.t('dataset.tab_overview') },
      { key: 'participants' as CollectionTab, label: this.lang.t('dataset.tab_participants') },
      { key: 'stimuli' as CollectionTab, label: this.lang.t('dataset.tab_stimuli') },
      { key: 'sessions' as CollectionTab, label: this.lang.t('dataset.tab_sessions') },
    ];
  });
  readonly quadrants: EmotionQuadrant[] = ['positive_low', 'positive_high', 'negative_low', 'negative_high'];
  readonly activeTab = signal<CollectionTab>('overview');
  readonly overview = signal<CollectionOverview | null>(null);
  readonly overviewLoading = signal(true);
  readonly participants = signal<DatasetParticipant[]>([]);
  readonly stimuli = signal<EmotionStimulus[]>([]);
  readonly sessions = signal<CollectionSession[]>([]);
  readonly participantsLoading = signal(true);
  readonly stimuliLoading = signal(true);
  readonly sessionsLoading = signal(true);
  readonly error = signal('');
  readonly participantSubmitting = signal(false);
  readonly stimulusSubmitting = signal(false);
  readonly sessionSubmitting = signal(false);

  consentConfirmed = false;
  stimulus = { title: '', file_path: '', checksum: '', duration_seconds: 45, target_quadrant: 'positive_low' as EmotionQuadrant, approval_state: 'draft' as StimulusApprovalState, stimulus_set_version: 'v1' };
  sessionParticipantId: number | null = null;
  deviceId = '';
  deviceName = '';

  ngOnInit(): void { this.loadOverview(); this.loadParticipants(); this.loadStimuli(); this.loadSessions(); }
  switchTab(tab: CollectionTab): void { this.activeTab.set(tab); }
  onTabKeydown(event: KeyboardEvent, current: CollectionTab): void {
    const tabsList = this.tabs();
    const index = tabsList.findIndex((tab) => tab.key === current);
    let next = index;
    if (event.key === 'ArrowRight') next = (index + 1) % tabsList.length;
    else if (event.key === 'ArrowLeft') next = (index - 1 + tabsList.length) % tabsList.length;
    else if (event.key === 'Home') next = 0;
    else if (event.key === 'End') next = tabsList.length - 1;
    else return;
    event.preventDefault();
    const key = tabsList[next].key;
    this.switchTab(key);
    document.getElementById(`collection-tab-${key}`)?.focus();
  }
  activeParticipants(): DatasetParticipant[] { return this.participants().filter((item) => item.state === 'active'); }
  hasActiveParticipant(): boolean { return this.sessionParticipantId !== null && this.activeParticipants().some((item) => item.id === this.sessionParticipantId); }
  isStimulusDurationValid(): boolean { return this.stimulus.duration_seconds >= 45 && this.stimulus.duration_seconds <= 60; }
  isStimulusReady(): boolean { return !!(this.stimulus.title.trim() && this.stimulus.file_path.trim() && this.stimulus.checksum.length === 64 && this.stimulus.stimulus_set_version.trim() && this.isStimulusDurationValid()); }
  sessionActionLabel(item: CollectionSession): string | null {
    if (item.state === 'completed') return 'ดูสรุปผล';
    return ['preparation', 'baseline', 'ready', 'in_progress', 'interrupted'].includes(item.state) ? 'เริ่ม / ดำเนินการต่อ' : null;
  }

  registerParticipant(): void {
    if (!this.consentConfirmed || this.participantSubmitting()) return;
    this.participantSubmitting.set(true); this.error.set('');
    this.api.createParticipant({ consent_confirmed_at: new Date().toISOString() }).subscribe({
      next: (item) => { this.participants.update((items) => [item, ...items]); this.consentConfirmed = false; this.participantSubmitting.set(false); },
      error: (err) => this.fail(err, this.participantSubmitting),
    });
  }

  registerStimulus(): void {
    if (!this.isStimulusReady() || this.stimulusSubmitting()) return;
    this.stimulusSubmitting.set(true); this.error.set('');
    this.api.createStimulus({ ...this.stimulus }).subscribe({
      next: (item) => { this.stimuli.update((items) => [item, ...items]); this.stimulusSubmitting.set(false); },
      error: (err) => this.fail(err, this.stimulusSubmitting),
    });
  }

  createSession(): void {
    if (!this.hasActiveParticipant() || this.sessionParticipantId === null || this.sessionSubmitting()) return;
    this.sessionSubmitting.set(true); this.error.set('');
    this.api.createSession({ participant_id: this.sessionParticipantId, device_id: this.deviceId.trim() || null, device_name: this.deviceName.trim() || null }).subscribe({
      next: (item) => { this.sessions.update((items) => [item, ...items]); this.sessionSubmitting.set(false); },
      error: (err) => this.fail(err, this.sessionSubmitting),
    });
  }

  private loadOverview(): void {
    this.overviewLoading.set(true);
    this.api.getOverview().subscribe({
      next: (value) => { this.overview.set(value); this.overviewLoading.set(false); },
      error: (err) => { this.overviewLoading.set(false); this.fail(err); },
    });
  }
  private loadParticipants(): void { this.participantsLoading.set(true); this.api.listParticipants().subscribe({ next: (value) => { this.participants.set(value.items); this.participantsLoading.set(false); }, error: (err) => { this.participantsLoading.set(false); this.fail(err); } }); }
  private loadStimuli(): void { this.stimuliLoading.set(true); this.api.listStimuli().subscribe({ next: (value) => { this.stimuli.set(value.items); this.stimuliLoading.set(false); }, error: (err) => { this.stimuliLoading.set(false); this.fail(err); } }); }
  private loadSessions(): void { this.sessionsLoading.set(true); this.api.listSessions().subscribe({ next: (value) => { this.sessions.set(value.items); this.sessionsLoading.set(false); }, error: (err) => { this.sessionsLoading.set(false); this.fail(err); } }); }
  private fail(err: unknown, busy?: { set(value: boolean): void }): void {
    busy?.set(false);
    this.error.set(toThaiError(err));
  }
}
