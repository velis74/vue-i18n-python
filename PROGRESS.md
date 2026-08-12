# Progress

Working notes. The cron job that restarts this work is session-only and expires after 7 days, so
this file — not the cron, and not the task list — is the continuity mechanism. Read it first.

## What this project is

**A Python port of vue-i18n.** Same JSON message files, same API, same behaviour — in Python. That
is the whole brief, and everything below is subordinate to it.

There is **no JavaScript in the deliverable**. Node appears twice and both are development-time:
VitePress builds the documentation site under `docs/`, and the generators under
`scripts/conformance/` run *real vue-i18n* and record what it returns. Those recordings are what the
port is held to — without them the port could only claim to match vue-i18n rather than be checked
against it, and they are what caught every real bug so far. The root `package.json` is
`private: true` and holds nothing else.

**Reference version: vue-i18n 11.x**, the current stable release, which is what `npm i vue-i18n`
installs today. The message compiler is byte-identical between 11.4.8 and 12.0.0-alpha.4 — all 126
comparable corpus cases match — so that half of the port is version-independent. The two differ on
plural selection: 12 added an `Intl.PluralRules` path that 11 does not have. This port follows 11.

### Behaving the same means not being cleverer

vue-i18n's default plural rule ignores the locale: two forms are singular/plural, more than that
clamps at index 2, so a fourth or fifth form is unreachable in any language. That is wrong for
Slovenian and most of its neighbours — and it is what the port does, because the port's job is to
behave identically. A Vue application fixes this by passing `pluralRules` to `createI18n`; the
Python equivalent is `plural_rules` on the message context.

`vue_i18n/plurals/` — the CLDR-derived rules, the arity ladder, the explicit `zero` form — is
therefore **an opt-in extra, not the default**. Nothing in the runtime reaches for it. It exists
because a caller who wants correct Slovenian plurals needs something to pass in, and hand-writing
that rule is what people currently do.

Upstream is tracked by the submodule at `vendor/vue-i18n`, pinned to the released version.
`UPSTREAM.md` records the pin, what maps to what, and the procedure when a new release lands.
Not ported, deliberately: `message-compiler`'s `generator`/`optimizer`/`mangler`/`transformer`
(they emit JavaScript; this port interprets the AST), `context.ts`'s devtools hooks, and
`vue-i18n-core` / `vue-i18n` entirely — components, directives and the Vue APIs have no Python
meaning.

## Decisions already settled (do not relitigate)

1. **The brief is a port**, stated at the top of this file. When the port and vue-i18n disagree,
   vue-i18n is right, even where vue-i18n is arguably wrong.
2. **Released versions only.** The submodule pin never moves to an alpha, beta or release candidate.
3. **`vue_i18n/plurals/` is opt-in and is not part of the port.** It exists so a caller has
   something to pass as `plural_rules`, the way a Vue application passes `pluralRules` to
   `createI18n`. Its model — a precedence list per locale, a ladder for messages carrying fewer
   forms than the locale has categories, and an explicit `zero` that CLDR does not have — is
   documented in `vue_i18n/plurals/__init__.py`. Nothing in the runtime reaches for it.
4. **Warnings go through Python's `warnings` module** under the `I18nWarning` category, rather than
   through an `on_warn` option only this library understands. `on_warn` still exists and still
   overrides.
5. **Corpora are recorded from real vue-i18n, never hand-authored.** A hand-written expectation
   tests the implementation against itself. Every corpus names the version that produced it, and
   every generator lives in `scripts/conformance/`.

## Deliberate deviations from upstream

Each one is asserted by a test, so it cannot widen unnoticed:

- **`\U` past U+10FFFF.** `{'\U110000'}` makes upstream's `String.fromCodePoint` throw a RangeError,
  so no AST is produced at all. This port substitutes U+FFFD — the same thing upstream already does
  for a lone surrogate — so that one malformed escape cannot abort the load of a whole file. The two
  corpus cases carry `upstream_throws` rather than an expected AST. Asserted in
  `vue_i18n/compiler/conformance_test.py`.
- **`resolve_with_key_value` reads own properties only.** Upstream's `resolveWithKeyValue` is
  `isObject(obj) ? obj[path] : null`, a plain property read that answers from the prototype chain:
  `resolveWithKeyValue({}, 'constructor')` hands back the `Object` constructor, `'toString'` and
  `'hasOwnProperty'` native functions, `'__proto__'` the prototype object. The Python equivalent
  would be reading an attribute, i.e. resolving a message key into `dict.keys`, `__class__` and
  everything reachable from there. This port returns `None` for those paths instead. The corpus
  marks such cases `"keyValue": {"kind": "prototype"}` and `resolver_test.py` asserts `None` for
  each. `resolve_value` needs no deviation: it already goes through `hasOwn`, so upstream does not
  leak there either.

- **An out-of-range plural rule clamps instead of raising.** A caller's `plural_rules` function
  returns an index; when it returns one past the last form, vue-i18n reads `undefined` and throws
  `UNEXPECTED_RETURN_TYPE`, taking the render down. This port clamps to the last form instead
  (`message_context.py`, `MessageContext.plural`).

  This one is **not settled**. Clamping is friendlier and is the direction upstream moved in v12,
  whose `Intl` path does `Math.min(index, choicesLength - 1)`. But the throw is what tells a
  developer their rule is wrong, and a real example exists: the hand-written `southSlavicRule` in
  `~/Projects/slovenske-železnice/vue/locale/index.ts` returns index 4 for a *four*-form Slovene
  message, which crashes in the browser and would render quietly here. Hiding that is arguably worse
  than reproducing it. Asserted by `message_context_test.py` either way, so whichever is chosen is
  chosen deliberately.

Not deviations, but worth knowing:

- **Reported offsets and columns count UTF-16 code units, not code points**, because that is what
  JavaScript strings measure. `Scanner.u16_index()` maintains the count. Without it every location
  past the first emoji in a message would disagree with vue-i18n by one.
- **The resolver walks `dict` and `list` and nothing else.** A message resource is JSON, so those
  are the only two containers a path can meet, and `is_object()` says so. That is also what makes
  the resolver structurally unable to reach a Python attribute. A JavaScript array's own properties
  include `length`, so `t('items.length')` really does return the count in both ports.

## State

- [x] Repository skeleton — pyproject, package.json, tsconfig, vite, eslint, LICENSE, README
- [x] Python message compiler (tokenizer, parser, AST) — `vue_i18n/compiler/`.
      Validated differentially against upstream bundled straight from the clone with esbuild:
      **128/128 messages produce byte-identical ASTs, error codes and error messages**, and
      **102/102 identical token streams including every source location**. The corpus lives in
      `conformance/compile.json`; regenerate it only when upstream changes, and say so in the commit.
      Not ported: `generator`, `optimizer`, `mangler`, `transformer` (they emit JavaScript).
- [x] Python runtime — complete for translation. `context.py` and `translate.py` are in, on top of
      `resolver`, `fallbacker`, `errors`, `warnings`, `display`, `message_context` and `format`.
      Validated against `@intlify/core-base` 11.4.8 itself: `conformance/translate.json`,
      **59/59 calls returning identical strings** — ordinary keys, nested and flat dotted keys,
      linked messages and modifiers, the fallback chain at each depth, per-call locale override,
      defaults, missing keys, and plural counts 0–102 in three locales.
      Two defects the corpus caught that the smoke test had not: a per-call `locale` option was
      silently ignored (the options object was passed to `get_locale` as a dict, which reads its
      `locale` attribute), and nested keys did not resolve at all.
      Still missing: `d()` and `n()`, and the output half of `escape_parameter`.
- [x] `runtime/message_context.py` + `runtime/format.py` — the message context (named/list values,
      linked lookup, modifiers, plural dispatch) and the AST evaluator.
      Validated end to end against **real vue-i18n**: `conformance/render.json`, **74/74 rendered
      strings identical**, covering interpolation, literals, every escape, linked messages, linked
      chains, dynamic linked keys, all three built-in modifiers, and each plural branch. Plural
      *selection* is pinned to a fixed branch there on purpose — which form a locale picks is
      `conformance/plurals.json`'s question, and the two ports disagree about it by design.
      Two traps found and fixed while building it: `@.capitalize` must not uppercase the first *code
      point*, because upstream's `charAt(0)` reads a UTF-16 unit and leaves an astral character
      alone ("𐐨test" stays "𐐨test"); and the built-in `upper`/`lower`/`capitalize` modifiers live in
      `context.ts`, not in `runtime.ts`, so a port of the latter alone renders `@.upper:x` unchanged.
- [x] `vue_i18n/runtime/display.py` — JavaScript's `String()` and `toDisplayString()`, which
      decide what a non-string value looks like once it reaches a `{placeholder}`. Needed because
      `str(1.0)` is `"1.0"` here and `"1"` there, and `str(True)` is `"True"` against `"true"`.
      Validated against Node: **1612/1612 cases identical**, of which 1576 are random 64-bit float
      patterns — shortest-round-trip formatting is where a hand-written port goes wrong, and it goes
      wrong on values nobody would write down. `scripts/conformance/generate_display_corpus.mjs`
      regenerates `conformance/display.json` byte for byte from a seeded PRNG.

## Where the two languages cannot agree

Not deviations and not fixable — properties of the languages. Both are kept out of the corpora so no
fixture ever pins one:

- **A JavaScript number is an IEEE double.** Past 2^53 it is not the integer that was written, so
  `String(12345678901234567890)` is `"12345678901234567000"` there. A Python `int` is exact at any
  size, and this port prints the integer it was given rather than throwing away precision the caller
  deliberately passed. A Python `float` of the same magnitude *does* follow JavaScript, because
  there the precision really is gone. Asserted in
  `runtime/display_test.py::test_python_int_beyond_double_precision_is_exact_not_javascript_shaped`.
  The same boundary applies to a plural `count`.
- **Visible fraction digits depend on the written form.** `1` has none and `Decimal("1.0")` has one,
  which is what CLDR's `v` operand means. A `float` is read through `repr`, so `1.0` has one visible
  fraction digit where JavaScript's `String(1.0)` has none.
- [x] CLDR plural rules: extraction + generators for both languages.
      `cldr/plurals.json` is `supplemental/plurals.json` from **npm cldr-core@48.2.0 (CLDR 48,
      Unicode 16)**, vendored verbatim with a `_vendored` provenance block on top.
      `scripts/generate_plurals.py` parses the UTS #35 rule syntax and writes both
      `vue_i18n/plurals/_generated.py` and `ts/plurals/generated.ts`: 224 locales collapse to
      **40 distinct rule sets**, one function each, plus the per-locale precedence list. The runtime
      (ladder, fall-forward, explicit `zero`) is hand-written in `vue_i18n/plurals/__init__.py`;
      `plurals_test.py` asserts the item-4 Slovenian table literally and tables for hr, en, ru, ar,
      ja, pl, cy at every arity, and `test_generated_modules_are_up_to_date` fails if either
      generated file is hand-edited.
      Verified against **`Intl.PluralRules` in Node 26 (ICU 78, CLDR 48)** — an independent
      implementation of the same data: **167 097 cases across 219 locales, 0 mismatches**, for both
      the Python and the TypeScript output. Cases cover 0–230, powers of ten up to 2 000 000, and
      fractions, each at `minimumFractionDigits` 0, 1 and 2 so the `v`/`w`/`f`/`t` operands are
      exercised. Five CLDR ids are excluded because ICU aliases them away and would answer with a
      different locale's rules: `jw→jv`, `mo→ro`, `sh→sr`, `tl→fil`, `und→en-GB`.
      **The precedence rule** (`PRECEDENCE_ORDER` in the generator): `other, one, zero, two, few,
      many`, filtered to the locale's CLDR categories plus `zero`. Read as "what does the k-th form
      buy you" — one form is always legal, the second is the singular/plural split, the third the
      hand-written "no items" case, then the rest of CLDR in canonical order. For `sl` it derives
      `[other, one, zero, two, few]`, i.e. exactly the item-4 table; for `en`, `[other, one, zero]`,
      i.e. the ordinary 2-form and 3-form behaviour.
      Two consequences worth knowing: fall-forward is uniform, so in a locale whose CLDR *does* have
      `zero` (ar, cy, lv, …) a message that supplies no zero form sends n = 0 one step forward onto
      `one`, not to `other`; and an arity above the full ladder leaves the surplus forms unreachable
      rather than inventing a category.
- [ ] Python `d()` / `n()` via babel
- [ ] `escape_parameter`: parameters are escaped (`runtime/sanitize.py` ports `escapeHtml`), but
      upstream's `sanitizeTranslatedHtml` — attribute sanitisation, event-handler neutralisation,
      `javascript:` URL stripping — is not ported. Enabling the option warns once saying so, and
      that warning stays until the sanitizer lands.
- [ ] TS loader package. **`ts/` still needs its plural runtime and its conformance runner.**
      `ts/plurals/generated.ts` exists and is verified, but the ladder arithmetic (locale
      resolution, operand extraction, `plural_index`) has no TypeScript home yet, so nothing in the
      repo replays `conformance/plurals.json` on the TS side. It has been replayed once, by a scratch
      harness (not committed) that transpiles `generated.ts` with esbuild and transcribes the ~30
      lines of ladder arithmetic from `vue_i18n/plurals/__init__.py` into JS: **13 452
      (locale, n, arity) cases, 0 index mismatches, 0 category mismatches, 0 ladder mismatches**.
      Write that arithmetic properly in `ts/plurals/`, then a runner over the corpus, then CI.
- [ ] Conformance corpus + two runners.
      `conformance/plurals.json` is done: 43 locales (one per distinct rule set, plus the eight the
      tests name), 3 268 rows of `(locale, n) -> category + indexes[arity - 1]`, 13 452
      `(locale, n, arity)` cases, produced by `scripts/generate_plural_corpus.py` from the Python
      runtime and re-checked by `test_conformance_corpus_matches_the_runtime`. `n` is a decimal
      string, and only values that survive a JavaScript `String(Number(x))` round trip appear —
      `Decimal("1.0")` has one visible fraction digit in Python and `1.0` has none in JavaScript, and
      pinning that into the corpus would pin a language difference rather than a plural rule.
- [ ] SPEC.md
- [ ] CI

## Open, not yet decided

- GitHub org for the repository. `velis74` assumed in the `pyproject.toml` URLs; the local
  directory is still `i18n-united` and there is no remote yet.
