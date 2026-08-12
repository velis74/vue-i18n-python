# Public issue — `fallbackWithLocaleChain` cache

Status: **filed 2026-08-12** as https://github.com/intlify/vue-i18n/issues/2562

Prior-art check (authenticated `gh`, issues *and* PRs, open and closed): no existing report.
Queries: `fallbackLocale cache`, `localeChainCache`, `fallbackWithLocaleChain`, `fallback chain stale`.

---

**Title:** `fallbackWithLocaleChain` caches the chain by start locale only, so a changed `fallbackLocale` is ignored

I'm building a Python port of this library — a faithful one, which means reading `core-base` closely
and recording what it actually does rather than what I assume it does — and I have found this.

`fallbackWithLocaleChain` memoises the computed chain in `context.__localeChainCache`, keyed by the
**start locale alone** (`packages/core-base/src/fallbacker.ts`, lines 135 and 160). The
`fallbackLocale` argument is not part of the key, so a second call with the same start locale and a
*different* `fallbackLocale` receives the first call's answer.

Reproduction, on `@intlify/core-base@11.4.8`, Node 26:

```js
import { fallbackWithLocaleChain } from '@intlify/core-base'

const ctx = {}
fallbackWithLocaleChain(ctx, { sl: ['en'], default: ['en'] }, 'sl')        // ["sl","en"]  ✅
fallbackWithLocaleChain(ctx, { sl: ['de', 'hr'], default: ['de'] }, 'sl')  // ["sl","en"]  ❌
fallbackWithLocaleChain({},  { sl: ['de', 'hr'], default: ['de'] }, 'sl')  // ["sl","de","hr"]
```

The third line shows the correct answer; the second is the stale one.

**Expected:** the chain reflects the `fallbackLocale` that was passed.
**Actual:** it reflects whichever `fallbackLocale` happened to be passed first for that start locale,
for the lifetime of the context.

This is reachable from application code whenever `fallbackLocale` changes at runtime — a language
picker that also changes the fallback order, or a lazily loaded locale set. `updateFallbackLocale`
clears the cache and is presumably why this has not bitten more often, but that puts the correctness
of the cache on the caller remembering to route through a specific function, and
`i18n.global.fallbackLocale = ...` does not.

Two possible fixes, depending on what you consider the contract: include the `fallbackLocale` in the
cache key (a stable stringification, as `generateFormatCacheKey` already does for message formats),
or clear the cache from the `fallbackLocale` setter so the existing key stays valid.

Happy to open a PR for either if you have a preference.
