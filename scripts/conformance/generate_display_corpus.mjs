// Regenerates conformance/display.json.
//
//   node scripts/conformance/generate_display_corpus.mjs
//
// Unlike the other generators this one needs no upstream bundle: `String()` is the language, and
// `toDisplayString` is six lines of packages/shared/src/utils.ts reproduced below. If that function
// changes upstream, change it here too - the copy is the thing being tested against.
//
// The number pool is deliberately dominated by random 64-bit patterns. Shortest-round-trip
// formatting is where a hand-written port goes wrong, and it goes wrong on values nobody would
// think to write down by hand.

import { writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
import { readFileSync } from 'node:fs';

const HERE = dirname(fileURLToPath(import.meta.url));
const OUT = resolve(HERE, '../../conformance/display.json');
// The pinned submodule, because the toDisplayString copy below is a copy *of that version*.
const VERSION = JSON.parse(readFileSync(resolve(HERE, '../../vendor/vue-i18n/package.json'), 'utf8')).version;

const objectToString = Object.prototype.toString;
const isPlainObject = (v) => objectToString.call(v) === '[object Object]';
const toDisplayString = (val) =>
  val == null
    ? ''
    : Array.isArray(val) || (isPlainObject(val) && val.toString === objectToString)
      ? JSON.stringify(val, null, 2)
      : String(val);

// Deterministic PRNG, so re-running the generator does not churn the corpus.
let seed = 0x2f6e2b1;
const nextU32 = () => {
  seed ^= seed << 13;
  seed ^= seed >>> 17;
  seed ^= seed << 5;
  return seed >>> 0;
};

const buffer = new ArrayBuffer(8);
const asFloat = new Float64Array(buffer);
const asInt = new Uint32Array(buffer);

const numbers = [
  0, 1, -1, 1.5, -0.0, 0.1, 100, 1e20, 1e21, 1e22, 1.5e21, 1e-6, 1e-7, 1e-21, 0.000001, 0.0000001,
  3.14159, 2.5e-10, 1e100, -1e-7, 0.30000000000000004, 5e-324, 1.7976931348623157e308, 2 ** 53,
];
while (numbers.length < 1600) {
  asInt[0] = nextU32();
  asInt[1] = nextU32();
  const f = asFloat[0];
  if (Number.isFinite(f)) numbers.push(f);
}

const cases = numbers.map((v) => ({ value: v, kind: 'number', string: String(v), display: toDisplayString(v) }));
for (const v of [true, false, 'plain', '', null]) {
  cases.push({ value: v, kind: typeof v, string: String(v), display: toDisplayString(v) });
}
for (const v of [[1, 2], ['a', 'b'], [], { a: 1 }, {}, { 'č': 'š' }, { a: { b: [1, 'x'] } }]) {
  cases.push({ value: v, kind: 'container', string: null, display: toDisplayString(v) });
}

writeFileSync(
  OUT,
  JSON.stringify(
    {
      $comment:
        'Generated from Node by scripts/conformance/generate_display_corpus.mjs. Each case records ' +
        'what JavaScript String(value) and toDisplayString(value) produce; the Python port must ' +
        'agree. Numbers include random 64-bit patterns, because shortest-round-trip formatting is ' +
        'where a hand-written port goes wrong.',
      upstream: `intlify/vue-i18n@${VERSION} (packages/shared/src/utils.ts)`,
      node: process.version,
      cases,
    },
    null,
    1,
  ) + '\n',
);

console.log(`${cases.length} cases -> ${OUT}`);
