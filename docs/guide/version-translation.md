<script setup>
import { data } from './versions.data.ts'
</script>

# Which version tracks which

Read in either direction: *"I am on this vue-i18n — what do I install?"* and *"I have this
vue-i18n-python — what does it behave like?"*

## Right now

<table>
  <thead>
    <tr><th>vue-i18n-python</th><th>behaves like vue-i18n</th></tr>
  </thead>
  <tbody>
    <tr><td><strong>{{ data.package }}</strong></td><td><strong>{{ data.vueI18n }}</strong></td></tr>
  </tbody>
</table>

Both numbers are read out of the package source when this page is built, so they are the version
this documentation was published from.

## History

Every release that changed the tracked vue-i18n, oldest first. A vue-i18n-python release that only
fixes something here does not appear — it keeps the row above it, which is
[why the numbers are not shared](/guide/versioning#version-numbers-are-not-shared).

<table v-if="data.releases.length">
  <thead>
    <tr><th>vue-i18n-python</th><th>started tracking</th><th>what moved</th></tr>
  </thead>
  <tbody>
    <tr v-for="release in data.releases" :key="release.version">
      <td>{{ release.version }}</td><td>{{ release.tracks }}</td><td>{{ release.note }}</td>
    </tr>
  </tbody>
</table>

<p v-else>Nothing here yet — the block above is the whole story until the first release.</p>

## Ask the package instead

The table is for choosing. Once installed, the answer is in the package, so a script never has to
trust a document:

```python
import vue_i18n

vue_i18n.__version__        # this package
vue_i18n.VUE_I18N_VERSION   # the vue-i18n it behaves like
```

The same string is what a context reports, because that is what upstream's `createCoreContext` does
with `core-base`'s own `VERSION`:

```python
from vue_i18n import create_core_context

create_core_context().version
```

## What "behaves like" is worth

It is not a claim about a version string. Every conformance corpus under `conformance/` was recorded
by running the vue-i18n in the second column, and the test suite replays all of them on every run —
so the row is checked, not asserted. [How it is verified](/guide/conformance) says what that covers.

## Choosing a row

**Match the major.** vue-i18n 11 and 12 disagree about plural selection: 12 resolves through
`Intl.PluralRules` when no custom rule is given, 11 does not. A front end on 12 and a back end
tracking 11 will disagree about which plural form a locale picks — which is the exact class of bug
this library exists to remove.

Within a major, a mismatch in the patch digit is rarely visible here: most upstream releases touch
the Vue bindings this project does not port, and the [following upstream](/guide/versioning) page
explains how that is checked release by release.
