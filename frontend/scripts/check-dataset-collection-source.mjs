import { readFileSync } from 'node:fs';
import { strict as assert } from 'node:assert';

const source = readFileSync(new URL('../src/app/features/dataset-collection/dataset-collection.component.ts', import.meta.url), 'utf8');
assert.match(source, /styleUrl:\s*['"]\.\/dataset-collection\.component\.css['"]/);
assert.doesNotMatch(source, /\bstyles\s*:/);
console.log('Dataset collection source metadata check passed.');
