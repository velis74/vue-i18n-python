# Public issue — `fallbackWithSimple` and a map-shaped `fallbackLocale`

Status: **filed 2026-08-12** as https://github.com/intlify/vue-i18n/issues/2563

Prior-art check (authenticated `gh`, issues and PRs, open and closed): no existing report.
Queries run: `fallbackWithSimple`, `fallbackLocale object`, `fallback default key`,
`Object.keys fallback`, `fallbackLocale keys`. The only plausibly related hit, #1280 "Make
fallback locale iterable", is a userland feature request and unrelated.

Reproduction: `upstream-reports/repro-3-fallback-simple-map.mjs`.

---

**Title:** `fallbackWithSimple` reads a map `fallbackLocale`'s keys instead of its values

I'm building a Python port of this library, which meant porting both fallbackers and testing them
against the real ones — and I have found this. It is low severity and it may well be intentional, so
the report is really a question: is the behaviour wrong, or is the type?

`fallbackWithSimple` (`packages/core-base/src/fallbacker.ts`, lines 87–105) accepts a
`FallbackLocale`, and that type includes the map form:

```ts
export type FallbackLocale = Locale | Locale[] | { [locale in string]: Locale[] } | false
```

For the map case it does this (line 99):

```ts
...(isArray(fallback)
  ? fallback
  : isObject(fallback)
    ? Object.keys(fallback)      // <-- keys, not values
    : ...)
```

So the map's **keys** become the fallback chain. The locales the configuration actually names are
never consulted, and the literal string `"default"` is treated as a locale.

Reproduction, `@intlify/core-base@11.4.8`, Node 26, with
`fallbackLocale = { 'sl-SI': ['sl','en'], sl: ['en'], default: ['en'] }`:

| start | `fallbackWithSimple` | `fallbackWithLocaleChain` |
|---|---|---|
| `sl-SI` | `["sl-SI","sl","default"]` | `["sl-SI","sl","en"]` |
| `sl` | `["sl","sl-SI","default"]` | `["sl","en"]` |
| `de` | `["de","sl-SI","sl","default"]` | `["de","en"]` |

Three things go wrong at once: `"default"` is emitted as a locale name; starting from `de` pulls in
`sl-SI` and `sl`, which the configuration never associated with `de`; and `en` — the only locale the
map actually points at — never appears.

**Why it is mostly invisible, and where it is not.** Every shipped entry point registers
`fallbackWithLocaleChain` (`packages/core/src/index.ts`, `packages/vue-i18n/src/index.ts`,
`packages/petite-vue-i18n/src/index.ts`), so a `vue-i18n` application never reaches this. It is
reached by anyone building directly on `@intlify/core-base` and relying on the default in
`createCoreContext` (line 563, `_fallbacker || fallbackWithSimple`). That is not hypothetical: it is
how my port behaved until I changed its default, and it is why I noticed.

**The question.** If "simple" is meant to be deliberately naive, then the behaviour is fine and the
*signature* is wrong — it should not accept a shape it cannot honour, or the doc comment should say
that a map contributes its keys. If the signature is right, then the implementation should follow
the values, and probably resolve `default` the way `fallbackWithLocaleChain` does.

Either is a small change; I did not want to send a PR before knowing which one you consider correct.
