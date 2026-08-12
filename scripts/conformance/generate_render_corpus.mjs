// Regenerates conformance/render.json — the end-to-end corpus.
//
//   npm i vue vue-i18n   # in this directory's node_modules, or run from a tree that has them
//   node scripts/conformance/generate_render_corpus.mjs
//
// Every other corpus pins one stage. This one pins the whole pipeline: a source message goes in and
// a rendered string comes out of REAL vue-i18n, through its tokenizer, parser, message context,
// interpolation, linked-message resolution and modifiers. If the Python port agrees here, it agrees
// about the thing users actually see.
//
// Plural SELECTION is deliberately pinned rather than exercised: for a message with k branches the
// generator asks vue-i18n for each branch in turn, by supplying a `pluralRules` function that
// returns a fixed index. The two ports disagree about which form a locale's rules pick — that is the
// project's whole point — so mixing that question into this corpus would make it untestable. Which
// form gets picked is `conformance/plurals.json`'s job.

import { writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
import { createI18n } from 'vue-i18n';

const OUT = resolve(dirname(fileURLToPath(import.meta.url)), '../../conformance/render.json');

const LINKS = {
  greeting: 'hi there',
  loud: 'HI THERE',
  deep: { key: 'nested value' },
  withparam: 'hi {who}',
  chain1: '@:chain2',
  chain2: 'end of chain',
  selfref: '@:selfref',
  accented: 'čebula',
  german: 'straße',
  astral: '𐐨test',
  turkish: 'iı',
  empty: '',
};

const CASES = [
  { source: 'plain text' },
  { source: 'hello {name}', named: { name: 'Jure' } },
  { source: 'hello {name}' },
  { source: '{a} and {b}', named: { a: 'x', b: 'y' } },
  { source: '{0} then {1}', list: ['first', 'second'] },
  { source: '{0} then {1}', list: ['only'] },
  { source: '{count} items', named: { count: 3 } },
  { source: '{count} items', named: { count: 0 } },
  { source: '{v} here', named: { v: 1.5 } },
  { source: '{v} here', named: { v: 1.0 } },
  { source: '{v} here', named: { v: true } },
  { source: '{v} here', named: { v: false } },
  { source: '{v} here', named: { v: null } },
  { source: '{v} here', named: { v: [1, 2] } },
  { source: '{v} here', named: { v: { a: 1 } } },
  { source: '{v} here', named: { v: '' } },
  { source: '{v} here', named: { v: 1e21 } },
  { source: '{v} here', named: { v: 0.000001 } },
  { source: "{'literal'}" },
  { source: "{'@'} sign" },
  { source: "{'{'}braces{'}'}" },
  { source: "{'it\\'s'}" },
  { source: "{'\\u0041'}" },
  { source: "{'\\U01F600'}" },
  { source: 'escaped \\{name\\}', named: { name: 'n' } },
  { source: 'escaped \\@ and \\| and \\\\' },
  { source: '@:greeting' },
  { source: '@:deep.key' },
  { source: '@.upper:greeting' },
  { source: '@.lower:loud' },
  { source: '@.capitalize:greeting' },
  { source: '@.upper:accented' },
  { source: '@.upper:german' },
  { source: '@.capitalize:accented' },
  { source: '@.capitalize:astral' },
  { source: '@.upper:astral' },
  { source: '@.upper:turkish' },
  { source: '@.lower:turkish' },
  { source: '@.capitalize:empty' },
  { source: '@:missing' },
  { source: '@.upper:missing' },
  { source: '@:empty' },
  { source: 'before @:greeting after' },
  { source: '@:a @:b' },
  { source: "@:{'greeting'}" },
  { source: '@:{ref}', named: { ref: 'greeting' } },
  { source: 'link to @:withparam', named: { who: 'world' } },
  { source: '@:chain1' },
  { source: '@.upper:chain1' },
  { source: 'no apples | one apple | {count} apples', named: { count: 5 } },
  { source: 'nič|ena|dve|{count} tri|{count} pet', named: { count: 3 } },
  { source: 'a | b' },
  { source: ' padded | branches ' },
  { source: '{name} | {name}s', named: { name: 'cat' } },
  { source: '@:greeting | @:greeting plural' },
  { source: 'multi\nline {v}', named: { v: 'x' } },
  { source: 'emoji 🎉 {v}', named: { v: 'y' } },
  { source: 'unicode č š ž {v}', named: { v: 'ć' } },
  { source: '{a}{b}{c}', named: { a: 1, b: 2, c: 3 } },
  { source: '{-1}', list: ['neg'] },
  { source: '{10}', list: ['zero'] },
  { source: '{0}{0}{0}', list: ['r'] },
  { source: '@:deep', named: {} },
];

const out = [];
for (const c of CASES) {
  const branches = c.source.split('|').length;
  for (let branch = 0; branch < branches; branch++) {
    const i18n = createI18n({
      legacy: false,
      locale: 'xx',
      fallbackLocale: 'xx',
      missingWarn: false,
      fallbackWarn: false,
      messages: { xx: { ...LINKS, __subject__: c.source } },
      pluralRules: { xx: () => branch },
    });
    let rendered = null;
    let threw = null;
    try {
      const args = c.list ?? c.named ?? {};
      rendered = i18n.global.t('__subject__', args, branches > 1 ? { plural: 1 } : undefined);
    } catch (e) {
      threw = String(e && e.message);
    }
    out.push({ source: c.source, named: c.named ?? null, list: c.list ?? null, branch, branches, rendered, threw });
  }
}

writeFileSync(
  OUT,
  JSON.stringify(
    {
      $comment:
        'Generated by scripts/conformance/generate_render_corpus.mjs from REAL vue-i18n. Each case ' +
        'is one source message rendered to one string, with plural selection pinned to a fixed ' +
        'branch so this corpus tests rendering only. The linked-message resources are in `links`.',
      upstream: 'intlify/vue-i18n@12.0.0-alpha.4 (rendered with the installed vue-i18n runtime)',
      links: LINKS,
      cases: out,
    },
    null,
    1,
  ) + '\n',
);

console.log(`${out.length} renders -> ${OUT}`);
