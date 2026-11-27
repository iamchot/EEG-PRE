import { DatePipe } from '@angular/common';
import { Pipe, PipeTransform } from '@angular/core';

@Pipe({
  name: 'thaiDate',
  standalone: true,
})
export class ThaiDatePipe implements PipeTransform {
  private readonly datePipe = new DatePipe('en-US');

  transform(value: string | Date | null | undefined, format = 'dd MMM yyyy HH:mm'): string | null {
    if (!value) return null;
    let normalized: string | Date = value;
    if (typeof value === 'string') {
      const trimmed = value.trim();
      const hasTz = /([zZ]|[+-]\d{2}:?\d{2})$/.test(trimmed);
      normalized = hasTz ? trimmed : `${trimmed}Z`;
    }
    return this.datePipe.transform(normalized, format, '+0700');
  }
}
