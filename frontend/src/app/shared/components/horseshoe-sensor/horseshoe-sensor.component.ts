import { Component, computed, input } from '@angular/core';
import { SensorStatus, SensorState } from '../../../core/services/eeg-ws.service';

export type SensorKey = 'tp9' | 'af7' | 'af8' | 'tp10';

interface SensorPoint {
  key: SensorKey;
  label: string;
  location: string;
}

const SENSOR_POINTS: SensorPoint[] = [
  { key: 'tp9', label: 'TP9', location: 'หลังหูซ้าย' },
  { key: 'af7', label: 'AF7', location: 'หน้าผากซ้าย' },
  { key: 'af8', label: 'AF8', location: 'หน้าผากขวา' },
  { key: 'tp10', label: 'TP10', location: 'หลังหูขวา' },
];

const STATE_LABEL: Record<SensorState, string> = {
  unknown: 'รอสัญญาณ',
  poor: 'ปรับตำแหน่ง',
  good: 'พร้อม',
  stale: 'ขาดการเชื่อมต่อ',
};

const STATE_ICON: Record<SensorState, string> = {
  unknown: '…',
  poor: '!',
  good: '✓',
  stale: '×',
};

@Component({
  selector: 'app-horseshoe-sensor',
  standalone: true,
  template: `
    <section class="sensor-panel" aria-labelledby="sensor-title">
      <header class="sensor-heading">
        <p class="section-kicker">สถานะการสวมใส่</p>
        <h2 id="sensor-title">Muse 2 ของคุณ</h2>
        <p>ตรวจให้เซนเซอร์ทั้ง 4 จุดแนบสนิทก่อนเริ่มบันทึก</p>
      </header>

      <div class="headset-figure" role="img" aria-label="ตำแหน่งเซนเซอร์ Muse 2 ได้แก่ TP9 AF7 AF8 และ TP10">
        <svg viewBox="0 0 360 220" aria-hidden="true" focusable="false">
          <path class="head-outline" d="M116 170 C118 92 145 54 180 54 C215 54 242 92 244 170" />
          <path class="headband" d="M64 160 C80 47 280 47 296 160" />
          @for (pt of sensorPoints; track pt.key) {
            <g [attr.class]="'sensor-node node-' + getSensorData(pt.key).state">
              <circle
                [attr.cx]="pt.key === 'tp9' ? 64 : pt.key === 'af7' ? 139 : pt.key === 'af8' ? 221 : 296"
                [attr.cy]="pt.key === 'tp9' || pt.key === 'tp10' ? 160 : 68"
                r="18"
              />
              <text
                [attr.x]="pt.key === 'tp9' ? 64 : pt.key === 'af7' ? 139 : pt.key === 'af8' ? 221 : 296"
                [attr.y]="pt.key === 'tp9' || pt.key === 'tp10' ? 165 : 73"
              >{{ stateIcon(pt.key) }}</text>
            </g>
          }
        </svg>
      </div>

      <div class="readiness" [class.ready]="allGood()" aria-live="polite">
        <span class="readiness-icon">{{ allGood() ? '✓' : '•' }}</span>
        <div>
          <strong>{{ readinessLabel() }}</strong>
          <span>{{ allGood() ? 'เซนเซอร์ครบทั้ง 4 จุด' : 'ขยับสายคาดตามตำแหน่งด้านล่าง' }}</span>
        </div>
      </div>

      <div class="sensor-list">
        @for (pt of sensorPoints; track pt.key) {
          <div class="sensor-row" [attr.data-state]="getSensorData(pt.key).state">
            <span class="state-mark" aria-hidden="true">{{ stateIcon(pt.key) }}</span>
            <div class="sensor-name">
              <strong>{{ pt.label }}</strong>
              <span>{{ pt.location }}</span>
            </div>
            <span class="state-label">{{ stateLabel(pt.key) }}</span>
          </div>
        }
      </div>

      @if (!allGood()) {
        <div class="signal-tip" role="status">
          <strong>ลองปรับแบบนี้</strong>
          <p>{{ currentTip() }}</p>
        </div>
      }
    </section>
  `,
  styleUrl: './horseshoe-sensor.component.css',
})
export class HorseshoeSensorComponent {
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

  stateLabel(key: SensorKey): string {
    return STATE_LABEL[this.getSensorData(key).state];
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
    if (this.allGood()) return 'พร้อมเริ่ม';
    if (this.allUnknown()) return 'กำลังรอสัญญาณ';
    const count = this.attentionCount();
    return count > 0 ? `ปรับเซนเซอร์อีก ${count} จุด` : 'กำลังตรวจสัญญาณ';
  });

  currentTip(): string {
    if (this.tp9().state !== 'good' || this.tp10().state !== 'good') {
      return 'เปิดผมบริเวณหลังหูซ้ายและขวา ให้เซนเซอร์แตะผิวโดยตรง แล้วขยับสายคาดเล็กน้อย';
    }
    if (this.af7().state !== 'good' || this.af8().state !== 'good') {
      return 'เช็ดหน้าผากให้แห้ง เปิดผมไม่ให้บัง แล้วเลื่อนเซนเซอร์ด้านหน้าให้แนบผิว';
    }
    return 'สัญญาณพร้อมแล้ว รักษาตำแหน่ง Muse 2 ไว้แบบนี้';
  }
}
