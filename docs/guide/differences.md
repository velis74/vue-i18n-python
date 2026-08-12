# Differences from vue-i18n

The goal is that there are none. These are the ones there are, all of them, in two groups: what the
platform forces, and what was chosen. Every chosen one is asserted by a test in the repository, so
it cannot widen without someone noticing.

State as of **vue-i18n 11.4.8**.

## Forced by the platform

These are not decisions and cannot be fixed.

| | |
|---|---|
| **Source offsets count UTF-16 units** | JavaScript strings are UTF-16; Python's are code points. Reported offsets and columns count units so a location means the same thing in both. Only diagnostics are affected. |
| **`d()` and `n()` do not match `Intl` exactly** | `Intl` and `babel` carry different CLDR data versions. The formats resolve identically; the rendered digits and month names may differ. No test pins them. |
| **`part=True` is refused** | `formatToParts` has no babel counterpart. It raises rather than returning an approximation. |
| **Some `Intl` options are ignored** | `signDisplay`, `unit`, `roundingMode`, `calendar`, `hourCycle` and others have nowhere to land in babel. `unsupported_number_options()` and `unsupported_datetime_options()` tell you which, so you can ask rather than discover. |
| **Large integers stay exact** | A JavaScript number is a double; past 2^53 it is not the integer you wrote. A Python `int` is exact, and this prints what it was given rather than discarding precision. A Python `float` follows JavaScript, because there the precision really is gone. |

## Chosen

These could have gone the other way.

### A malformed `\U` escape yields U+FFFD instead of raising

`{'\U110000'}` names a code point past the last one. Upstream's `String.fromCodePoint` throws a
`RangeError`, so no message is produced at all and the whole file fails to load. This substitutes
U+FFFD — the same thing upstream already does for a lone surrogate — so one malformed escape cannot
take down a catalogue.

### Message keys cannot reach Python attributes

Upstream's `resolveWithKeyValue` is a plain property read, so `resolveWithKeyValue({}, 'constructor')`
returns the `Object` constructor and `'__proto__'` returns the prototype. The Python equivalent would
be `getattr`, which resolves a message key into `__class__` and everything reachable from it. This
returns `None` for those names. Not reproducing that is a security decision, not an oversight.

### The defaults are what a vue-i18n application actually runs with

`@intlify/core-base` defaults to a flat key resolver and a simple fallback walker, then expects
`@intlify/core` to register the real ones. There is no separate core package here, so the defaults
are the registered ones: nested path resolution and the full fallback chain. Pass the others
explicitly if you want them.

The same applies to the message compiler, which core-base leaves unset so a Vue build can
pre-compile every message and drop the compiler from the bundle. There is no bundle here.

### Warnings go through Python's `warnings` module

Under the `I18nWarning` category, so `warnings.simplefilter("error", I18nWarning)` turns missing
keys into test failures. The `on_warn` option still exists and still overrides.

### An out-of-range plural index clamps rather than raising

**This one is not settled.** A rule that returns an index past the last form makes vue-i18n read
`undefined` and throw `UNEXPECTED_RETURN_TYPE`. This clamps to the last form instead.

Clamping is friendlier, and it is the direction upstream moved in v12. But the throw is what tells a
developer their rule is wrong, and a real hand-written south-Slavic rule does exactly this for a
four-form Slovene message — so clamping means a bug that crashes the browser renders quietly on the
server. See [plural rules](/guide/plurals).

## Not differences, but gaps

`escape_parameter` escapes interpolated values but does not yet apply upstream's
`sanitizeTranslatedHtml` to the rendered result. Enabling it warns once saying exactly that. The
option is off by default. `GAPS.md` in the repository is the full list of what is knowingly missing.

## Bugs reproduced on purpose

Three upstream behaviours are wrong and are reproduced anyway, because a back end that silently
disagrees with the front end is worse than one that matches it. All three are reported upstream:

- [#2562](https://github.com/intlify/vue-i18n/issues/2562) — the fallback chain cache ignores a
  changed `fallback_locale`
- [#2563](https://github.com/intlify/vue-i18n/issues/2563) — `fallback_with_simple` reads a map's
  keys instead of its values
- one security-relevant issue, reported privately, not described here until it is fixed

If upstream fixes them, this follows and the differences disappear.
