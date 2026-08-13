# translate

vue-i18n's `t()`. Takes a context and a key, returns a string.

```python
from vue_i18n import translate

translate(ctx, "hello", {"name": "Ana"})     # 'Hola Ana'
```

## Call shapes

The rules are positional and untyped, exactly as upstream's are. The **second** argument is read by
its type:

| second argument | means |
|---|---|
| a mapping | named values — `{name}` |
| a sequence | positional values — `{0}`, `{1}` |
| a number | a plural count |
| a string | a default message, used when the key resolves to nothing |

The **third** argument repeats the number and string rules, and a mapping there is *options* rather
than values:

```python
translate(ctx, "trips", {"count": 3}, 3)                  # named values and a count
translate(ctx, "hello", {"name": "Ana"}, {"locale": "en"})   # a per-call locale
translate(ctx, "hello", {}, {"default": "fallback text"})
```

Options accepted in that position: `locale`, `plural`, `default`, `missing_warn`, `fallback_warn`,
`escape_parameter`, `resolved_message`.

::: tip An empty mapping is not "no named values"
`translate(ctx, "key", {})` is the same as `translate(ctx, "key")`. Upstream ignores an empty
mapping so that it does not shadow the plural argument, and so does this.
:::

## What it returns

A string, normally.

| situation | result |
|---|---|
| key resolves | the rendered message |
| key missing | the key itself, and a warning |
| key missing, `missing` handler returns a string | that string |
| key missing, `unresolving=True` | `NOT_RESOLVED`, which is `-1` |
| message fails to compile | the message source, so the broken text is visible |

Returning the key rather than an empty string is deliberate: an untranslated string should be
visible in the interface rather than leaving a hole in a sentence.

## Errors

`translate` does not raise for a missing key or a malformed message — both are reported and rendered
as something visible. It raises only for a call it cannot make sense of at all: a first argument that
is neither a string, a number, a compiled message nor an AST raises `CoreErrorCodes.INVALID_ARGUMENT`.

To turn missing keys into failures, escalate the warning:

```python
import warnings
from vue_i18n import I18nWarning

warnings.simplefilter("error", I18nWarning)
```

## Pre-parsing a message

A message can be parsed once and rendered many times, which skips the compiler on each call:

```python
from vue_i18n import create_parser

ast = create_parser().parse("Hola {name}")
translate(ctx, ast, {"name": "Ana"}, {"resolved_message": True})
```

The compilation cache makes this unnecessary in most cases — compiled messages are cached per
`(locale, key, source)`, and including the source means editing a resource takes effect rather than
being served from the cache.
