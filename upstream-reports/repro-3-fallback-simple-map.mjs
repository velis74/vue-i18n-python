// Reproduces: fallbackWithSimple reads a map fallbackLocale's keys instead of its values.
// Run from the repo root:  node upstream-reports/repro-3-fallback-simple-map.mjs
import { fallbackWithSimple, fallbackWithLocaleChain } from '@intlify/core-base';
import { createRequire } from 'node:module';
console.log('@intlify/core-base', createRequire(import.meta.url)('@intlify/core-base/package.json').version);

const fallback = { 'sl-SI': ['sl', 'en'], sl: ['en'], default: ['en'] };

console.log('\nfallbackLocale =', JSON.stringify(fallback), '\n');
for (const start of ['sl-SI', 'sl', 'de']) {
  console.log(
    ` start=${start.padEnd(6)}`,
    'simple:', JSON.stringify(fallbackWithSimple({}, fallback, start)).padEnd(34),
    'chain:', JSON.stringify(fallbackWithLocaleChain({}, fallback, start)),
  );
}

console.log('\n`simple` returns the literal string "default" as if it were a locale, pulls in');
console.log('unrelated locales when starting from one the map does not mention, and never returns');
console.log('`en` - the locale the configuration actually names. `chain` gets all three right.');
