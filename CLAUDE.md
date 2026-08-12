# Working on vue-i18n-python

**This library is a port of [vue-i18n](https://github.com/intlify/vue-i18n) to Python.** Same JSON
message files, same API, same behaviour. That framing decides most questions that come up: when the
port and vue-i18n disagree, vue-i18n is right, even where vue-i18n is arguably wrong. Read
`PROGRESS.md` for where the work stands, `GAPS.md` for what is knowingly missing, and
`UPSTREAM.md` for what exactly was ported from where.

**Record a gap the moment it is known**, in `GAPS.md`, not when it is convenient. Something
missing and written down is a decision; something missing and unrecorded is a defect waiting to
be found by a user.

## Check upstream at least once a week

`UPSTREAM.md` carries a **Last checked for a new release** date. At the start of a session, read it.
If it is more than seven days old, do the check before other work, and update the date whether or
not anything had moved.

Upstream is a submodule at `vendor/vue-i18n`, pinned to the baseline, so the check is local:

```sh
git -C vendor/vue-i18n fetch --tags
git -C vendor/vue-i18n tag --list 'v*' --sort=-v:refname | grep -vE 'alpha|beta|rc' | head -5
```

**Released versions only** — never an alpha, beta or release candidate. If there is a newer release
tag than the pin, read what changed in the three source paths this project actually ports, and
nothing else:

```sh
git -C vendor/vue-i18n diff HEAD..vNEW -- \
  packages/message-compiler/src packages/core-base/src packages/shared/src/utils.ts
```

Then report to the user: the new version, whether the diff touches ported code, and what it would
mean here. `UPSTREAM.md` has the file-by-file map from upstream paths to modules in this repo, and
the procedure for applying a non-empty diff. Do not start applying it without saying what it is.

This is a standing commitment the documentation makes to users, not a chore — the promise is that
vue-i18n-python follows vue-i18n's releases.

## House rules

- **Port faithfully.** Where upstream is ugly, port the ugliness. A tidier version that disagrees
  about one case is worse than an untidy one that agrees about all of them.
- **Every deliberate deviation needs three things**: a comment at the site, an entry in
  `PROGRESS.md` under "Deliberate deviations from upstream", and a test asserting it. Two out of
  three is not enough — the missing one is how a deviation quietly widens.
- **Verify against real vue-i18n, not against a reading of its source.** `scripts/conformance/`
  bundles upstream and records what it returns; that is what caught every real bug so far. Node is
  in this repo for that and for VitePress, and for nothing else. There is no JavaScript in the
  deliverable.
- **The library comes first; tests are secondary.** Write the tests that convince a reader it works
  on real input — ordinary interpolation, accented text, emoji in message text, counts in the 0–1000
  range, fallback chains a real application has. Do not chase extreme values, and do not build a
  corpus for its own sake.
- **`vue_i18n/plurals/` is not part of the port.** vue-i18n's own plural rule ignores the locale
  and clamps at index 2; the runtime reproduces that and never reaches for the CLDR module. The CLDR
  rules exist as something a caller passes as `plural_rules`, the way a Vue application passes
  `pluralRules` to `createI18n`.

## Style

Match the code that is already there — `vue_i18n/compiler/tokenizer.py` and
`vue_i18n/runtime/message_context.py` are the reference. Module docstring names the upstream file
it ports. Comments explain *why*, especially where the port deviates or upstream surprises; never
restate the code. Dataclasses over dicts. `X | None`, never `Optional[X]`. Double quotes, line
length 120. Tests live next to the code as `<module>_test.py`. `None` stands in for JavaScript
`undefined`.
