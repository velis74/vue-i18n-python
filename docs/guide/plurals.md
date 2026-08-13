# Plural rules

Read this page if you translate into any language that needs more than two plural forms — Arabic,
Russian, Polish, Czech, Welsh, Slovenian, Croatian, Lithuanian, Irish, Hebrew, Tachelhit, Langi and
many others.

How many a language needs is not a matter of taste. CLDR settles it, and the range is wide:

| language | CLDR categories | |
|---|---|---|
| Chinese, Japanese, Korean, Yoruba, Igbo | 1 | `other` |
| English, German, Swahili, Hausa, Zulu | 2 | `one`, `other` |
| Spanish, French, Portuguese | 3 | `one`, `many`, `other` |
| Langi | 3 | `zero`, `one`, `other` |
| Nama | 3 | `one`, `two`, `other` |
| Russian, Polish, Czech, Ukrainian | 4 | `one`, `few`, `many`, `other` |
| Slovenian | 4 | `one`, `two`, `few`, `other` |
| Arabic, Welsh, Cornish | 6 | `zero`, `one`, `two`, `few`, `many`, `other` |

Slovenian is the example this page keeps coming back to, and not out of local pride: four categories
including a dual, driven by `n mod 100`, make it the compact case where every way a rule can go
wrong is visible at counts small enough to write in a table. Arabic and Welsh are the deep end at
six. Langi and Nama are here because they answer a question the European languages cannot — see
below.

A message written for English carries two forms. Rendered in Arabic by a rule that knows only
"singular or plural", four of those six categories are unreachable. The same message in Polish never
leaves `few`; in Slovenian it sticks on the dual. It is one problem, not a Slavic one.

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
{ "trips": "ni povezav | {count} povezava | {count} povezavi | {count} povezave | {count} povezav" }
```

| count | default rule renders | correct Slovenian |
|---|---|---|
| 0 | ni povezav | ni povezav |
| 1 | 1 povezava | 1 povezava |
| 2 | 2 povezavi | 2 povezavi |
| 3 | 3 **povezavi** | 3 povezave |
| 5 | 5 **povezavi** | 5 povezav |
| 105 | 105 **povezavi** | 105 povezav |

Every count above 2 renders "two connections" — `min(choice, 2)` stops at the third form and stays
there. Nothing about that is specific to Slovenian: any message with more than three forms loses the
fourth onwards in every language, so a Russian, Polish or Arabic message is cut off at exactly the
same place. Arabic simply has the furthest to fall, since three of its six categories sit past the
cut.

That is wrong in all three languages — and it is what the browser does too. The port matching it is
the point: a back end that quietly fixed this would disagree with the page the user is looking at.

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
| 1 | 1 povezava |
| 2 | 2 povezavi |
| 3 | 3 povezave |
| 5 | 5 povezav |
| 101 | 101 povezava |
| 102 | 102 povezavi |
| 103 | 103 povezave |

::: tip Do not hard-code the number into a form
Writing the `one` form as `"ena povezava"` reads better at 1 and is wrong at **101**, which is also
`one` in Slovenian — the message would say "ena povezava" about a hundred and one things. The same
trap catches `"dve povezavi"` at 102. A category is not a count: use `{count}` in every inflected
form and let the rule pick the ending.
:::

### Unless you want both

"ena povezava" at 1 and "101 povezava" at 101 is not a compromise you have to make. A rule receives
the count, not a category, so nothing stops it giving *exactly one* a form of its own:

```python
# ni povezav | ena povezava | {count} povezava | {count} povezavi | {count} povezave | {count} povezav
#      0            1               2                  3                  4                 5

def south_slavic_exact_one(choice, choices_length, _org=None):
    if choices_length < 6:
        return min(choice, choices_length - 1)   # degrade instead of crashing
    if choice == 0:
        return 0
    if choice == 1:
        return 1                                 # the word, only for a real single
    if choice % 100 == 1:
        return 2                                 # 101, 201 - same category, different copy
    if choice % 100 == 2:
        return 3
    if choice % 100 in (3, 4):
        return 4
    return 5
```

| count | renders |
|---|---|
| 0 | ni povezav |
| 1 | **ena povezava** |
| 2 | 2 povezavi |
| 101 | **101 povezava** |
| 102 | 102 povezavi |
| 105 | 105 povezav |

This is the same move as the explicit `zero` the [CLDR module](/api/plurals) adds: a form CLDR has
no category for, because the *copy* wants it even though the *grammar* does not. Rules are not
limited to CLDR's categories — they are limited to the number of forms your message supplies.

The cost is that both ends must agree, so transcribe the same rule into your Vue application. That
is the recommendation at the top of this page, and it does not change here.

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

## What vue-i18n 12 changes

Upstream has already addressed this. vue-i18n 12 — in alpha at the time of writing, not yet released
— resolves through `Intl.PluralRules`, in this order:

```
your custom rule  >  Intl.PluralRules  >  the default rule above
```

So a message with as many forms as the locale has CLDR categories selects correctly: a four-form
Arabic or Slovenian message picks the right one of the four. When a message carries *more* forms
than the locale has categories, it falls back to the clamp, unchanged.

This port tracks the released line, so it has the old behaviour today. When 12 is released the pin
moves, the port follows, and this page changes with it.

**A custom rule stays worth having even then**, for a reason that has nothing to do with version
numbers: CLDR gives almost no language a `zero` category. Ten locales in CLDR 48 have one — Arabic,
Welsh, Cornish, Latvian, Chuvash, Colognian, Prussian, and the two that make the point best because
nobody expects them, **Langi** in Tanzania and **Anii** in Benin and Togo.

Everything else — English, Spanish, Slovenian, Swahili, Russian, Chinese — sends a count of zero to
`other`, because grammatically that is where it belongs. So a message that says "no trips" instead
of "0 trips" cannot be reached through `Intl.PluralRules` in any of them, in vue-i18n 12 or any
version after it. An explicit zero is a decision about your copy rather than about grammar, and it
needs a rule that knows you made it. That is what the first precedence slot is for, and it is why
the recommendation at the top of this page does not change.
