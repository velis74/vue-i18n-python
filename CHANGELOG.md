# Changelog

All notable changes to `vue-i18n-python` are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

**Version numbers are this package's own and do not track vue-i18n's.** A port needs releases for
reasons of its own — a bug here, a new Python version, a documentation fix — and most vue-i18n
releases touch only the Vue bindings this project does not port. Every entry below therefore names
the vue-i18n release it behaves like, and
[which version tracks which](https://docs.velis.si/vue-i18n-python/guide/version-translation.html)
is the same table on the site.

## [0.2.0] - 2026-08-13

First release. Behaves like **vue-i18n 11.4.8**, the current stable release.

0.2.0 is the first published version; there is no 0.1.0 on PyPI.

### Added

- **The message compiler** — tokenizer, parser and AST, ported from
  `packages/message-compiler/src`. Named and positional placeholders, `a | b | c` plurals,
  `@:linked` messages, `@.upper:` modifiers and `{'@'}` literals, with the same error codes,
  messages and source locations as upstream.
- **The runtime** — `translate()`, the key resolver, the fallback walk, the message context and the
  AST evaluator, ported from `packages/core-base/src`. Nested keys, flat dotted keys, per-call
  locale override, defaults, the missing-key path, and both fallback walkers.
- **`d()` and `n()`** for dates and numbers, standing on `babel` — the `intl` extra. Their option
  objects are vue-i18n's and travel in the message resource unchanged.
- **`vue_i18n.plurals`** — CLDR 48 plural rules for 224 locales, an arity ladder for messages
  carrying fewer forms than the locale has categories, and an explicit `zero` that CLDR does not
  have. Opt-in, passed as `plural_rules`; nothing in the runtime reaches for it.
- **`vue_i18n.check`** and `python -m vue_i18n.check` — compiles every message, follows every
  `@:link`, compares each locale against the base one, and matches the keys your code asks for
  against the keys that exist. Python is parsed with `ast`; `.vue`, `.ts` and `.js` are
  pattern-matched. A key missing from the base locale fails; a key not yet translated does not.
- **Type information** — `py.typed` ships with the package.

### Verified against upstream

Seven corpora, every case recorded by running real vue-i18n and replayed on each test run: 128 ASTs
with their error codes and source locations, 57 `translate()` calls against `@intlify/core-base`
itself, 74 rendered messages, 200 key-path resolutions, 374 fallback chains, and 1612 values through
JavaScript's `String()` semantics.

The CLDR rules under `vue_i18n.plurals` are held to `conformance/plurals.json` — 4180 rows, 16 644
`(locale, n, arity)` cases — and the generated category functions were separately verified against
`Intl.PluralRules` in Node over 167 097 cases across 219 locales with no mismatches.

### Known limits

Deliberate differences from vue-i18n, and what is knowingly missing, are listed on the
[differences page](https://docs.velis.si/vue-i18n-python/guide/differences.html) and in `GAPS.md`.
The two that matter most on day one:

- The default plural rule is vue-i18n's, which ignores the locale and stops at two forms. Pass
  `plural_rules` — see [plural rules](https://docs.velis.si/vue-i18n-python/guide/plurals.html).
- `escape_parameter` escapes interpolated values but does not yet apply upstream's
  `sanitizeTranslatedHtml` to the result. Enabling it warns once saying exactly that.

Nothing here has served a production page yet. That, not a complete corpus, is what 1.0 waits for.

[0.2.0]: https://github.com/velis74/vue-i18n-python/releases/tag/v0.2.0
