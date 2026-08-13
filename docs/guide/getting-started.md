# Getting started

## Installation

```sh
pip install vue-i18n-python
```

The library itself has **no dependencies**. A message is parsed and rendered by code in the package.

`d()` and `n()` need CLDR date and number data, which Python does not ship, so they are behind an
extra:

```sh
pip install "vue-i18n-python[intl]"     # adds babel, for d() and n()
```

There is no extra for message files, in any format. Like vue-i18n itself, this library takes
messages as an already-parsed object — vue-i18n leaves `.json` and `.yaml` to a bundler plugin, and
here it is your `json.load` or `yaml.safe_load`.

## Your first translation

Point it at the message files your front end already uses.

```python
import json
from vue_i18n import create_core_context, translate

messages = {
    "es": json.load(open("locales/es.json", encoding="utf-8")),
    "ar": json.load(open("locales/ar.json", encoding="utf-8")),
    "en": json.load(open("locales/en.json", encoding="utf-8")),
}

ctx = create_core_context(locale="es", fallback_locale="en", messages=messages)

translate(ctx, "hello", {"name": "Ana"})
```

A context is built once and reused. It holds the messages, the current locale, the fallback chain
and the policies for what happens when a key is missing — the same things `createI18n` holds in a
Vue application.

## The call shapes

`translate()` accepts the same argument shapes as vue-i18n's `t()`, and the rules are positional:

```python
translate(ctx, "hello")                          # no values
translate(ctx, "hello", {"name": "Ana"})        # a mapping is named values
translate(ctx, "positional", ["first", "second"])  # a sequence is positional values, {0} and {1}
translate(ctx, "trips", 5)                       # a number is a plural count
translate(ctx, "missing", "a default")           # a string is a default message
translate(ctx, "hello", {"name": "Ana"}, {"locale": "en"})   # options in the third position
```

The third argument, when it is a mapping, is options rather than values: `locale`, `plural`,
`default`, `missing_warn`, `fallback_warn`, `escape_parameter`.

## Option names

Every option is vue-i18n's, in snake_case. `fallbackLocale` is `fallback_locale`, `missingWarn` is
`missing_warn`, `postTranslation` is `post_translation`. The concepts and their defaults are
unchanged, so the vue-i18n documentation describes them accurately.

## What a missing key does

It renders as the key, and warns:

```python
translate(ctx, "not.in.the.file")     # 'not.in.the.file'
```

That is upstream's behaviour, and it is deliberate — an untranslated string should be visible in the
interface rather than leaving a hole in a sentence. Warnings go through Python's `warnings` module
under the `I18nWarning` category, so you can silence or escalate them the ordinary way:

```python
import warnings
from vue_i18n import I18nWarning

warnings.simplefilter("error", I18nWarning)      # turn missing keys into test failures
```

If you would rather handle it yourself, pass `missing`:

```python
def missing(ctx, locale, key, type_):
    logger.warning("missing translation %s in %s", key, locale)
    return None          # return a string to use it as the translation

ctx = create_core_context(..., missing=missing, missing_warn=False)
```

## Next

- [Message format](/guide/message-format) — what you can write in a message
- [Plural rules](/guide/plurals) — read this one if you translate into a Slavic language
- [Differences from vue-i18n](/guide/differences) — where this does not match, and why
