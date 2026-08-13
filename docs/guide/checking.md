# Checking your messages

`t("cart.emty")` does not fail. It returns the key, renders `cart.emty` on the page, and waits for a
customer to find it. This checks for that before it ships.

```sh
python -m vue_i18n.check locales/ --source backend/ --source frontend/src
```

```
error  locales/en.json            badlink: @:cart.coun resolves in no locale (at character 7 of the message)
warn   locales/sl.json            cart.none: in en, not in sl
error  backend/views.py:3:24      'cart.emty' is not in en
note   backend/views.py:4:24      key is computed at runtime, so it was not checked
error  frontend/src/Cart.vue:3:9  'cart.emty' is not in en (found by pattern, so check it by hand)

3 errors, 1 warning, 1 unchecked
```

Note which line is the warning: `sl` is behind on a key, and that does not fail the build. The
typo does. [Why](#the-asymmetry-that-makes-it-usable-in-ci).

::: tip This is not part of the port
vue-i18n has no such command, and nothing here changes what a message renders to — it only reads.
It lives in this package because following an `@:linked` reference means *parsing the message*, and
the parser that agrees with vue-i18n about what a link is happens to be the one in this package.
:::

## What it checks

**Without reading any code**, from the message files alone:

| | |
|---|---|
| `does-not-compile` | the message is run through the real compiler; a stray `}` or `@.` is an error, not a surprise at render time |
| `broken-link` | `@:some.key` resolves in no locale at all |
| `link-needs-fallback` | the link resolves, but only in another locale — fine if your chain covers it, worth knowing if not |
| `unknown-modifier` | `@.shout:key` is not one of `upper`, `lower`, `capitalize`, so it renders the message unchanged unless you pass it |
| `unreachable-plural-form` | more forms than the built-in rule can reach — see [plural rules](/guide/plurals) |
| `missing-key` | a translated locale is behind the base one — a **warning**, see below |
| `extra-key` | a key a translation has and the base locale does not — an **error**, see below |

**With `--source`**, additionally:

| | |
|---|---|
| `unknown-key` | the code asks for a key the **base locale** does not define |
| `unused-key` | a message nothing asks for |
| `dynamic-key` | the key is built at runtime, so it was not checked — counted, never guessed at |

## The asymmetry that makes it usable in CI

**A key missing from the source language fails the build. The same key untranslated fails nothing.**

That is the whole severity model, and it is deliberate. A key your code uses and your source
language does not define is a bug in the commit in front of you. The same key not yet translated
into Spanish is a translation in flight — and a build that blocks on it gets switched off within a
week, after which it catches nothing at all.

| situation | kind | severity | build |
|---|---|---|---|
| code uses `cart.promo`, `en` has no such key | `unknown-key` | error | **fails** |
| `sl` has `cart.promo`, `en` does not | `extra-key` | error | **fails** |
| `en` has `cart.count`, `sl` does not yet | `missing-key` | warning | passes |
| the key is computed at runtime | `dynamic-key` | note | passes |

`--base-locale` names the source language; it is `en` by default. `--strict` makes warnings fatal
too, if you have reached the point where untranslated keys should block a release.

An `unknown-key` says where the key *was* found, if anywhere:

```
error  app/views.py:3:27  'cart.promo' is not in en (found in sl)
```

which is a different fix from a plain typo, and worth the words.

## In a pipeline

```yaml
- run: pip install vue-i18n-python
- run: python -m vue_i18n.check locales/ --source backend/ --source frontend/src --format github
```

`--format github` emits workflow commands, so each finding becomes an annotation on the diff rather
than a line in a log nobody opens. `--format json` gives you `problems` and `counts` to branch on.

Exit codes are the contract:

| | |
|---|---|
| `0` | no errors — warnings and notes may still have been printed |
| `1` | errors, or warnings with `--strict` |
| `2` | the checker could not run: a message file that will not parse, a `--base-locale` that is not there, no message files at all |

Two is separate from one on purpose: a mistyped path must never read as a green build.

## Both ends of the same project

`.py` is parsed with Python's `ast`, so a call is a call. `.vue`, `.ts` and `.js` are matched with a
regular expression, which is approximate and labelled as such on every finding — parsing them
properly would mean shipping a JavaScript toolchain, and this package has none.

Approximate is still more than `xgettext` manages, since it cannot read `.vue` at all. Comments are
skipped, `` `item.${kind}` `` is recognised as computed rather than reported as a missing key, and
`format(` is not mistaken for a `t(` call.

## From Python

The command is a wrapper; the checks are ordinary functions, which is what you want in a test:

```python
from vue_i18n.check import check_messages

def test_translations_are_consistent():
    report = check_messages({"en": en, "sl": sl}, base_locale="en")
    assert not report.errors, "\n".join(str(p) for p in report.problems)
```

`check_messages` takes resources, not paths — the library still never opens a file. Each `Problem`
carries `severity`, `kind`, `key`, `locale` and, where it is honestly known, `file`, `line` and
`column`.

::: warning `line` is a file coordinate, and message problems have none
A finding from parsing a message reports `in_message` — a column inside the message text — and
leaves `line` and `column` unset. Mapping that back to a line in a JSON file would need a
position-aware JSON parser, and printing it as `file:1:7` would send you to the wrong place.
:::

## Options

| | |
|---|---|
| `--source PATH` | code to scan; repeatable |
| `--base-locale LOCALE` | the source language, default `en`; keys missing from it fail, keys missing from the others do not |
| `--no-unused` | skip `unused-key` |
| `--quiet` | errors only |
| `--strict` | exit non-zero on warnings too |
| `--format text\|json\|github` | output format, default `text` |

Message files are read as JSON. YAML works when PyYAML happens to be installed — it is not a
dependency and not an extra, because the library itself still takes messages as an object.
