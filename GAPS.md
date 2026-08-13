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
served a page. The version is pre-1.0 and the classifier says alpha for that reason, and the first
confirmed production use is what earns 1.0 — not a complete corpus.

---

## Not yet publishable

Nothing here is about behaviour; these are the formalities between a working library and a release.

- **No `CHANGELOG.md`.** `UPSTREAM.md` and the documentation both say every release records the
  vue-i18n version it tracks; there is nowhere yet for it to be recorded. The first release breaks
  that promise the moment it is made, which makes this the one item on this list that is genuinely
  release-blocking rather than merely missing.
- **CI is written but has never run.** `.github/workflows/ci.yml` lints, tests on 3.10 through 3.13,
  builds both artefacts, runs `twine check` and builds the docs; every step was verified locally
  first. It is still unproven until the first push, and the action majors (`checkout@v7`,
  `setup-node@v7`) are taken from `@dynamicforms/vue-forms` rather than confirmed here.
  **Corpus regeneration is not in it**: re-recording against a freshly resolved `vue-i18n@^11` would
  turn an upstream release into a red build on an unrelated pull request. That check wants its own
  scheduled workflow, which is not written.
- **`ruff format` is not enforced.** `ruff check` passes and CI runs it; `ruff format --check .`
  currently reports 8 files. Either the tree gets formatted once and the check joins CI, or the
  `[tool.ruff.format]` section is admitting to a standard nothing holds the code to.
- **`py.typed` ships but nothing type-checks.** The package declares itself typed and no mypy or
  pyright run backs that up.
- **`SPEC.md` is listed in the sdist `include` and does not exist.** Harmless — hatch skips a
  missing pattern and `python -m build` succeeds — but it is a reference to a file that has to
  either get written or get removed from `pyproject.toml`.
- **The docs site is not deployed anywhere,** and `publish` does not rebuild it. The version numbers
  on the site are read from the package source at build time, so whoever deploys has to build
  *after* the version bump or the site will show the previous one.

Done since this list was written: the GitHub repository exists and `pyproject.toml`'s URLs point at
it, `~/.pypirc` is in place, and `vue-i18n-python` was still unregistered on PyPI when checked
(2026-08-13, HTTP 404).

---

## The checker reads `.vue` and `.ts` with a regular expression

`vue_i18n/check/` parses Python with `ast`, which is exact. For `.vue`, `.ts` and `.js` it pattern-
matches `t(`/`$t(`/`tc(`/`te(` calls, because parsing them properly would mean a JavaScript
toolchain and there is none in this repository. Block and line comments are blanked first and a
template literal carrying `${}` is treated as computed, so the common false positives are handled —
but a key assembled across lines, or a call written unusually, is missed silently.

Every such finding is flagged `approximate` in the API and says "found by pattern" in the CLI, so
the limit is disclosed rather than hidden. Making it exact needs a real parser for those files,
which is a bigger decision than this gap.

---

## No `.po` bridge

The documentation's [rationale page](docs/guide/rationale.md) names the `.po` ecosystem as the one
real reason to prefer `gettext`: Weblate, Crowdin and Poedit read JSON, but `.po` carries translator
comments, message context and fuzzy flags that JSON does not. A converter in both directions would
close it. Not written, and not obviously in scope.

---

## Decisions waiting on the owner

- Whether the plural-index clamp should stay or become a raise (above).
- Whether `te()`, `tm()` and `rt()` belong here (above).
- Whether to fix the two reproduced upstream bugs locally, or wait for upstream. Fixing them makes
  this port disagree with the browser, which is the thing it exists not to do; waiting means shipping
  known-wrong behaviour. Currently: reproduced, documented, reported.
- Whether to tell intlify about the port, now that two issues are open under the same account.
