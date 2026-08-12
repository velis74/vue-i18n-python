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

- The same `.json` (or `.yaml`) files, unchanged, loaded by both ends.
- The same message syntax: `{named}` and `{0}` placeholders, `a | b | c` plurals, `@:linked`
  messages, `@.upper:` modifiers, `{'@'}` literals.
- The same key resolution, including nested keys and dotted keys held flat.
- The same fallback chain, including the map form with `default` and the `!` terminator.
- The same plural selection — and, if you already pass a custom `pluralRules` in JavaScript, the
  same rule transcribes directly. See [plural rules](/guide/plurals).
- `d()` and `n()` for dates and numbers, with the caveat on their page.

## Who should not use it

If you have no vue-i18n front end, you do not want this. You want `gettext`, or `babel` on its own,
or one of the Python-native i18n libraries. The reason to reach for a port is that something else in
your system already speaks this format.
