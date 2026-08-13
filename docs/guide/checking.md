# Checking your messages

`t("cart.emty")` does not fail. It returns the key, renders `cart.emty` on the page, and waits for a
customer to find it. This checks for that before it ships.

```sh
python -m vue_i18n.check locales/ --source backend/ --source frontend/src
```

```
error  locales/en.json  badlink: @:cart.coun resolves in no locale (at character 7 of the message)
warn   locales/sl.json  cart.none: in en, not in sl
error  views.py:4:24    'cart.emty' is in no locale
note   views.py:5:24    key is computed at runtime, so it was not checked
error  Cart.vue:3:9     'cart.emty' is in no locale (found by pattern, so check it by hand)

3 errors, 1 warning, 1 unchecked
```

Exit status is 1 when there are errors, so it drops into CI as it is.

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
| `missing-key` / `extra-key` | each locale against the base one |

**With `--source`**, additionally:

| | |
|---|---|
| `unknown-key` | the code asks for a key no locale defines |
| `unused-key` | a message nothing asks for |
| `dynamic-key` | the key is built at runtime, so it was not checked — counted, never guessed at |

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
| `--base-locale LOCALE` | the locale others are compared against, default `en` |
| `--no-unused` | skip `unused-key` |
| `--quiet` | errors only |

Message files are read as JSON. YAML works when PyYAML happens to be installed — it is not a
dependency and not an extra, because the library itself still takes messages as an object.
