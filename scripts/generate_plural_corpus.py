#!/usr/bin/env python3
"""Write ``conformance/plurals.json``: the corpus that pins Python and TypeScript together.

Every case is ``(locale, n, arity) -> index``, produced by the Python runtime. The TypeScript side
must reproduce all of them; until ``ts/`` has its runtime and runner, the cross-check is done with a
scratch harness (see PROGRESS.md).

``n`` is a **decimal string**, not a JSON number, so that both languages read the same digits. Only
values that survive a JavaScript ``String(Number(x))`` round trip are emitted — a count such as
``1.0`` carries one visible fraction digit in Python but none in JavaScript, and pinning that
disagreement into the corpus would be pinning a language difference rather than a plural rule.

Run it with no arguments::

    python scripts/generate_plural_corpus.py
"""

import json
import sys

from decimal import Decimal
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT = REPO_ROOT / "conformance" / "plurals.json"

# Run from anywhere without installing the package first.
sys.path.insert(0, str(REPO_ROOT))

from i18n_united.plurals import (  # noqa: E402
    CLDR_VERSION,
    plural_category,
    plural_index,
    plural_ladder,
    plural_precedence,
)
from i18n_united.plurals._generated import RULES  # noqa: E402

#: Locales the acceptance tests name explicitly. Everything else is sampled below.
REQUIRED_LOCALES = ("sl", "hr", "en", "ru", "ar", "ja", "pl", "cy")

#: Tags that are *not* keys of the rule table, so that a case can only be answered by resolving them
#: first. Without these the corpus would replay green against any locale resolution at all — every
#: other locale in it is already an exact key. They cover the whole of ``resolve_locale``: the
#: underscore and hyphen separators, dropping a script and a region, a region that must *not* be
#: dropped (``pt-PT`` is a key of its own, so ``pt-BR`` has to reach plain ``pt``), a tag nothing
#: matches, the root itself, and the deprecated subtags of ``_aliases.py``.
RESOLUTION_TAGS = (
    "sl_SI",
    "sl-SI",
    "zh-Hant-TW",
    "pt-BR",
    "sr-Latn-RS",
    "xx-YY",
    "und",
    "iw",
    "in",
    "ji",
    "slv",
    "hbs",
)

#: JavaScript counts are IEEE doubles, so above 2**53 the count a JS caller passes is not the
#: integer they wrote. Both ports are exact below it and only Python is exact above, so a case up
#: there would pin a language difference rather than a plural rule. See PROGRESS.md.
MAX_EXACT_COUNT = 2**53

COUNTS: tuple[str, ...] = (
    *(str(value) for value in range(0, 31)),
    *(str(value) for value in (99, 100, 101, 102, 103, 104, 105, 110, 111, 112, 113, 114, 115, 119, 120, 121)),
    *(str(value) for value in (200, 201, 202, 203, 211, 999, 1000, 1001, 1002, 1003, 1011, 1021, 1101, 1111)),
    *(str(value) for value in (10000, 100000, 1000000, 1000001, 2000000)),
    # Fractional counts, chosen so that JavaScript's `String(Number(x))` returns the same digits.
    "0.5",
    "1.1",
    "1.5",
    "2.5",
    "3.5",
    "10.5",
    "11.5",
    "21.5",
    "100.5",
    "101.5",
)


def sample_locales() -> list[str]:
    """One locale per distinct rule set, plus the locales the tests name and the tags to resolve."""
    seen: dict[int, str] = {}
    for locale in sorted(RULES):
        seen.setdefault(id(RULES[locale]), locale)
    return sorted(set(seen.values()) | set(REQUIRED_LOCALES) | set(RESOLUTION_TAGS))


def serialize(document: dict) -> str:
    """indent-1 JSON in the house style of ``conformance/compile.json``, one line per row.

    ``json.dumps(indent=1)`` would spread a 3000-row corpus over a megabyte of mostly whitespace.
    Keeping each row on its own line keeps the diffs readable and the file a tenth of the size.
    """
    entries = []
    for key, value in document.items():
        if key in ("precedence", "ladders"):
            inner = ",\n".join(f"  {json.dumps(k)}: {json.dumps(v)}" for k, v in value.items())
            entries.append(f" {json.dumps(key)}: {{\n{inner}\n }}")
        elif key == "cases":
            inner = ",\n".join("  " + json.dumps(row, ensure_ascii=False) for row in value)
            entries.append(f" {json.dumps(key)}: [\n{inner}\n ]")
        else:
            entries.append(f" {json.dumps(key)}: {json.dumps(value, ensure_ascii=False)}")
    return "{\n" + ",\n".join(entries) + "\n}\n"


def main() -> None:
    locales = sample_locales()
    too_large = [count for count in COUNTS if abs(Decimal(count)) >= MAX_EXACT_COUNT]
    if too_large:
        raise ValueError(f"counts at or above 2**53 cannot be pinned across the two languages: {too_large}")
    cases = []
    for locale in locales:
        arities = list(range(1, len(plural_precedence(locale)) + 1))
        for count in COUNTS:
            value = Decimal(count)
            cases.append(
                {
                    "locale": locale,
                    "n": count,
                    "category": plural_category(locale, value),
                    # `indexes[k - 1]` is the form index for a message with k forms.
                    "indexes": [plural_index(locale, value, arity) for arity in arities],
                }
            )
    document = {
        "$comment": (
            "Generated by scripts/generate_plural_corpus.py from the Python plural runtime. Both "
            "language ports are held to it: `indexes[k - 1]` is the index of the form a message with "
            "k forms must use for count `n` in `locale`. `n` is a decimal string, and only values "
            "that survive a JavaScript String(Number(x)) round trip appear, so the two languages see "
            "the same visible fraction digits; every count is below 2**53, above which a JavaScript "
            "number is no longer the integer it was written as. `category` is the plain CLDR "
            "category, before the arity ladder and before the explicit `zero` rule. Some `locale` "
            "values are not keys of the rule table — they have to be resolved first."
        ),
        "cldr_version": CLDR_VERSION,
        "precedence": {locale: list(plural_precedence(locale)) for locale in locales},
        "ladders": {
            locale: [
                list(plural_ladder(locale, arity)) for arity in range(1, len(plural_precedence(locale)) + 1)
            ]
            for locale in locales
        },
        "cases": cases,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(serialize(document), encoding="utf-8")
    total = sum(len(row["indexes"]) for row in cases)
    print(f"wrote {OUT}: {len(locales)} locales, {len(cases)} rows, {total} (locale, n, arity) cases")


if __name__ == "__main__":
    main()
