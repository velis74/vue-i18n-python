# Gaps

Everywhere this port is not yet vue-i18n, and everywhere it is not yet a finished library.
**This file is the complete list** - if something is left to do and it is not here, that is a
defect in this file. One entry per gap, newest last. A gap is something absent or unverified; a *deliberate difference* is not a gap
and lives under "Deliberate deviations from upstream" in `PROGRESS.md`.

The rule for this file is that a gap is written down the moment it is known, not the moment it is
convenient. Something missing and recorded is a decision; something missing and unrecorded is a
defect waiting to be discovered by a user.

---

## `d()` and `n()` cannot honour every `Intl` option

Ported, and working — but `Intl.DateTimeFormat` and `Intl.NumberFormat` do not exist in Python, so
`babel` stands in and some of the option surface has nowhere to land.

**Refused outright:** `part=True` (`formatToParts`). babel has no counterpart and a caller asking for
parts wants the structure, so it raises rather than returning an approximation.

**Accepted and ignored:** `localeMatcher`, `currencySign`, `signDisplay`, `unit`, `unitDisplay`,
`roundingMode`, `roundingPriority`, `roundingIncrement`, `trailingZeroDisplay`,
`minimumSignificantDigits`, `maximumSignificantDigits` for numbers; `localeMatcher`, `formatMatcher`,
`calendar`, `numberingSystem`, `hourCycle`, `fractionalSecondDigits` for dates. They are listed in
`UNSUPPORTED_OPTIONS` in each module and reportable through `unsupported_number_options()` /
`unsupported_datetime_options()`, so a caller can ask what will be dropped rather than discover it.

**Not a gap, and not fixable:** the formatted strings will not match `Intl` character for character.
The two carry different CLDR data versions. No corpus pins them, deliberately.

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

---

## The plural-index clamp is undecided

`MessageContext.plural` clamps an out-of-range index from a caller's rule; vue-i18n throws
`UNEXPECTED_RETURN_TYPE`. Documented and tested under "Deliberate deviations from upstream" in
`PROGRESS.md`, but recorded there as **unsettled**: the throw is what tells a developer their rule is
wrong, and clamping means a bug that crashes the browser renders quietly on the server. Waiting on a
decision from the project owner.

---

## Nothing has run against a real application yet

Every claim in this repository rests on recorded upstream behaviour and on tests. Not one line has
served a page. The version is `0.1.0` and the classifier says alpha for that reason, and the first
confirmed production use is what earns 1.0 — not a complete corpus.

---

## Not yet publishable

Nothing here is about behaviour; these are the formalities between a working library and a release.

- **No GitHub repository.** The URLs in `pyproject.toml` (`velis74/vue-i18n-python`) are a guess and
  point at nothing. The `socialLinks` entry in `docs/.vitepress/config.ts` guesses the same.
- **No `CHANGELOG.md`.** `UPSTREAM.md` says every release records the vue-i18n version it tracks;
  there is nowhere yet for it to be recorded.
- **No CI.** Nothing runs the tests, the lint, the docs build or the corpus regeneration on a push.
  `muxws` has `.github/workflows/{ci,cross-language,docs}.yml` and this should follow it.
- **`py.typed` ships but nothing type-checks.** The package declares itself typed and no mypy or
  pyright run backs that up.
- **The name is unclaimed on PyPI.** `vue-i18n-python` was free when checked (2026-08-12) and has
  not been registered.

## Decisions waiting on the owner

- Whether the plural-index clamp should stay or become a raise (above).
- Whether `te()`, `tm()` and `rt()` belong here (above).
- Whether to fix the three reproduced upstream bugs locally, or wait for upstream. Fixing them makes
  this port disagree with the browser, which is the thing it exists not to do; waiting means shipping
  known-wrong behaviour. Currently: reproduced, documented, reported.
- Whether to tell intlify about the port, now that two issues are open under the same account.
