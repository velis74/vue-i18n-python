# Which version tracks which

One table, read in either direction: *"I am on vue-i18n 11.4.8 — what do I install?"* and *"I have
vue-i18n-python 0.1.0 — what does it behave like?"*

| vue-i18n-python | behaves like vue-i18n | what moved |
|---|---|---|
| 0.1.0 *(unreleased)* | **11.4.8** | First release. The whole port recorded against this pin. |

A row is added every time the tracked release changes, and only then. A vue-i18n-python release that
fixes something here keeps the vue-i18n column it inherited — see
[why the numbers are not shared](/guide/versioning#version-numbers-are-not-shared).

## Ask the package instead

The table is for choosing. Once installed, the answer is in the package, so a script never has to
trust a document:

```python
import vue_i18n

vue_i18n.__version__        # '0.1.0'   - this package
vue_i18n.VUE_I18N_VERSION   # '11.4.8'  - the vue-i18n it behaves like
```

The same string is what a context reports, because that is what upstream's `createCoreContext` does
with `core-base`'s own `VERSION`:

```python
from vue_i18n import create_core_context

create_core_context().version   # '11.4.8'
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
