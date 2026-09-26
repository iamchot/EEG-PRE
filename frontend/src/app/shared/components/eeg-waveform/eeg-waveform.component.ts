import {
  AfterViewInit,
  Component,
  ElementRef,
  OnDestroy,
  ViewChild,
  computed,
  effect,
  input,
} from '@angular/core';
import { SensorStatus } from '../../../core/services/eeg-ws.service';

interface ChannelConfig {
  key: 'tp9' | 'af7' | 'af8' | 'tp10';
  label: string;
  color: string;
  offsetY: number;
}

const CHANNELS: ChannelConfig[] = [
  { key: 'tp9', label: 'TP9', color: '#a855f7', offsetY: 0.18 },
  { key: 'af7', label: 'AF7', color: '#06b6d4', offsetY: 0.39 },
  { key: 'af8', label: 'AF8', color: '#10b981', offsetY: 0.60 },
  { key: 'tp10', label: 'TP10', color: '#f59e0b', offsetY: 0.81 },
];

@Component({
  selector: 'app-eeg-waveform',
  standalone: true,
  templateUrl: './eeg-waveform.component.html',
  styleUrl: './eeg-waveform.component.css',
})
export class EegWaveformComponent implements AfterViewInit, OnDestroy {
  @ViewChild('waveformCanvas') canvasRef!: ElementRef<HTMLCanvasElement>;

  readonly tp9 = input<SensorStatus>({ state: 'unknown', quality_score: 0, timestamp: 0, sequence: 0 });
  readonly af7 = input<SensorStatus>({ state: 'unknown', quality_score: 0, timestamp: 0, sequence: 0 });
  readonly af8 = input<SensorStatus>({ state: 'unknown', quality_score: 0, timestamp: 0, sequence: 0 });
  readonly tp10 = input<SensorStatus>({ state: 'unknown', quality_score: 0, timestamp: 0, sequence: 0 });
  readonly isConnected = input<boolean>(false);

  readonly channels = CHANNELS;

  private animationFrameId: number | null = null;
  private bufferSize = 400;
  private channelBuffers: Record<string, number[]> = {
    tp9: new Array(400).fill(0),
    af7: new Array(400).fill(0),
    af8: new Array(400).fill(0),
    tp10: new Array(400).fill(0),
  };
  private phaseOffsets: Record<string, number> = {
    tp9: 0,
    af7: 0.8,
    af8: 1.6,
    tp10: 2.4,
  };

  readonly averageQuality = computed(() => {
    const scores = [this.tp9().quality_score, this.af7().quality_score, this.af8().quality_score, this.tp10().quality_score];
    const avg = scores.reduce((a, b) => a + b, 0) / (scores.length || 1);
    return Math.round(avg * 100);
  });

  readonly hasArtifact = computed(() => {
    const s = [this.tp9(), this.af7(), this.af8(), this.tp10()];
    return s.some(item => item.state === 'poor');
  });

  constructor() {
    effect(() => {
      this.updateBuffersWithNewData();
    });
  }

  ngAfterViewInit(): void {
    this.startRendering();
  }

  ngOnDestroy(): void {
    if (this.animationFrameId !== null) {
      cancelAnimationFrame(this.animationFrameId);
      this.animationFrameId = null;
    }
  }

  private updateBuffersWithNewData(): void {
    const sensors = { tp9: this.tp9(), af7: this.af7(), af8: this.af8(), tp10: this.tp10() };
    const connected = this.isConnected();

    CHANNELS.forEach(ch => {
      const status = sensors[ch.key];
      const buf = this.channelBuffers[ch.key];
      buf.shift();

      let val = 0;
      if (connected && status.state !== 'unknown') {
        const time = Date.now() / 1000;
        const baseFreq = ch.key.startsWith('af') ? 10 : 8; // Alpha/Beta frequency simulation
        const phase = this.phaseOffsets[ch.key];
        
        // Base sine wave
        val = Math.sin(time * baseFreq * 2 * Math.PI + phase) * 12;
        // Secondary harmonic
        val += Math.cos(time * (baseFreq * 1.5) * Math.PI) * 6;

        // Artifact spike if poor status (blink / muscle movement)
        if (status.state === 'poor') {
          const spikeChance = Math.random();
          if (spikeChance > 0.8) {
            val += (Math.random() - 0.5) * 45;
          }
        }
      } else {
        // Subtle noise when idle
        val = (Math.random() - 0.5) * 3;
      }

      buf.push(val);
    });
  }

  private startRendering(): void {
    const canvas = this.canvasRef?.nativeElement;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const render = () => {
      const rect = canvas.getBoundingClientRect();
      if (canvas.width !== rect.width || canvas.height !== rect.height) {
        canvas.width = rect.width || 600;
        canvas.height = rect.height || 180;
      }

      ctx.clearRect(0, 0, canvas.width, canvas.height);

      const width = canvas.width;
      const height = canvas.height;

      // Draw each channel waveform trace
      CHANNELS.forEach(ch => {
        const buf = this.channelBuffers[ch.key];
        const centerY = height * ch.offsetY;

        // Channel baseline
        ctx.beginPath();
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.05)';
        ctx.lineWidth = 1;
        ctx.moveTo(0, centerY);
        ctx.lineTo(width, centerY);
        ctx.stroke();

        // Waveform trace
        ctx.beginPath();
        ctx.strokeStyle = ch.color;
        ctx.lineWidth = 1.8;
        ctx.shadowColor = ch.color;
        ctx.shadowBlur = this.isConnected() ? 8 : 2;

        const stepX = width / (buf.length - 1);
        for (let i = 0; i < buf.length; i++) {
          const x = i * stepX;
          const y = centerY - buf[i];
          if (i === 0) {
            ctx.moveTo(x, y);
          } else {
            ctx.lineTo(x, y);
          }
        }
        ctx.stroke();

        // Reset shadow for next operations
        ctx.shadowBlur = 0;
      });

      this.animationFrameId = requestAnimationFrame(render);
    };

    render();
  }
}
