# How it is verified

A port can claim to match the original, or it can be checked against it. This one is checked, on
every test run, against recordings of the real thing.

## The corpora

Each file records what upstream produced for a set of inputs. Nothing in them is written by hand.

| corpus | what it records | cases |
|---|---|---|
| `translate.json` | `translate()` calls against `@intlify/core-base` itself | 59 |
| `render.json` | messages rendered end to end by real `vue-i18n` | 74 |
| `compile.json` | ASTs, error codes, error messages and source locations | 128 |
| `resolve.json` | key-path resolutions, including the awkward ones | 200 |
| `fallback.json` | fallback chains, both walkers | 374 |
| `display.json` | values through JavaScript's `String()` semantics | 1612 |
| `plurals.json` | the opt-in CLDR rules, cross-checked against `Intl.PluralRules` | 4180 |

`translate.json` is the one that matters most: it exercises the whole library through the entry
point an application actually uses — argument parsing, the fallback walk, resolution, compilation,
interpolation, linked messages and the missing-key path, all at once.

## Recorded, never hand-authored

Every corpus is produced by a generator under `scripts/conformance/` that runs upstream and writes
down what came back. Two of them run vue-i18n as an installed package; the rest run its TypeScript
sources, bundled straight from the pinned submodule with esbuild.

This distinction is the point. A hand-written expectation tests the implementation against its
author's belief about the original — which is the same belief that produced the implementation. A
recording tests it against the original.

Each corpus names the version that produced it, and the generators read that version from whatever
actually ran rather than from a constant someone might forget to update.

## What the corpora cannot do

They record what vue-i18n **does**, not what it is **supposed** to do. Where upstream has a bug, the
port reproduces it and the corpus agrees enthusiastically. Three such bugs are known and
[documented](/guide/differences); upstream's own test suite, which encodes intent rather than
behaviour, is not yet ported.

They also cannot pin what the two languages cannot agree on: `d()` and `n()` output, where `Intl`
and `babel` carry different CLDR data, and integers past 2^53. Those are deliberately left
unrecorded rather than pinned to a value that would be wrong on one side.

## Reproducing it

```sh
git submodule update --init                    # upstream, at the pinned release
./scripts/conformance/bundle-upstream.sh       # bundle its sources with esbuild
node scripts/conformance/generate_translate_corpus.mjs
# ... and the other generators; scripts/conformance/README.md lists them

python -m pytest vue_i18n/ -q
```

If a regenerated corpus differs from the committed one, upstream changed observable behaviour. That
is a thing to read, not to overwrite.
