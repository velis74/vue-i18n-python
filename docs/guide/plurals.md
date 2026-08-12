# Plural rules

Read this page if you translate into Slovenian, Croatian, Serbian, Bosnian, Polish, Czech, Russian,
Welsh, Arabic, or anything else with more than two plural forms.

## The short version

**If your Vue application already passes `pluralRules` to `createI18n`, transcribe the same rule
here and the two ends will agree.** That is the whole story, and it is the recommended path.

If it does not, both ends use vue-i18n's default rule, which cannot reach a fourth or fifth form in
any language — and this port reproduces that faithfully rather than improving on it.

## How a form is chosen

A plural rule is a function:

```
(choice, choices_length) -> index
```

`choice` is the count, `choices_length` is how many forms the message supplies, and the return value
is which form to use. Exactly the same signature as in JavaScript, which is what makes a rule
transcribe line for line.

## The default rule

With no rule of your own, vue-i18n uses this — and so does this port:

```python
def plural_default(choice, choices_length):
    choice = abs(choice)
    if choices_length == 2:
        return 0 if choice == 1 else 1
    return min(choice, 2)
```

It ignores the locale entirely. Two forms mean singular/plural; three or more clamp at index 2. A
message with four or five forms can never reach the fourth or the fifth:

```json
{ "trips": "ni povezav | ena povezava | dve povezavi | {count} povezave | {count} povezav" }
```

| count | default rule renders |
|---|---|
| 0 | ni povezav |
| 1 | ena povezava |
| 2 | dve povezavi |
| 3 | dve povezavi |
| 5 | dve povezavi |
| 105 | dve povezavi |

That is wrong Slovenian, and it is what the browser does too. The port matching it is the point.

## Passing your own rule

```python
def south_slavic(choice, choices_length, _org=None):
    if choices_length == 2:
        return 0 if choice == 1 else 1
    if choices_length == 3:
        return min(choice, 2)
    if choice == 0:
        return 0
    if choice % 100 == 1:
        return 1
    if choice % 100 == 2:
        return 2
    if choice % 100 in (3, 4):
        return 3
    return 4

ctx = create_core_context(
    locale="sl",
    fallback_locale="en",
    messages=messages,
    plural_rules={"sl": south_slavic},
)
```

| count | with the rule above |
|---|---|
| 0 | ni povezav |
| 1 | ena povezava |
| 2 | dve povezavi |
| 3 | 3 povezave |
| 5 | 5 povezav |
| 101 | ena povezava |
| 103 | 103 povezave |

The third parameter is the built-in rule, which upstream passes so a custom rule can delegate to it.
A two-argument rule works too.

::: warning Make your rule total
A rule that returns an index past the last form crashes in the browser — vue-i18n reads `undefined`
and raises `UNEXPECTED_RETURN_TYPE`. The rule above returns 4, so it requires messages with five
forms; give a Slovene message only four and the page breaks.

The cheap insurance is to clamp on the way out:

```python
    return min(index, choices_length - 1)
```

which degrades to the last available form instead of failing.
:::

## The CLDR module

If you would rather not hand-write the rule, `vue_i18n.plurals` carries one derived from CLDR:

```python
from vue_i18n.plurals import rule_for

ctx = create_core_context(..., plural_rules={"sl": rule_for("sl")})
```

It covers 224 locales from CLDR 48, adds an explicit `zero` form that CLDR does not have, and copes
with a message carrying fewer forms than the locale has categories by dropping categories in a
defined order.

::: danger It will not match a hand-written rule
This is a *different* rule, not a better spelling of yours. At three forms it gives
`zero, one, other` where a typical hand-written south-Slavic rule gives the same, but at four it
gives `zero, one, two, other` where pure CLDR would give `one, two, few, other`.

**If your front end has a rule, port that one.** Using this module on one end and a hand-written rule
on the other reintroduces exactly the disagreement this library exists to remove.
:::

It is opt-in. Nothing in the runtime reaches for it unless you pass it.

## Why the default is like this

vue-i18n 12 changed it: unreleased at the time of writing, it resolves plurals through
`Intl.PluralRules` when no custom rule is given. It handles the case where a message has exactly as
many forms as the locale has CLDR categories, and falls back to the old clamp when it has more — so
a five-form Slovene message, which needs an explicit zero, is still not reachable.

This port tracks the released line and therefore the old behaviour. When 12 is released and the pin
moves, this page changes with it.
