import { Component, computed, input, inject } from '@angular/core';
import { SensorStatus, SensorState } from '../../../core/services/eeg-ws.service';
import { LanguageService } from '../../../core/services/language.service';
import { TranslatePipe } from '../../../core/pipes/translate.pipe';

export type SensorKey = 'tp9' | 'af7' | 'af8' | 'tp10';

interface SensorPoint {
  key: SensorKey;
  label: string;
}

const SENSOR_POINTS: SensorPoint[] = [
  { key: 'tp9', label: 'TP9' },
  { key: 'af7', label: 'AF7' },
  { key: 'af8', label: 'AF8' },
  { key: 'tp10', label: 'TP10' },
];

const STATE_ICON: Record<SensorState, string> = {
  unknown: '…',
  poor: '!',
  good: '✓',
  stale: '×',
};

@Component({
  selector: 'app-horseshoe-sensor',
  standalone: true,
  imports: [TranslatePipe],
  templateUrl: './horseshoe-sensor.component.html',
  styleUrl: './horseshoe-sensor.component.css',
})
export class HorseshoeSensorComponent {
  readonly lang = inject(LanguageService);
  readonly tp9 = input<SensorStatus>({ state: 'unknown', quality_score: 0, timestamp: 0, sequence: 0 });
  readonly af7 = input<SensorStatus>({ state: 'unknown', quality_score: 0, timestamp: 0, sequence: 0 });
  readonly af8 = input<SensorStatus>({ state: 'unknown', quality_score: 0, timestamp: 0, sequence: 0 });
  readonly tp10 = input<SensorStatus>({ state: 'unknown', quality_score: 0, timestamp: 0, sequence: 0 });
  readonly sensorPoints = SENSOR_POINTS;

  getSensorData(key: SensorKey): SensorStatus {
    return {
      tp9: this.tp9(),
      af7: this.af7(),
      af8: this.af8(),
      tp10: this.tp10(),
    }[key];
  }

  locationLabel(key: SensorKey): string {
    const map: Record<SensorKey, string> = {
      tp9: this.lang.t('sensor.tp9_label'),
      af7: this.lang.t('sensor.af7_label'),
      af8: this.lang.t('sensor.af8_label'),
      tp10: this.lang.t('sensor.tp10_label'),
    };
    return map[key];
  }

  stateLabel(key: SensorKey): string {
    const state = this.getSensorData(key).state;
    if (state === 'good') return this.lang.currentLang() === 'th' ? 'พร้อม' : 'Good';
    if (state === 'poor') return this.lang.currentLang() === 'th' ? 'ปรับตำแหน่ง' : 'Poor';
    if (state === 'stale') return this.lang.currentLang() === 'th' ? 'ขาดการเชื่อมต่อ' : 'Stale';
    return this.lang.currentLang() === 'th' ? 'รอสัญญาณ' : 'Waiting';
  }

  stateIcon(key: SensorKey): string {
    return STATE_ICON[this.getSensorData(key).state];
  }

  allGood = computed(() =>
    this.sensorPoints.every(({ key }) => this.getSensorData(key).state === 'good')
  );

  allUnknown = computed(() =>
    this.sensorPoints.every(({ key }) => this.getSensorData(key).state === 'unknown')
  );

  attentionCount = computed(() =>
    this.sensorPoints.filter(({ key }) =>
      ['poor', 'stale'].includes(this.getSensorData(key).state)
    ).length
  );

  readinessLabel = computed(() => {
    this.lang.currentLang();
    if (this.allGood()) return this.lang.currentLang() === 'th' ? 'พร้อมเริ่ม' : 'All Good';
    if (this.allUnknown()) return this.lang.currentLang() === 'th' ? 'กำลังรอสัญญาณ' : 'Waiting for Signal';
    const count = this.attentionCount();
    return this.lang.currentLang() === 'th' ? `ปรับเซนเซอร์อีก ${count} จุด` : `Adjust ${count} Sensor(s)`;
  });

  readinessHint = computed(() => {
    this.lang.currentLang();
    return this.allGood()
      ? (this.lang.currentLang() === 'th' ? 'เซนเซอร์ครบทั้ง 4 จุด' : 'All 4 sensors ready')
      : (this.lang.currentLang() === 'th' ? 'ขยับสายคาดตามตำแหน่งด้านล่าง' : 'Adjust headband sensors below');
  });

  currentTip = computed(() => {
    this.lang.currentLang();
    const isTh = this.lang.currentLang() === 'th';
    if (this.tp9().state !== 'good' || this.tp10().state !== 'good') {
      return isTh
        ? 'เปิดผมบริเวณหลังหูซ้ายและขวา ให้เซนเซอร์แตะผิวโดยตรง แล้วขยับสายคาดเล็กน้อย'
        : 'Clear hair behind left and right ears. Ensure sensors touch skin directly.';
    }
    if (this.af7().state !== 'good' || this.af8().state !== 'good') {
      return isTh
        ? 'เช็ดหน้าผากให้แห้ง เปิดผมไม่ให้บัง แล้วเลื่อนเซนเซอร์ด้านหน้าให้แนบผิว'
        : 'Ensure forehead is clean and free of hair. Press headband firmly against skin.';
    }
    return isTh
      ? 'สัญญาณพร้อมแล้ว รักษาตำแหน่ง Muse 2 ไว้แบบนี้'
      : 'All 4 sensors ready. Maintain headband position.';
  });
}
