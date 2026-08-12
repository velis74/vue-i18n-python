# create_core_context

Builds the context every other call is made against. Build it once and reuse it.

```python
from vue_i18n import create_core_context

ctx = create_core_context(
    locale="sl",
    fallback_locale="en",
    messages={"sl": {...}, "en": {...}},
)
```

Every argument is keyword-only.

## Messages and locale

| | default | |
|---|---|---|
| `locale` | `"en-US"` | The current locale, or a callable returning one (vue-i18n's `LocaleDetector`). |
| `fallback_locale` | the locale | A string, a list, a per-locale map, or `False`. See [fallback locales](/guide/fallback). |
| `messages` | `{locale: {}}` | `{locale: {key: message}}`, nested or flat. |
| `datetime_formats` | `{locale: {}}` | Named `Intl.DateTimeFormat` option objects, per locale. |
| `number_formats` | `{locale: {}}` | Named `Intl.NumberFormat` option objects, per locale. |

An option of the wrong type falls back to its default rather than raising. A translation layer that
refuses to start because one option was misspelled is worse than one that warns and translates.

## Missing keys and warnings

| | default | |
|---|---|---|
| `missing` | `None` | `(ctx, locale, key, type) -> str | None`. A returned string is used as the translation; anything else falls through to the key. |
| `missing_warn` | `True` | `bool`, or a compiled regex to narrow it to matching keys. |
| `fallback_warn` | `True` | Same, for falling back to another locale. |
| `fallback_format` | `False` | When set, an unresolved key is rendered as a message rather than returned raw. |
| `unresolving` | `False` | When set, an unresolved key returns `NOT_RESOLVED` (`-1`) instead of the key. |
| `on_warn` | Python's `warnings` | `(message) -> None`. Overrides the default channel entirely. |

## Rendering

| | default | |
|---|---|---|
| `modifiers` | built-ins | Extra linked-message modifiers. `upper`, `lower` and `capitalize` are always present and win on a name clash, as upstream. |
| `plural_rules` | `{}` | `{locale: (choice, choices_length) -> index}`. See [plural rules](/guide/plurals). |
| `post_translation` | `None` | `(result, key) -> result`, applied to every translation. |
| `processor` | `None` | Custom `type` / `interpolate` / `normalize`, for building something other than a string. |
| `escape_parameter` | `False` | HTML-escape interpolated values. Read the caveat in [differences](/guide/differences) before enabling. |

## Seams

Rarely needed, and here because upstream has them.

| | default | |
|---|---|---|
| `message_compiler` | the built-in | `(source, ctx) -> message function`. |
| `message_resolver` | nested paths | `(messages, key) -> value`. Pass `resolve_with_key_value` for flat keys only. |
| `locale_fallbacker` | `fallback_with_locale_chain` | The fallback walker. |
| `fallback_context` | `None` | Another context to fall back to, vue-i18n's global-scope mechanism. |
| `version` | the package version | Reported as `ctx.version`. |

## Attributes worth knowing

```python
ctx.current_locale       # `locale` resolved to a string, calling the detector if it is one
ctx.messages             # the resource, mutable - editing it takes effect on the next call
ctx.cid                  # a per-context id, as upstream
```

## update_fallback_locale

```python
from vue_i18n import update_fallback_locale

update_fallback_locale(ctx, "sl", {"sl": ["hr", "en"], "default": ["en"]})
```

Changes the fallback and clears the chain cache. Assigning `ctx.fallback_locale` directly does not
clear it, and the next lookup answers with the chain computed from the old value — a sharp edge
inherited from upstream and reported as
[intlify/vue-i18n#2562](https://github.com/intlify/vue-i18n/issues/2562).
