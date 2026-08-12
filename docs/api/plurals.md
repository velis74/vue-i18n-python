# vue_i18n.plurals

CLDR-derived plural rules, ready to pass as `plural_rules`.

**This is not part of the port.** Nothing in the runtime reaches for it. It exists because a caller
who wants correct Slavic plurals needs *something* to pass, and hand-writing that rule is what
people currently do.

::: danger Read this before using it
If your Vue front end already has a hand-written `pluralRules`, **port that rule instead**. This
module is a different rule, not a better spelling of yours, and using one on each end reintroduces
the disagreement this library exists to remove. See [plural rules](/guide/plurals).
:::

## Using it

```python
from vue_i18n import create_core_context
from vue_i18n.plurals import rule_for

ctx = create_core_context(
    locale="sl",
    fallback_locale="en",
    messages=messages,
    plural_rules={"sl": rule_for("sl"), "hr": rule_for("hr")},
)
```

`rule_for(locale)` returns a `(choice, choices_length) -> index` callable — the same shape
`plural_rules` takes and the same shape vue-i18n's `pluralRules` takes.

## The model

**Categories.** CLDR gives each locale a set: `sl` has `one`, `two`, `few`, `other`; `en` has `one`
and `other`; `ja` has only `other`. Data is CLDR 48, vendored in the repository and covering 224
locales.

**An explicit `zero`.** CLDR has no `zero` for most locales — for `sl`, zero is plain `other`. But a
message that opens with "ni povezav" wants one, so this adds `zero` as an extra category that wins
at exactly `n == 0` when the message supplies a form for it.

**A ladder.** A message may carry fewer forms than the locale has categories. Each locale has a
precedence list saying which categories earn a form first; the ladder for a message with *k* forms
is the first *k* of that list, re-sorted into the order a message writes them in. For `sl`:

| forms | means |
|---|---|
| 2 | `one`, `other` |
| 3 | `zero`, `one`, `other` |
| 4 | `zero`, `one`, `two`, `other` |
| 5 | `zero`, `one`, `two`, `few`, `other` |

**Falling forward.** A count whose category the ladder does not carry moves toward `other` until it
finds one that is there. `other` heads every precedence list, so the walk always terminates and the
rule is total — it can never return an index that does not exist.

## Other entry points

```python
from vue_i18n.plurals import plural_category, plural_index, plural_ladder, resolve_locale

plural_category("sl", 3)        # 'few'  - the plain CLDR category, no ladder involved
plural_index("sl", 3, 5)        # 3      - the form index for 3 in a five-form message
plural_ladder("sl", 3)          # ('zero', 'one', 'other')
resolve_locale("sl-SI")         # 'sl'   - how a tag is widened to one CLDR has rules for
```

## Verification

The generated rules are cross-checked against `Intl.PluralRules` in Node — an independent
implementation of the same CLDR data — over 167 097 cases across 219 locales, with no mismatches.
That covers the plain categories; the `zero` extension and the ladder are this project's own and are
covered by their own tests.

`conformance/plurals.json` records the resulting table.

## Regenerating

```sh
python scripts/generate_plurals.py
```

Reads `cldr/plurals.json` and rewrites `vue_i18n/plurals/_generated.py`. A test fails if the checked-in
file is not what the generator produces, so a hand-edit cannot survive.
