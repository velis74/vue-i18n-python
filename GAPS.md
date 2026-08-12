# Gaps

Everywhere this port is not yet vue-i18n, and everywhere it is not yet a finished library. One entry
per gap, newest last. A gap is something absent or unverified; a *deliberate difference* is not a gap
and lives under "Deliberate deviations from upstream" in `PROGRESS.md`.

The rule for this file is that a gap is written down the moment it is known, not the moment it is
convenient. Something missing and recorded is a decision; something missing and unrecorded is a
defect waiting to be discovered by a user.

---

## `d()` and `n()` are not ported

**What is missing:** `packages/core-base/src/datetime.ts`, `number.ts` and the parts of
`formatter.ts` they use. A caller cannot format a date or a number through this library at all.

**Why it is not simply a port:** the structure ports cleanly — the format resources are plain data,
and the argument shapes, locale fallback walk, missing handling and caching are all logic — but
`Intl.DateTimeFormat` and `Intl.NumberFormat` do not exist in Python. `babel` is the intended
substitute and is already declared as the `intl` extra in `pyproject.toml`.

**What it will not do:** match `Intl`'s output character for character. The two carry different CLDR
data versions, so pinning their strings would be testing someone else's data rather than this port.
The tests will cover the logic — which locale is chosen from the chain, which format name resolves,
how overrides merge, what a missing format does — and the corpus will not pin the formatted text.

---

## `escape_parameter` does not sanitise its output

**What is missing:** upstream's `sanitizeTranslatedHtml` from `packages/shared/src/sanitize.ts` —
attribute-value sanitisation, event-handler neutralisation and `javascript:` URL stripping, 162
lines of it.

**What is present:** `escape_html`, character for character, applied to every string parameter when
the option is on. That is the half the option is named after.

**Why it is recorded rather than half-done:** a security feature that is quietly weaker than the one
it copies is worse than one that is plainly absent. Enabling `escape_parameter` therefore warns once
per process (`runtime/sanitize.py`, `warn_output_not_sanitized`) saying exactly what is not applied.
The warning stays until the sanitizer lands.

**Mitigating:** the option is off by default, and a Python back end usually hands translated text to
a template engine that escapes on output anyway.

---

## The documentation site does not exist

**What is missing:** `docs/` has a `package.json` and nothing else. No `.vitepress/config.ts`, no
pages.

**What it must say**, because these were asked for explicitly: that this library is a port of
vue-i18n; what the differences are; and the commitment to follow vue-i18n's releases. The material
for the third is written — `UPSTREAM.md` — and the material for the second is the deviations section
of `PROGRESS.md`. Neither is a substitute for a page a user will actually read.

---

## Upstream's own test suite is not ported

**What is missing:** the 477 `it()` blocks under `packages/message-compiler/test/` and
`packages/core-base/test/` that cover the modules this port has.

**Why it matters:** the conformance corpora record what vue-i18n *does*. Upstream's tests encode what
it is *supposed to do*. A corpus cannot tell the two apart, so where upstream has a bug this port
reproduces it faithfully and the corpus agrees enthusiastically.

**Why it is deferred:** the library comes first. This is worth doing once the library is complete,
and worth doing at a smaller scale than "all 477" — the cases that describe intent are the valuable
ones.

---

## Options that are threaded but not exercised

`processor`, `fallback_context` and `post_translation` are read by `translate()` and passed where
upstream passes them, but nothing in the corpora or the tests uses them. They are ported code with
no evidence behind them, which is a weaker claim than the rest of the runtime carries.

`fallback_context` in particular is the mechanism by which vue-i18n's component-local messages fall
back to the global ones. Its Python meaning is real but unproven.

---

## The Vue-level API is out of scope, and it is not obvious that it should be

**What is missing:** `te()` (does this key exist), `tm()` (fetch a whole message subtree), `rt()`
(render an already-resolved message). These live in `vue-i18n-core`'s composer rather than in
`core-base`, alongside the components, directives and `useI18n` that genuinely have no Python
meaning — so by the ported-package boundary they are out.

**Why it is a gap anyway:** the brief is "same API", and `te()` and `tm()` are things a Python caller
would plausibly reach for and find missing. They are also small. Worth a decision rather than an
omission by boundary.
