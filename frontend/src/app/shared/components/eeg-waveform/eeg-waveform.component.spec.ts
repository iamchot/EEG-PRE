import { ComponentFixture, TestBed } from '@angular/core/testing';
import { EegWaveformComponent } from './eeg-waveform.component';

describe('EegWaveformComponent', () => {
  let component: EegWaveformComponent;
  let fixture: ComponentFixture<EegWaveformComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [EegWaveformComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(EegWaveformComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('should render waveform canvas', () => {
    const canvas = fixture.nativeElement.querySelector('canvas');
    expect(canvas).toBeTruthy();
  });

  it('should calculate average quality correctly', () => {
    expect(component.averageQuality()).toBe(0);
  });
});
