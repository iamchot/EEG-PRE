import { Pipe, PipeTransform, inject } from '@angular/core';
import { LanguageService } from '../services/language.service';

@Pipe({
  name: 'translate',
  standalone: true,
  pure: false,
})
export class TranslatePipe implements PipeTransform {
  private readonly lang = inject(LanguageService);

  transform(key: string): string {
    // Touch currentLang signal so template tracks reactive dependency
    this.lang.currentLang();
    return this.lang.translate(key);
  }
}
