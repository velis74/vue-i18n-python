# API Reference

Everything ordinary use needs is on the package root:

```python
from vue_i18n import create_core_context, translate, datetime, number
```

| | |
|---|---|
| [`create_core_context`](/api/context) | build the context everything else is called against |
| [`translate`](/api/translate) | translate a key — vue-i18n's `t()` |
| [`datetime`, `number`](/api/datetime-number) | format a date or a number — `d()` and `n()` |
| [`vue_i18n.plurals`](/api/plurals) | the opt-in CLDR plural rules |

## Everything exported

```python
from vue_i18n import (
    create_core_context,        # build a context
    CoreContext,                # its type
    translate,                  # t()
    datetime,                   # d()
    number,                     # n()
    update_fallback_locale,     # change fallback_locale safely
    fallback_with_locale_chain, # the default fallback walker
    fallback_with_simple,       # the other one
    NOT_RESOLVED,               # what unresolving=True returns
    I18nWarning,                # the warning category
    create_parser,              # parse a message without rendering it
    CompileError,               # what a malformed message raises
)
```

## Naming

Names are vue-i18n's, in snake_case, and the concepts are unchanged:

| vue-i18n | here |
|---|---|
| `createI18n` / `createCoreContext` | `create_core_context` |
| `t` / `translate` | `translate` |
| `d` | `datetime` |
| `n` | `number` |
| `fallbackLocale` | `fallback_locale` |
| `missingWarn`, `fallbackWarn` | `missing_warn`, `fallback_warn` |
| `pluralRules` | `plural_rules` |
| `postTranslation` | `post_translation` |
| `escapeParameter` | `escape_parameter` |

`d` and `n` are spelled out because a single letter is not a name in Python. Import them under the
short name if you prefer the symmetry with the front end:

```python
from vue_i18n import datetime as d, number as n
```
