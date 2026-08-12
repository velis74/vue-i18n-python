// Regenerates conformance/fallback.json by running upstream's own fallbacker.
//
//   ./scripts/conformance/bundle-upstream.sh
//   node scripts/conformance/generate_fallback_corpus.mjs
//
// One case is one (start locale, fallbackLocale option) pair, recording what `fallbackWithSimple`
// and `fallbackWithLocaleChain` return.
//
// A trap worth knowing about, because an earlier version of this corpus fell into it: the
// `fallback` value must be written to the corpus as the generator's own literal, NOT re-serialised
// from the object JavaScript parsed. `Object.keys` reorders canonical array-index keys ahead of
// string keys, so a round trip through JS bakes that reordering into the fixture - and the Python
// runner then reads the already-reordered version and agrees with itself by construction. Key order
// is exactly one of the things this corpus is supposed to pin, so the cases below are emitted from
// `structuredClone` of the source literal rather than from anything upstream touched.

import { readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
import { fallbackWithSimple, fallbackWithLocaleChain } from './upstream-bundle/upstream_fallback.mjs';

const here = import.meta.url;
const OUT = resolve(dirname(fileURLToPath(here)), '../../conformance/fallback.json');
const version = readFileSync(new URL('./upstream-bundle/version.txt', here), 'utf8').trim();

// Realistic starts: what a browser actually reports, plus the tags this project's own users have.
const STARTS = [
  'en-US', 'en', 'sl-SI', 'sl', 'de-AT', 'hr', 'sr-Latn-RS', 'hu', 'it', 'bs',
  'zh-Hant-TW', 'pt-BR', 'xx-YY', 'und', '', 'en!', 'sl-SI!',
];

// Realistic fallbackLocale shapes: the false/undefined defaults, a plain string, an array, and the
// map form with a `default` key, which is how a multi-language app usually spells it.
const FALLBACKS = [
  false,
  undefined,
  'en',
  'sl',
  ['en'],
  ['sl', 'en'],
  ['hr', 'sr', 'en'],
  { 'sl-SI': ['sl', 'en'], default: ['en'] },
  { 'de-AT': ['de', 'en'], 'sl-SI': ['sl'], default: ['en'] },
  { 'sr-Latn-RS': ['sr', 'hr'], default: ['en'] },
  { default: ['en'] },
  { 'en-US': ['en'] },
  // A block that stops rather than continuing to `default`.
  { 'sl-SI': ['sl!'], default: ['en'] },
  // The same terminator in the array form.
  ['sl!', 'en'],
  // A block whose entry itself has a block: the chain has to follow through two levels, which is
  // how a regional -> language -> lingua-franca setup is actually written.
  { 'sl-SI': ['sl'], sl: ['hr', 'en'], default: ['en'] },
  // Self-reference and a two-node cycle: both must terminate.
  { en: ['en'], default: ['en'] },
  { a: ['b'], b: ['a'], default: ['en'] },
  // A locale named like an Object.prototype member, which JavaScript answers from the prototype
  // chain. This is the case that first exposed the port emulating arrays but not maps.
  { a: ['toString', 'fr'], default: ['de'] },
  { a: ['valueOf'], default: ['de'] },
  // Key order that Object.keys reorders: numeric-looking keys sort ahead of the rest.
  { b: ['x'], 2: ['x'], 1: ['x'], a: ['x'] },
  {},
  [],
];

const cases = [];
for (const start of STARTS) {
  for (const fallback of FALLBACKS) {
    // A fresh clone per call: `fallbackWithLocaleChain` caches on the context it is handed, and a
    // shared one would make later cases read an earlier case's answer.
    const ctx = { __localeChainCache: new Map() };
    const arg = fallback === undefined ? undefined : structuredClone(fallback);
    cases.push({
      start,
      fallback: fallback === undefined ? null : structuredClone(fallback),
      simple: fallbackWithSimple(ctx, structuredClone(arg), start),
      chain: fallbackWithLocaleChain(ctx, structuredClone(arg), start),
    });
  }
}

writeFileSync(
  OUT,
  JSON.stringify(
    {
      $comment:
        'Generated from intlify/vue-i18n by scripts/conformance/generate_fallback_corpus.mjs, ' +
        'running packages/core-base/src/fallbacker.ts over each (start, fallbackLocale) pair. ' +
        '`simple` is fallbackWithSimple() and `chain` is fallbackWithLocaleChain(). A `fallback` of ' +
        'null means the option was undefined. Regenerate only when upstream changes, and say so in ' +
        'the commit.',
      upstream: `intlify/vue-i18n@${version}`,
      cases,
    },
    null,
    1,
  ) + '\n',
);

console.log(`${cases.length} cases -> ${OUT}`);
