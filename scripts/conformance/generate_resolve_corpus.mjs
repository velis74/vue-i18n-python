// Writes conformance/resolve.json by running upstream's own resolver.ts over every (object, path)
// pair below. Run ./bundle-upstream.sh first; see README.md.
//
// Usage: node generate_resolve_corpus.mjs [output-path]
import { readFileSync, writeFileSync } from 'node:fs';

import { parse, resolveValue, resolveWithKeyValue } from './upstream-bundle/upstream_resolve.mjs';

const here = new URL('./', import.meta.url);
const version = readFileSync(new URL('./upstream-bundle/version.txt', here), 'utf8').trim();
const out = process.argv[2]
  ? new URL(process.argv[2], `file://${process.cwd()}/`)
  : new URL('../../conformance/resolve.json', here);

// Long enough that Python's int() refuses to convert it: CPython caps string-to-int conversion at
// 4300 digits and raises above that. JavaScript never converts an index at all, so upstream simply
// answers "no such key", and a port that reaches for int() has to reject the segment before it does.
const HUGE = '9'.repeat(4301);

// Every object goes through JSON.parse so that "__proto__" is an own property, exactly as it is
// when a message resource is loaded from a .json file. An object *literal* with __proto__ would
// set the prototype instead (and would then be dropped by JSON.stringify), which is why the two
// __proto__ keys below are spliced in as raw JSON text rather than written as literal properties.
const MESSAGES = JSON.parse(
  '{"__proto__":"own proto","protoObj":{"__proto__":{"p":"deep own proto"}},' +
  JSON.stringify({
  hello: 'world',
  nested: { a: { b: 'deep' }, empty: {} },
  list: ['zero', 'one', { k: 'in list' }],
  matrix: [['a', 'b'], ['c']],
  n: null,
  num: 42,
  t: true,
  '0': 'index zero',
  '1.5': 'dotted key',
  'a.b': 'flat dotted',
  'with space': 'spaced',
  'ключ': 'unicode key',
  '日本語': { 'キー': 'nested unicode' },
  'emoji😀': 'emoji key',
  '-dash': 'dash',
  _under: 'under',
  $dollar: 'dollar',
  length: 'own length',
  constructor: 'own constructor',
  toString: 'own toString',
  '': 'empty key',
  '*dyn': 'star key',
  deep: { one: { two: { three: 'bottom' } } },
  fn: { call: 'not a function' },
  '١٢٣': 'arabic-indic digits',
  '..': 'two dots',
  '.': 'one dot',
  '00': 'double zero'
  }).slice(1)
);

const AST = JSON.parse(JSON.stringify({
  short: { t: 0, b: { t: 2, i: [{ t: 3, v: 'hi' }] } },
  long: { type: 0, body: { type: 2, items: [{ type: 3, value: 'hi' }] } },
  notAst: { t: 1, b: 'plural body' },
  boolType: { t: false, b: 'bool type' },
  noBody: { t: 0, i: [] }
}));

const ARR = JSON.parse(JSON.stringify(['first', 'second', { k: 'v' }]));

const PLAIN_PATHS = [
  '', ' ', 'hello', 'nested', 'nested.a', 'nested.a.b', 'nested.empty', 'deep.one.two.three',
  'missing', 'nested.missing', 'nested.a.b.c', 'hello.missing', 'num.missing', 't.missing',
  'n', 'n.x', 'num', 't',
  '.', '.hello', 'hello.', 'nested..a', '..', 'a.', '. ',
  'list', 'list.0', 'list.1', 'list.2', 'list.2.k', 'list.3', 'list[0]', 'list[2]["k"]',
  'list.length', 'list.-1', 'list.01', 'list.+0', 'list.1.0', 'matrix.0.1', 'matrix[1][0]',
  'matrix[0].length', 'matrix.length',
  '0', '1.5', "['1.5']", '[1.5]', "['a.b']", '["a.b"]', 'a.b',
  "['with space']", 'with space', "['']", "['hello']", '[ "hello" ]', '[hello]', '[dyn]',
  '[]', '[', ']', "['unterminated", '["unterminated', 'nested[a', "['a\\'b']", '["a\\"b"]',
  'ключ', '日本語.キー', 'emoji😀', '-dash', '_under', '$dollar',
  'length', 'constructor', 'toString', '__proto__', 'hasOwnProperty', 'valueOf',
  'protoObj', 'protoObj.__proto__', 'protoObj.__proto__.p', 'protoObj.p',
  'nested.constructor', 'nested.__proto__', 'nested.toString', 'list.constructor', 'list.map',
  'list.push', 'nested.a.hasOwnProperty', 'fn.call', 'fn.call.length',
  '[true]', '[false]', '[-1]', '[0]', 'hello\tworld', 'hello\nworld', 'a b', 'a b c',
  '  hello  ', 'nested . a', 'nested.a .b',
  // The BOM is whitespace to JavaScript's trim() and not to Python's strip(); NEL (U+0085) and the
  // file separator (U+001C) are the other way round. All three sit inside a sub-path, which is the
  // one place trim() decides whether what is left reads as a quoted literal.
  "[﻿'hello'﻿]", "['hello']", "['hello']",
  "[ 'hello' ]", '[﻿hello﻿]', '[hello]',
  // JavaScript's \d is ASCII-only and Python's is not, so an Arabic-Indic number is a dynamic key
  // to one and a numeric literal to the other.
  '[١٢٣]', '[ ١٢٣ ]', '١٢٣',
  '[00]', '[0x10]', '[01]', '[-0]', '[1e3]', '[+1]',
  // formatSubPath's "invalid leading 0" guard. It is `charAt(0) === '0' && isNaN(parseInt(path))`,
  // and parseInt is NaN behind a leading zero in exactly one situation: it sniffs the 0x/0X radix
  // prefix and finds no hex digit after it. So `[0x]` is a parse error while `[0x10]` (16) and
  // `[0b]` (0) are not, and the guard reads the *untrimmed* path, which is why `[ 0x]` survives it.
  'a[0x]', 'a[0X]', 'a[0xg]', 'a[0x ]', 'a[ 0x]', 'a[0b]', 'a[0x10]', 'a[0e]', 'a[0.5]',
  'nested[0x]', '[0x]', '[0X]', '[0xg]', '[0x ]', '[0b]',
  // Nested brackets: INC_SUB_PATH_DEPTH swallows the inner pair into one dynamic key.
  '[[a]]', '[[0]]', "[['hello']]", 'nested[[a]]', '[[[a]]]', 'list[[0]]',
  '[..]', '[.]', '[-]', '[\'"\']', '["\'"]',
  ' hello', 'hello world', '﻿hello', 'hello﻿world', 'hello world',
  // Digit runs that no array index can be: past the end, past what a double can tell apart, and
  // past what CPython will convert to an int at all.
  'list.19', 'list.100', 'list.9007199254740993', 'list.' + '9'.repeat(20), 'list.' + HUGE,
  'matrix.0.' + HUGE, HUGE
];

const AST_PATHS = [
  'short', 'short.b', 'short.t', 'short.i', 'short.body', 'short.missing',
  'long', 'long.body', 'long.type', 'long.body.items', 'notAst.b', 'notAst.t',
  'boolType.b', 'boolType.t', 'noBody.i', 'noBody.t'
];

// The last two go through an array *root*, which is where resolveWithKeyValue looks the key up
// itself rather than walking to it.
const ARR_PATHS = ['0', '1', '2', '2.k', '3', 'length', '[0]', 'constructor', '', '3'.repeat(20), HUGE];

const cases = [];

function classifyKeyValue(obj, path) {
  if (obj === null || typeof obj !== 'object') {
    return { kind: 'null' };
  }
  const own = Object.prototype.hasOwnProperty.call(obj, path);
  const v = resolveWithKeyValue(obj, path);
  if (!own) {
    return v === undefined ? { kind: 'undefined' } : { kind: 'prototype', typeof: typeof v };
  }
  return { kind: 'value', value: v };
}

function add(obj, path) {
  const keys = parse(path);
  cases.push({
    obj,
    path,
    keys: keys === undefined ? null : keys,
    value: resolveValue(obj, path),
    keyValue: classifyKeyValue(obj, path)
  });
}

for (const p of PLAIN_PATHS) add(MESSAGES, p);
for (const p of AST_PATHS) add(AST, p);
for (const p of ARR_PATHS) add(ARR, p);
for (const root of [null, 'a string', 42, true, false]) {
  for (const p of ['', 'hello', '0', 'length']) add(root, p);
}

// `undefined` never survives JSON, so a value that resolveValue turns into null and one that was
// already null are indistinguishable in the corpus; the runner treats both as None.
const corpus = {
  $comment:
    `Generated from intlify/vue-i18n @ ${version} by running packages/core-base/src/resolver.ts ` +
    "over each (obj, path) pair. `keys` is parse()'s result, null where it fails; `value` is " +
    'resolveValue(); `keyValue` classifies resolveWithKeyValue() - kind "value" when the key is an ' +
    'own property, "undefined" when it is absent, and "prototype" when JavaScript answered from the ' +
    'prototype chain, which this port deliberately does not do. Every object is JSON round-tripped, ' +
    'so "__proto__" is an own property just as it is in a loaded .json resource. Regenerate only ' +
    'when upstream changes, and say so in the commit.',
  upstream: `intlify/vue-i18n@${version}`,
  cases
};

writeFileSync(out, JSON.stringify(corpus, null, 1) + '\n');
console.log(`${cases.length} cases -> ${out.pathname}`);
