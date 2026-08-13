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

Two things are worth knowing before you choose this over `gettext` or `babel`, and only one of them
is really an argument against it.

- **The default plural rule is vue-i18n's**, which ignores the locale and stops at two forms. For
  Slovenian, Polish, Russian or Arabic that is the wrong form until you pass `plural_rules`
  yourself — see [plural rules](/guide/plurals). `gettext` gets this right from the `Plural-Forms`
  header with nothing to opt into. Keeping the clamp is the correct choice for a port and the wrong
  one for a general-purpose library, and this is a port. Upstream appears to agree: vue-i18n 12
  resolves through `Intl.PluralRules` when no custom rule is given.
- **Nothing checks your keys.** `t("cart.empty")` with a typo returns the key rather than failing,
  and no tool here reads your Python and tells you which keys are missing or which messages nobody
  calls. `vue-i18n-extract` does that for `.vue` and `.js`; the Python side of it does not exist yet.

What is *not* an argument against it is the absence of `xgettext`-style extraction. That step exists
because `gettext` uses the source string as the key, so the catalogue has to be rebuilt from the
code every time the code changes — and it breaks down exactly where a mixed project needs it most,
since `xgettext` cannot read `.vue` at all. Keys are authored here, not extracted, which is why
editing an English string does not invalidate every translation of it.

Nor is disambiguation. `gettext` needs `msgctxt` and `pgettext()` to tell two identical source
strings apart; with keys the question does not arise, because `menu.file.open` and
`dialog.file.open` were already different things.

The reason to reach for a port is agreement. If a Vue front end already renders these files, a back
end that renders them identically removes a whole class of bug — a narrower claim than "best", and a
checkable one: [seven corpora](/guide/conformance) check it on every test run.
