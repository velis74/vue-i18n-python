// Writes conformance/compile.json by parsing every message in messages.json with upstream's own
// `createParser()`. Run ./bundle-upstream.sh first; see README.md.
//
// Usage: node generate_compile_corpus.mjs [output-path]
import { readFileSync, writeFileSync } from 'node:fs';

import { createParser } from './upstream-bundle/upstream_compile.mjs';

const here = new URL('./', import.meta.url);
const version = readFileSync(new URL('./upstream-bundle/version.txt', here), 'utf8').trim();
const messages = JSON.parse(readFileSync(new URL('./messages.json', here), 'utf8'));
const out = process.argv[2]
  ? new URL(process.argv[2], `file://${process.cwd()}/`)
  : new URL('../../conformance/compile.json', here);

const cases = [];

for (const source of messages) {
  const errors = [];
  const parser = createParser({ onError: e => errors.push({ code: e.code, message: e.message }) });
  try {
    cases.push({ source, ast: parser.parse(source), errors });
  } catch (e) {
    // `String.fromCodePoint` throws a RangeError past U+10FFFF, so upstream produces no AST at all
    // for `{'\U110000'}`. The Python port deliberately substitutes U+FFFD instead rather than let
    // one malformed escape abort the load of a whole file, so the case carries the message of the
    // exception in place of an AST and the runner asserts the deviation.
    cases.push({ source, upstream_throws: String(e && e.message), ast: null, errors });
  }
}

writeFileSync(
  out,
  JSON.stringify(
    {
      $comment:
        `Generated from intlify/vue-i18n @ ${version} by parsing each source with createParser() ` +
        'and serialising the result. The TypeScript AST is the source of truth and the Python ' +
        'port is held to it. Regenerate only when upstream changes, and say so in the commit.',
      upstream: `intlify/vue-i18n@${version}`,
      cases
    },
    null,
    1
  ) + '\n'
);
console.log(`${cases.length} cases -> ${out.pathname}`);
