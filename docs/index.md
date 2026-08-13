---
layout: home

hero:
  name: vue-i18n-python
  text: vue-i18n, in Python
  tagline: One set of translation files. A Vue front end and a Python back end that agree on what they say.
  actions:
    - theme: brand
      text: Get started
      link: /guide/getting-started
    - theme: alt
      text: Why this exists
      link: /guide/rationale
    - theme: alt
      text: API Reference
      link: /api/

features:
  - title: The same files
    details: >
      Ordinary vue-i18n message resources - the en.json and sl.json your front end already loads.
      Named and positional placeholders, pipe plurals, linked messages, modifiers, literals. Nothing
      to migrate, and vue-i18n-extract keeps working.
  - title: The same behaviour
    details: >
      A port, not a reimplementation. The tokenizer, parser, resolver, fallback walk and message
      context are all vue-i18n's, translated to Python - including the parts where vue-i18n is
      arguably wrong, because a back end that quietly disagrees is worse than one that matches.
  - title: Checked, not claimed
    details: >
      Seven conformance corpora, recorded by running real vue-i18n and replayed on every test run.
      59 translate() calls against @intlify/core-base itself, 74 rendered messages, 128 ASTs down to
      their source locations.
  - title: Follows releases
    details: >
      Upstream is a git submodule pinned to the released version being tracked, so which vue-i18n
      this matches is answered by a checkout rather than by a promise. Released versions only, never
      an alpha.
---

## In one screen

```python
import json
from vue_i18n import create_core_context, translate

ctx = create_core_context(
    locale="sl",
    fallback_locale="en",
    messages={
        "sl": json.load(open("locales/sl.json")),
        "en": json.load(open("locales/en.json")),
    },
)

translate(ctx, "hello", {"name": "Jure"})   # 'Zdravo Jure'
translate(ctx, "trips", 5)                  # the plural form for 5
translate(ctx, "nested.deep.key")           # nested keys, as in the browser
```

::: info Unofficial
This is an unofficial port. [vue-i18n](https://github.com/intlify/vue-i18n) is © kazuya kawaguchi
and contributors, MIT licensed. This project is not affiliated with or endorsed by intlify.
:::

::: warning Early
Pre-1.0, and honest about it: nothing here has served a production page yet. The behaviour is
checked against upstream on every test run, which is a different thing from being battle-tested.
1.0 is what the first confirmed production use earns.
:::
