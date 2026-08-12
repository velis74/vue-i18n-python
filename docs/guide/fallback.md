# Fallback locales

When a key is missing from the current locale, the fallback chain decides where to look next. The
shapes and the walk are vue-i18n's.

## The shapes

```python
create_core_context(locale="sl", fallback_locale="en", ...)          # a single locale
create_core_context(locale="sl", fallback_locale=["hr", "en"], ...)  # in order
create_core_context(locale="sl", fallback_locale=False, ...)         # no fallback at all

create_core_context(                                                 # per-locale, the usual shape
    locale="sl-SI",
    fallback_locale={
        "sl-SI": ["sl", "en"],
        "sl": ["en"],
        "default": ["en"],
    },
    ...
)
```

The map form is the one a multi-language application usually wants: each locale names its own chain,
and `default` catches everything else.

## Implicit region fallback

`sl-SI` falls back to `sl` without you asking. That step is treated as "the same language, spelled
less specifically" rather than as a missing translation, so it does not go through the missing
handler and does not warn.

## Stopping a chain

A `!` suffix ends the walk there:

```python
fallback_locale={"sl-SI": ["sl!"], "default": ["en"]}
```

`sl-SI` then tries `sl` and stops — it never reaches `en`.

## Two walkers

vue-i18n ships two, and so does this:

| | what it does |
|---|---|
| `fallback_with_locale_chain` | the full algorithm: map blocks, `!`, region-to-language, `default`. **The default here.** |
| `fallback_with_simple` | start locale plus whatever `fallback_locale` names, deduplicated. No subtag walking, no `!` |

::: warning `fallback_with_simple` and the map form
Given a map, `fallback_with_simple` contributes the map's **keys**, not its values — so
`{"sl": ["en"], "default": ["en"]}` yields `["sl-SI", "sl", "default"]`, treating the string
`"default"` as a locale and never reaching `en`.

That is upstream's behaviour and it is reproduced here. It is also reported upstream as
[intlify/vue-i18n#2563](https://github.com/intlify/vue-i18n/issues/2563). Use the chain walker,
which is the default, unless you have a specific reason not to.
:::

::: warning A changed `fallback_locale` may be ignored
`fallback_with_locale_chain` caches the computed chain on the context, keyed by the start locale
alone. Change `fallback_locale` and ask again for the same start locale, and you get the first
answer. Call `update_fallback_locale(ctx, locale, fallback)` to change it safely — that clears the
cache.

Upstream behaves the same way; reported as
[intlify/vue-i18n#2562](https://github.com/intlify/vue-i18n/issues/2562).
:::

## Warnings

Falling back warns by default, which is noisy if falling back is normal for you:

```python
create_core_context(..., fallback_warn=False)
```

Both `fallback_warn` and `missing_warn` also accept a compiled regular expression, which narrows the
warning to keys that match it — useful when you want to hear about missing keys in one namespace and
not in another.
