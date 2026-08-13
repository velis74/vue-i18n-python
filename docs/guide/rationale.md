# Why this exists

You have a Vue front end using [vue-i18n](https://github.com/intlify/vue-i18n) and a Python back
end. Both need to produce text in the user's language: the front end renders the interface, the back
end renders the confirmation email, the PDF, the SMS, the error the API returns.

Today that means two sets of translation files, two syntaxes, and two sets of plural rules that
drift apart. The email says "3 povezave" and the page says "3 povezav", and nobody notices until a
customer does.

This library removes the second set. It reads the message files you already have and produces the
same strings from them.

## What it is

**A port of vue-i18n's message compiler and runtime to Python.** Not a library inspired by
vue-i18n, not a converter, not a common subset — the actual tokenizer, parser, key resolver,
fallback walk and message context, translated file by file into Python and checked against the
originals.

`UPSTREAM.md` in the repository maps every module to the upstream file it came from. The mapping is
one-to-one on purpose: when vue-i18n releases, the diff can be read in one column and applied in the
other.

## What it deliberately is not

**It is not an improvement.** Where vue-i18n does something surprising, this does the same
surprising thing. That is the whole value: a back end that is *better* than the front end is a back
end that disagrees with it, and a disagreement in a translation looks like a bug in your
application, not like a fix in your library.

There are exceptions, every one of them written down with its reasoning on the
[differences](/guide/differences) page. There are not many.

**It is not a Vue binding.** Components, directives, `useI18n` and the composition API have no
meaning outside a browser and are not ported. What is ported is everything underneath them.

## What you get

- The same message files, unchanged. Both ends read the one set; loading them is your step, with
  `json.load` — or `yaml.safe_load`, if your front end's build takes YAML — and the resulting object
  is what you hand over.
- The same message syntax: `{named}` and `{0}` placeholders, `a | b | c` plurals, `@:linked`
  messages, `@.upper:` modifiers, `{'@'}` literals.
- The same key resolution, including nested keys and dotted keys held flat.
- The same fallback chain, including the map form with `default` and the `!` terminator.
- The same plural selection — and, if you already pass a custom `pluralRules` in JavaScript, the
  same rule transcribes directly. See [plural rules](/guide/plurals).
- `d()` and `n()` for dates and numbers, with the caveat on their page.

## Who should not use it

If nothing in your system already speaks vue-i18n's format, two things weigh against this library.

- **The default plural rule is vue-i18n's.** It ignores the locale and stops at two forms, which is
  wrong for Slovenian, Polish, Russian, Arabic and most of the world. One line corrects it —
  `plural_rules={"sl": rule_for("sl")}` — the CLDR rules ship with the package, and the checker
  warns about every message that needs one. `gettext` gets this right with nothing to opt into. See
  [plural rules](/guide/plurals).
- **The translator ecosystem speaks `.po`.** Weblate, Crowdin and Poedit all read JSON, but `.po`
  carries translator comments, message context and fuzzy flags that JSON does not. There is no
  converter here. On a Python-only project with outside translators, that alone is reason enough to
  stay with `gettext`.

### What a key-based format does not need

- **An extraction step.** `xgettext` and `pybabel extract` exist because `gettext` uses the source
  string as the key, so the catalogue is rebuilt from the code on every change — and neither reads
  `.vue`. Keys are authored here, so editing an English string does not invalidate its translations.
- **`msgctxt`.** Two identical strings need disambiguating only when the string *is* the key.
  `menu.file.open` and `dialog.file.open` are already different things.
- **A separate linter.** `python -m vue_i18n.check` reads your message files and your code and
  reports the keys that do not line up, `.vue` included. See
  [checking your messages](/guide/checking).

## What this library claims

Agreement. If a Vue front end already renders these files, a back end that renders them identically
removes a whole class of bug. That is narrower than "best", and it is checkable:
[seven corpora](/guide/conformance) check it on every test run.
