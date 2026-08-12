# Following upstream

**This port follows vue-i18n's releases.** That is a commitment, and this page is how it is kept
rather than merely stated.

## Which vue-i18n does this match?

Answered by a checkout, not by a claim. Upstream is a **git submodule** in the repository, pinned to
the exact commit of the released version being tracked:

| | |
|---|---|
| Tracked release | **v11.4.8** |
| Commit | `de2393bae16676a8a7c293bb493415e3085a521a` |

Every conformance corpus is recorded by running *that* checkout, so "does it behave like vue-i18n"
is a question the test suite answers on every run.

## Released versions only

The pin never moves to an alpha, beta or release candidate. The question this project answers is
"does it behave like the vue-i18n you can install today", and a pre-release is not that.

This matters more than it sounds. vue-i18n 12 changes plural selection — it resolves through
`Intl.PluralRules` when no custom rule is given. Porting from the pre-release would have meant
shipping behaviour that no released vue-i18n has.

## Version numbers are not shared

This library has its own semantic version. A port needs releases for reasons of its own: a bug in
the port, a new Python version, a documentation fix. Every release records the vue-i18n version it
tracks, in `UPSTREAM.md` and in the changelog.

So `vue-i18n-python 0.3.0` does not mean vue-i18n 0.3.0, and it never will.

## What happens when upstream releases

1. The new release is noticed — the repository asks for a check at least weekly, and `UPSTREAM.md`
   carries the date of the last one.
2. The diff is read, and only in the three source paths this project ports:

   ```sh
   git -C vendor/vue-i18n diff HEAD..vNEW -- \
     packages/message-compiler/src packages/core-base/src packages/shared/src/utils.ts
   ```

3. Changes are applied through the file-by-file map in `UPSTREAM.md`, which pairs every module here
   with the upstream file it came from.
4. The corpora are **re-recorded** against the new pin. A corpus line that moves is upstream changing
   observable behaviour, which is exactly what wants a human's attention.
5. The pin moves, and the release notes say which vue-i18n version it now tracks.

An empty diff means there is nothing to do but move the pin — which happens more often than not,
because most upstream changes are in the Vue bindings this project does not port.

## What is not tracked

`vue-i18n-core`, `vue-i18n`, `petite-vue-i18n` and the devtools packages. Components, directives,
`useI18n` and the composition API are Vue bindings. A release that only touches them changes nothing
here, and the diff command above will show that in one line.
