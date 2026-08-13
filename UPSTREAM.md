# Upstream tracking

vue-i18n-python is a port of [vue-i18n](https://github.com/intlify/vue-i18n). This file records exactly
what it was ported from, so that bringing it up to a new vue-i18n release is reading one diff rather
than re-reading the whole library.

## Where the port stands

| | |
|---|---|
| **Behavioural baseline** | **v11.4.8** — commit `de2393bae16676a8a7c293bb493415e3085a521a` |
| Sources read from | `main` at `efeda9ec1bc53912cc29a8fbb7f1c0928ddf093e` (12.0.0-alpha.4, 2026-08-11) |
| Repository | https://github.com/intlify/vue-i18n |
| **Last checked for a new release** | **2026-08-12** — v11.4.8 was still the newest tag |

The last-checked date is the one line that has to be kept honest: `CLAUDE.md` asks for a check at
least weekly and reads that date to decide whether one is due. Update it on every check, whether or
not anything had moved.

Two commits, because they answer two different questions.

**`de2393b` (v11.4.8) is the contract.** It is the released version this port is expected to behave
like, the one `npm i vue-i18n` installs, and the one the conformance corpora under `conformance/`
were recorded from. When the two versions disagree, the port follows this one.

**`efeda9e` (main) is what the source files were read from.** The message compiler is byte-identical
between the two — verified, 126/126 comparable corpus cases — so for that half the distinction does
not arise. Where `main` has moved ahead, it is noted at the site. The one difference that matters so
far: 12.x added an `Intl.PluralRules` path for plural selection that 11.x does not have, and this
port follows 11.x. See "Deliberate deviations from upstream" in `PROGRESS.md`.

## The commitment

**This port follows vue-i18n's releases.** When upstream releases, the diff is reviewed and the
port is brought up to it. That is the promise the documentation makes and this file is the machinery
for keeping it.

Version numbering is *not* shared. vue-i18n-python has its own semantic version, because a port can need
a release for reasons of its own. Every release records the vue-i18n version it tracks, both here
and in the changelog.

## The submodule is the source of truth

`vendor/vue-i18n` is upstream, as a git submodule pinned to the baseline commit. That pin — not the
table above, which only restates it for a human reader — is what git actually tracks, and it is what
`scripts/conformance/bundle-upstream.sh` reads by default. It also means the whole comparison is
local: no clone to find, no network to check against.

```sh
git submodule update --init          # first time
```

**Released versions only.** The pin never moves to an alpha, beta or release candidate. The
question this project answers is "does it behave like the vue-i18n you can install today".

## Checking for a new release

```sh
git -C vendor/vue-i18n fetch --tags
git -C vendor/vue-i18n tag --list 'v*' --sort=-v:refname \
  | grep -vE 'alpha|beta|rc' | head -5
```

If the newest release tag is later than the pin, read the diff — and only in the three source paths
this project ports:

```sh
git -C vendor/vue-i18n diff HEAD..vNEW -- \
  packages/message-compiler/src packages/core-base/src packages/shared/src/utils.ts
```

An empty diff means there is nothing to do but move the pin. A non-empty one maps onto this port
through the table below.

Moving the pin, once the diff has been applied:

```sh
git -C vendor/vue-i18n checkout vNEW
./scripts/conformance/bundle-upstream.sh      # rebuild against the new pin
# regenerate the corpora - scripts/conformance/README.md - and read what moved
git add vendor/vue-i18n && git commit
```

## What maps to what

| This port | Upstream |
|---|---|
| `vue_i18n/compiler/location.py` | `packages/message-compiler/src/location.ts` |
| `vue_i18n/compiler/errors.py` | `packages/message-compiler/src/errors.ts` |
| `vue_i18n/compiler/scanner.py` | `packages/message-compiler/src/scanner.ts` |
| `vue_i18n/compiler/tokenizer.py` | `packages/message-compiler/src/tokenizer.ts` |
| `vue_i18n/compiler/nodes.py` | `packages/message-compiler/src/nodes.ts` |
| `vue_i18n/compiler/parser.py` | `packages/message-compiler/src/parser.ts` |
| `vue_i18n/runtime/errors.py` | `packages/core-base/src/errors.ts` |
| `vue_i18n/runtime/resolver.py` | `packages/core-base/src/resolver.ts` |
| `vue_i18n/runtime/fallbacker.py` | `packages/core-base/src/fallbacker.ts` |
| `vue_i18n/runtime/message_context.py` | `packages/core-base/src/runtime.ts`, plus the built-in modifiers from `context.ts` |
| `vue_i18n/runtime/format.py` | `packages/core-base/src/format.ts`, plus the accessors from `ast.ts` |
| `vue_i18n/runtime/display.py` | `packages/shared/src/utils.ts` — `String()` and `toDisplayString` |
| `vue_i18n/runtime/context.py` | `packages/core-base/src/context.ts` |
| `vue_i18n/runtime/translate.py` | `packages/core-base/src/translate.ts` |
| `vue_i18n/runtime/datetime.py`, `number.py` | `packages/core-base/src/datetime.ts`, `number.ts`, `formatter.ts` |
| `vue_i18n/plurals/` | **not a port** — see below |

### Deliberately not ported

- `message-compiler`'s `generator.ts`, `optimizer.ts`, `mangler.ts`, `transformer.ts`. They compile
  the AST into JavaScript source; this port interprets the AST directly. A change to any of them is
  usually irrelevant here — but read it anyway, because a change to what the AST *means* can arrive
  disguised as a change to how it is compiled.
- `context.ts`'s devtools hooks (`__v_emitter`, the timeline).
- `vue-i18n-core`, `vue-i18n`, `petite-vue-i18n` in their entirety: components, directives, the
  legacy API and the composition API are Vue bindings with no Python meaning.
- `vue_i18n/plurals/` is not a port at all. It is an opt-in CLDR rule source a caller passes as
  `plural_rules`, the counterpart of passing `pluralRules` to `createI18n`. An upstream change to
  plural handling still matters to it, but as a design question rather than as a diff to apply.

## When the diff is non-empty

1. Apply the source changes to the mapped modules.
2. Re-record the corpora — `scripts/conformance/README.md` says how — and read what moved. A corpus
   line that changes is upstream changing observable behaviour, which is exactly what wants
   attention.
3. Update the baseline commit and version at the top of this file, and the "Reference version"
   paragraph in `PROGRESS.md`.
4. Bump `VUE_I18N_VERSION` in `vue_i18n/__init__.py` — it is what the package and every context
   report as the release they behave like, and `context_test.py` checks it against this file.
5. Add a row to `docs/guide/version-translation.md`: the vue-i18n-python version that carries the
   change, the vue-i18n version it now tracks, and what actually moved. That table is how a user
   picks a version, so a pin that moves without a row is a pin nobody can find.
6. Note anything user-visible in the documentation's differences page.
