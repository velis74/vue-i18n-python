# i18n-united

One translation file format, two reference runtimes, and plural rules that are actually correct.

The format is **vue-i18n's** — ordinary `en.json` / `sl.json` message resources, with `{named}`
placeholders, `a | b | c` plurals, `@:linked` messages and `@.upper:` modifiers. Nothing here asks
you to migrate a file or learn a new syntax; `vue-i18n-extract` and the rest of the toolchain keep
working exactly as they do now.

Two things are added on top:

**A Python runtime that reads the same files.** `i18n_united` is a port of `@intlify/message-compiler`
and `@intlify/core-base`, so a message resource written for a Vue front end renders identically in a
Python back end — same tokenizer, same parser, same resolution and fallback rules, same output.
Proven by a conformance corpus that both ports read verbatim.

**Real CLDR plural rules, shared by both ports.** This is the part that is not merely a port. Out of
the box, vue-i18n's plural rule is locale-independent and clamps to index 2:

```
sl  0→nič  1→ena  2→dve  3→dve  5→dve  101→dve  102→dve
en  0→nič  1→ena  2→dve  3→dve  5→dve  101→dve  102→dve
```

Slots 3 and 4 are unreachable, in every language. Any application needing more than three forms —
which is most Slavic, Celtic and Semitic languages — has to hand-write a `pluralRules` function and
pass it to `createI18n`. `i18n-united` ships those rules instead, generated from CLDR into both
languages from one source, so the two runtimes cannot disagree about which form a given `n` selects.

## Status

Early. See `PROGRESS.md` for what exists and what does not.

## License

MIT
