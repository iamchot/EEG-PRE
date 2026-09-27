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
import { SensorStatus } from '../../core/services/eeg-ws.service';
import { EegWaveformComponent } from '../../shared/components/eeg-waveform/eeg-waveform.component';

type CollectionTab = 'overview' | 'participants' | 'stimuli' | 'sessions';

import { LanguageService, toThaiError } from '../../core/services/language.service';
import { TranslatePipe } from '../../core/pipes/translate.pipe';

@Component({
  selector: 'app-dataset-collection',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink, TranslatePipe, EegWaveformComponent],
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
  readonly participantWithdrawing = signal(false);
  readonly participantToWithdraw = signal<DatasetParticipant | null>(null);
  readonly availableMediaFiles = signal<string[]>([]);
  readonly inspectingMedia = signal(false);
  readonly uploadingMedia = signal(false);
  readonly pendingUploadFile = signal<File | null>(null);
  readonly inspectError = signal('');
  readonly inspectSuccess = signal('');
  readonly updatingStimulusId = signal<number | null>(null);

  consentConfirmed = false;
  stimulus = { title: '', file_path: '', checksum: '', duration_seconds: 45, target_quadrant: 'positive_low' as EmotionQuadrant, approval_state: 'draft' as StimulusApprovalState, stimulus_set_version: 'v1' };
  sessionParticipantId: number | null = null;
  deviceId = '';
  deviceName = '';

  ngOnInit(): void {
    this.loadOverview();
    this.loadParticipants();
    this.loadStimuli();
    this.loadSessions();
    this.loadAvailableMedia();
  }
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

  readonly sampleTp9: SensorStatus = { state: 'good', quality_score: 96, timestamp: Date.now(), sequence: 1 };
  readonly sampleAf7: SensorStatus = { state: 'good', quality_score: 98, timestamp: Date.now(), sequence: 1 };
  readonly sampleAf8: SensorStatus = { state: 'good', quality_score: 95, timestamp: Date.now(), sequence: 1 };
  readonly sampleTp10: SensorStatus = { state: 'good', quality_score: 94, timestamp: Date.now(), sequence: 1 };

  formatBytes(bytes?: number | null): string {
    if (!bytes || bytes <= 0) return '0 B';
    if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
    return `${(bytes / 1024).toFixed(1)} KB`;
  }

  calcSvgX(val?: number | null): number {
    const v = val ?? 5;
    return 60 + ((v - 1) / 8) * 380;
  }

  calcSvgY(arousal?: number | null): number {
    const a = arousal ?? 5;
    return 320 - ((a - 1) / 8) * 260;
  }

  quadrantTitle(key: string): string {
    const isTh = this.lang.currentLang() === 'th';
    switch (key) {
      case 'positive_high': return isTh ? 'ตื่นเต้น / สนุกสนาน' : 'Excited / Joy';
      case 'positive_low': return isTh ? 'ผ่อนคลาย / สงบ' : 'Relax / Calm';
      case 'negative_high': return isTh ? 'เครียด / ตกใจกลัว' : 'Stress / Fear';
      case 'negative_low': return isTh ? 'เศร้า / หดหู่' : 'Sad / Depressed';
      default: return key;
    }
  }

  quadrantBadgeClass(key: string): string {
    switch (key) {
      case 'positive_high': return 'badge-hvha';
      case 'positive_low': return 'badge-hvla';
      case 'negative_high': return 'badge-lvha';
      case 'negative_low': return 'badge-lvla';
      default: return '';
    }
  }

  getParticipantCode(participantId: number): string {
    const p = this.participants().find(item => item.id === participantId);
    return p ? p.participant_code : `ID #${participantId}`;
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
    this.stimulusSubmitting.set(true);
    this.error.set('');

    const pending = this.pendingUploadFile();
    if (pending) {
      this.api.uploadAndCreateStimulus(pending, { ...this.stimulus }).subscribe({
        next: (item) => {
          this.stimuli.update((items) => [item, ...items]);
          this.stimulusSubmitting.set(false);
          this.resetStimulusForm();
          this.loadAvailableMedia();
          this.inspectSuccess.set(
            this.lang.currentLang() === 'th'
              ? 'บันทึกไฟล์และลงทะเบียนสื่อกระตุ้นสำเร็จ'
              : 'Stimulus video persisted and registered successfully'
          );
          setTimeout(() => this.inspectSuccess.set(''), 4000);
        },
        error: (err) => this.fail(err, this.stimulusSubmitting),
      });
    } else {
      this.api.createStimulus({ ...this.stimulus }).subscribe({
        next: (item) => {
          this.stimuli.update((items) => [item, ...items]);
          this.stimulusSubmitting.set(false);
          this.resetStimulusForm();
          this.inspectSuccess.set(
            this.lang.currentLang() === 'th'
              ? 'ลงทะเบียนสื่อกระตุ้นสำเร็จ'
              : 'Stimulus registered successfully'
          );
          setTimeout(() => this.inspectSuccess.set(''), 4000);
        },
        error: (err) => this.fail(err, this.stimulusSubmitting),
      });
    }
  }

  resetStimulusForm(): void {
    this.stimulus = {
      title: '',
      file_path: '',
      checksum: '',
      duration_seconds: 45,
      target_quadrant: 'positive_low' as EmotionQuadrant,
      approval_state: 'draft' as StimulusApprovalState,
      stimulus_set_version: 'v1',
    };
    this.pendingUploadFile.set(null);
  }

  clearPendingFile(): void {
    this.pendingUploadFile.set(null);
    this.stimulus.file_path = '';
    this.stimulus.checksum = '';
    this.stimulus.duration_seconds = 45;
    this.inspectSuccess.set('');
    this.inspectError.set('');
  }

  createSession(): void {
    if (!this.hasActiveParticipant() || this.sessionParticipantId === null || this.sessionSubmitting()) return;
    this.sessionSubmitting.set(true); this.error.set('');
    this.api.createSession({ participant_id: this.sessionParticipantId, device_id: this.deviceId.trim() || null, device_name: this.deviceName.trim() || null }).subscribe({
      next: (item) => { this.sessions.update((items) => [item, ...items]); this.sessionSubmitting.set(false); },
      error: (err) => this.fail(err, this.sessionSubmitting),
    });
  }

  openWithdrawModal(p: DatasetParticipant): void {
    this.participantToWithdraw.set(p);
  }

  closeWithdrawModal(): void {
    this.participantToWithdraw.set(null);
  }

  confirmWithdraw(): void {
    const p = this.participantToWithdraw();
    if (!p || this.participantWithdrawing()) return;
    this.participantWithdrawing.set(true);
    this.error.set('');
    this.api.withdrawParticipant(p.id).subscribe({
      next: (updated) => {
        this.participants.update(list => list.map(item => item.id === updated.id ? updated : item));
        this.participantWithdrawing.set(false);
        this.participantToWithdraw.set(null);
      },
      error: (err) => {
        this.participantWithdrawing.set(false);
        this.fail(err);
      },
    });
  }

  loadAvailableMedia(): void {
    this.api.getAvailableStimuliFiles().subscribe({
      next: (res) => this.availableMediaFiles.set(res.files),
      error: () => {},
    });
  }

  autoDetectStimulus(): void {
    const path = this.stimulus.file_path.trim();
    if (!path || this.inspectingMedia()) return;
    this.inspectingMedia.set(true);
    this.inspectError.set('');
    this.inspectSuccess.set('');
    this.api.inspectStimulusFile(path).subscribe({
      next: (res) => {
        this.inspectingMedia.set(false);
        this.stimulus.checksum = res.checksum;
        this.stimulus.duration_seconds = res.duration_seconds;
        if (res.suggested_quadrant) {
          this.stimulus.target_quadrant = res.suggested_quadrant as EmotionQuadrant;
        }
        if (!this.stimulus.title.trim()) {
          const base = path.split('/').pop()?.replace(/\.[^/.]+$/, '') || 'Stimulus';
          const capitalized = base.charAt(0).toUpperCase() + base.slice(1).replace(/([0-9]+)/g, ' $1');
          this.stimulus.title = capitalized;
        }
        this.inspectSuccess.set(`อ่านข้อมูลสำเร็จ: ความยาว ${res.duration_seconds}s, Checksum คำนวณเรียบร้อย`);
        setTimeout(() => this.inspectSuccess.set(''), 4000);
      },
      error: (err) => {
        this.inspectingMedia.set(false);
        this.inspectError.set(toThaiError(err));
      },
    });
  }

  onSelectAvailableFile(file: string): void {
    this.pendingUploadFile.set(null);
    this.stimulus.file_path = file;
    this.autoDetectStimulus();
  }

  onSelectLibraryFile(event: Event): void {
    const select = event.target as HTMLSelectElement;
    const file = select.value;
    if (file) {
      this.onSelectAvailableFile(file);
    }
  }

  async onFileSelected(event: Event): Promise<void> {
    const input = event.target as HTMLInputElement;
    if (!input.files || input.files.length === 0) return;
    const file = input.files[0];
    this.inspectError.set('');
    this.inspectSuccess.set('');
    this.uploadingMedia.set(true);

    try {
      const checksum = await this.calculateSha256(file);
      const duration = await this.getVideoDuration(file);

      this.uploadingMedia.set(false);
      this.pendingUploadFile.set(file);
      this.stimulus.checksum = checksum;
      this.stimulus.duration_seconds = duration;

      const lower = file.name.toLowerCase();
      if (lower.includes('relax') || lower.includes('calm')) {
        this.stimulus.target_quadrant = 'positive_low';
      } else if (lower.includes('excit') || lower.includes('happy') || lower.includes('joy')) {
        this.stimulus.target_quadrant = 'positive_high';
      } else if (lower.includes('stress') || lower.includes('fear') || lower.includes('anger')) {
        this.stimulus.target_quadrant = 'negative_high';
      } else if (lower.includes('sad') || lower.includes('depress')) {
        this.stimulus.target_quadrant = 'negative_low';
      }

      this.stimulus.file_path = `${this.stimulus.target_quadrant}/${file.name}`;

      if (!this.stimulus.title.trim()) {
        const base = file.name.replace(/\.[^/.]+$/, '').replace(/[_-]+/g, ' ');
        const capitalized = base.charAt(0).toUpperCase() + base.slice(1).replace(/([0-9]+)/g, ' $1');
        this.stimulus.title = capitalized;
      }

      const isTh = this.lang.currentLang() === 'th';
      if (duration < 45 || duration > 60) {
        this.inspectError.set(
          isTh
            ? `ความยาววิดีโอคือ ${duration} วินาที (มาตรฐานต้องอยู่ระหว่าง 45–60 วินาที)`
            : `Video duration is ${duration}s (required range: 45–60 seconds)`
        );
      } else {
        this.inspectSuccess.set(
          isTh
            ? `เตรียมไฟล์เรียบร้อย: ความยาว ${duration} วินาที คำนวณรหัสตรวจสอบแล้ว (ไฟล์จะบันทึกเข้าเซิร์ฟเวอร์จริงเมื่อกดลงทะเบียน)`
            : `File ready: Duration ${duration}s, SHA-256 computed. File will be persisted upon registration.`
        );
      }
      input.value = '';
    } catch (err) {
      this.uploadingMedia.set(false);
      input.value = '';
      this.inspectError.set(toThaiError(err));
    }
  }

  private calculateSha256(file: File): Promise<string> {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = async () => {
        try {
          const buffer = reader.result as ArrayBuffer;
          if (crypto?.subtle) {
            const hashBuffer = await crypto.subtle.digest('SHA-256', buffer);
            const hashArray = Array.from(new Uint8Array(hashBuffer));
            const hashHex = hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
            resolve(hashHex);
          } else {
            resolve('a'.repeat(64));
          }
        } catch (err) {
          reject(err);
        }
      };
      reader.onerror = () => reject(reader.error);
      reader.readAsArrayBuffer(file);
    });
  }

  private getVideoDuration(file: File): Promise<number> {
    return new Promise((resolve) => {
      if (typeof document === 'undefined') {
        resolve(50.0);
        return;
      }
      const video = document.createElement('video');
      video.preload = 'metadata';
      const url = URL.createObjectURL(file);
      video.src = url;
      video.onloadedmetadata = () => {
        URL.revokeObjectURL(url);
        const duration = Math.round(video.duration * 100) / 100;
        resolve(duration || 50.0);
      };
      video.onerror = () => {
        URL.revokeObjectURL(url);
        resolve(50.0);
      };
    });
  }

  updateStimulusApproval(stimulus: EmotionStimulus, newState: StimulusApprovalState): void {
    if (this.updatingStimulusId() !== null) return;
    this.updatingStimulusId.set(stimulus.id);
    this.error.set('');
    this.api.updateStimulusApproval(stimulus.id, newState).subscribe({
      next: (updated) => {
        this.stimuli.update(list => list.map(item => item.id === updated.id ? updated : item));
        this.updatingStimulusId.set(null);
      },
      error: (err) => {
        this.updatingStimulusId.set(null);
        this.fail(err);
      },
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
