import { CommonModule } from '@angular/common';
import {
  Component,
  ElementRef,
  EventEmitter,
  HostListener,
  Input,
  Output,
  forwardRef,
  inject,
  signal,
} from '@angular/core';
import { ControlValueAccessor, NG_VALUE_ACCESSOR } from '@angular/forms';

export interface AppSelectOption<T = unknown> {
  value: T;
  label: string;
}

@Component({
  selector: 'app-select',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './app-select.component.html',
  styleUrl: './app-select.component.css',
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => AppSelectComponent),
      multi: true,
    },
  ],
})
export class AppSelectComponent implements ControlValueAccessor {
  private readonly hostEl = inject(ElementRef<HTMLElement>);

  @Input() options: AppSelectOption<any>[] = [];
  @Input() placeholder = '';
  @Input() emptyText = '';
  @Input() inputId = '';
  @Input() disabled = false;

  @Input()
  set value(val: unknown) {
    this.currentValue.set(val);
  }
  get value(): unknown {
    return this.currentValue();
  }

  @Output() valueChange = new EventEmitter<any>();

  readonly isOpen = signal(false);
  readonly currentValue = signal<unknown>(null);

  private onChange: (val: unknown) => void = () => {};
  private onTouched: () => void = () => {};

  writeValue(val: unknown): void {
    this.currentValue.set(val);
  }

  registerOnChange(fn: (val: unknown) => void): void {
    this.onChange = fn;
  }

  registerOnTouched(fn: () => void): void {
    this.onTouched = fn;
  }

  setDisabledState(isDisabled: boolean): void {
    this.disabled = isDisabled;
  }

  toggle(event: Event): void {
    event.stopPropagation();
    if (this.disabled) return;
    this.isOpen.update((open) => !open);
  }

  selectOption(val: unknown): void {
    if (this.disabled) return;
    this.currentValue.set(val);
    this.onChange(val);
    this.onTouched();
    this.valueChange.emit(val);
    this.isOpen.set(false);
  }

  isSelected(val: unknown): boolean {
    return this.currentValue() === val;
  }

  selectedLabel(): string {
    const val = this.currentValue();
    const match = this.options.find((opt) => opt.value === val);
    if (match) return match.label;
    return this.placeholder || (this.options[0]?.label ?? '');
  }

  hasSelection(): boolean {
    const val = this.currentValue();
    return val !== null && val !== undefined && val !== '';
  }

  @HostListener('document:click', ['$event'])
  onDocumentClick(event: Event): void {
    const target = event.target as HTMLElement | null;
    if (!target || !this.hostEl.nativeElement.contains(target)) {
      this.isOpen.set(false);
    }
  }

  @HostListener('keydown.escape')
  onEscape(): void {
    this.isOpen.set(false);
  }
}
