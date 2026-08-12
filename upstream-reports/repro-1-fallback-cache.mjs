// Reproduces: fallbackWithLocaleChain caches by start locale only.
// Run from the repo root:  node upstream-reports/repro-1-fallback-cache.mjs
import { fallbackWithLocaleChain } from '@intlify/core-base';
import { createRequire } from 'node:module';
console.log('@intlify/core-base', createRequire(import.meta.url)('@intlify/core-base/package.json').version);

const ctx = {};
console.log('1st call, fallback {sl:["en"]}       ->', fallbackWithLocaleChain(ctx, { sl: ['en'], default: ['en'] }, 'sl'));
console.log('2nd call, fallback {sl:["de","hr"]}  ->', fallbackWithLocaleChain(ctx, { sl: ['de', 'hr'], default: ['de'] }, 'sl'));
console.log('fresh ctx, same 2nd fallback         ->', fallbackWithLocaleChain({}, { sl: ['de', 'hr'], default: ['de'] }, 'sl'));
console.log('\nThe 2nd line should equal the 3rd. It equals the 1st instead.');
