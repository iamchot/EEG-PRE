import { ComponentFixture, TestBed } from '@angular/core/testing';
import { HorseshoeSensorComponent } from './horseshoe-sensor.component';
import { SensorState, SensorStatus } from '../../../core/services/eeg-ws.service';

import { LanguageService } from '../../../core/services/language.service';

const sensor = (state: SensorState): SensorStatus => ({
  state,
  quality_score: state === 'good' ? 100 : 0,
  timestamp: 0,
  sequence: 0,
});

describe('HorseshoeSensorComponent', () => {
  let fixture: ComponentFixture<HorseshoeSensorComponent>;
  let component: HorseshoeSensorComponent;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [HorseshoeSensorComponent],
    }).compileComponents();

    TestBed.inject(LanguageService).setLanguage('th');
    fixture = TestBed.createComponent(HorseshoeSensorComponent);
    component = fixture.componentInstance;
  });

  function setStates(states: [SensorState, SensorState, SensorState, SensorState]) {
    fixture.componentRef.setInput('tp9', sensor(states[0]));
    fixture.componentRef.setInput('af7', sensor(states[1]));
    fixture.componentRef.setInput('af8', sensor(states[2]));
    fixture.componentRef.setInput('tp10', sensor(states[3]));
    fixture.detectChanges();
  }

  it('renders all four sensor identifiers and Thai locations', () => {
    setStates(['unknown', 'unknown', 'unknown', 'unknown']);
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';

    expect(text).toContain('TP9');
    expect(text).toContain('หลังหูซ้าย');
    expect(text).toContain('AF7');
    expect(text).toContain('หน้าผากซ้าย');
    expect(text).toContain('AF8');
    expect(text).toContain('หน้าผากขวา');
    expect(text).toContain('TP10');
    expect(text).toContain('หลังหูขวา');
  });

  it('uses Thai text and an icon for each sensor state', () => {
    setStates(['unknown', 'poor', 'good', 'stale']);
    const text = (fixture.nativeElement as HTMLElement).textContent ?? '';

    expect(text).toContain('รอสัญญาณ');
    expect(text).toContain('ปรับตำแหน่ง');
    expect(text).toContain('พร้อม');
    expect(text).toContain('ขาดการเชื่อมต่อ');
    expect(text).toContain('…');
    expect(text).toContain('!');
    expect(text).toContain('✓');
    expect(text).toContain('×');
  });

  it('summarizes unknown, attention, and ready states without a quality percentage', () => {
    setStates(['unknown', 'unknown', 'unknown', 'unknown']);
    expect(component.readinessLabel()).toBe('กำลังรอสัญญาณ');

    setStates(['good', 'poor', 'good', 'stale']);
    expect(component.readinessLabel()).toBe('ปรับเซนเซอร์อีก 2 จุด');

    setStates(['good', 'good', 'good', 'good']);
    expect(component.readinessLabel()).toBe('พร้อมเริ่ม');
    expect((fixture.nativeElement as HTMLElement).textContent).not.toContain('%');
  });

  it('uses an accessible headset figure label', () => {
    setStates(['good', 'good', 'good', 'good']);
    const figure = (fixture.nativeElement as HTMLElement).querySelector('[role="img"]');
    expect(figure?.getAttribute('aria-label')).toBe('ตำแหน่งเซนเซอร์ Muse 2 ได้แก่ TP9 AF7 AF8 และ TP10');
  });

  it('suggests adjusting hair and contact behind the ears when a rear sensor needs attention', () => {
    setStates(['poor', 'good', 'good', 'good']);
    expect(component.currentTip()).toBe(
      'เปิดผมบริเวณหลังหูซ้ายและขวา ให้เซนเซอร์แตะผิวโดยตรง แล้วขยับสายคาดเล็กน้อย'
    );
  });

  it('suggests cleaning and repositioning the forehead sensors when they need attention', () => {
    setStates(['good', 'poor', 'stale', 'good']);
    expect(component.currentTip()).toBe(
      'เช็ดหน้าผากให้แห้ง เปิดผมไม่ให้บัง แล้วเลื่อนเซนเซอร์ด้านหน้าให้แนบผิว'
    );
  });

  it('uses the all-good fallback tip', () => {
    setStates(['good', 'good', 'good', 'good']);
    expect(component.currentTip()).toBe('สัญญาณพร้อมแล้ว รักษาตำแหน่ง Muse 2 ไว้แบบนี้');
  });
});
