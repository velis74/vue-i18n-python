"""Tests for the plural runtime.

The expected index tables were derived by hand from the CLDR rules and then confirmed against
``Intl.PluralRules`` in Node (see PROGRESS.md for the run and its numbers). ``conformance/plurals.json``
covers far more ground; these tests are the readable statement of the same behaviour.
"""

import json
import sys

from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from types import ModuleType

import pytest

from i18n_united.plurals import (
    CANONICAL_ORDER,
    CLDR_VERSION,
    LANGUAGE_ALIASES,
    operands,
    plural_category,
    plural_index,
    plural_ladder,
    plural_precedence,
    resolve_locale,
    ROOT_LOCALE,
    rule_for,
)
from i18n_united.plurals._generated import RULES

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def load_corpus() -> dict:
    return json.loads((REPO_ROOT / "conformance" / "plurals.json").read_text(encoding="utf-8"))


def load_generator() -> ModuleType:
    """``scripts/generate_plurals.py`` as a module; it is not importable as part of the package."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("_generate_plurals", REPO_ROOT / "scripts" / "generate_plurals.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


#: The counts every locale table below is indexed by.
COUNTS = (0, 1, 2, 3, 4, 5, 11, 21, 100, 101, 102, 103, 111, 1000)

#: ``{locale: {arity: index per count in COUNTS}}``, every arity from 1 to the full ladder.
EXPECTED: dict[str, dict[int, tuple[int, ...]]] = {
    "sl": {
        1: (0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
        2: (1, 0, 1, 1, 1, 1, 1, 1, 1, 0, 1, 1, 1, 1),
        3: (0, 1, 2, 2, 2, 2, 2, 2, 2, 1, 2, 2, 2, 2),
        4: (0, 1, 2, 3, 3, 3, 3, 3, 3, 1, 2, 3, 3, 3),
        5: (0, 1, 2, 3, 3, 4, 4, 4, 4, 1, 2, 3, 4, 4),
    },
    "hr": {
        1: (0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
        2: (1, 0, 1, 1, 1, 1, 1, 0, 1, 0, 1, 1, 1, 1),
        3: (0, 1, 2, 2, 2, 2, 2, 1, 2, 1, 2, 2, 2, 2),
        4: (0, 1, 2, 2, 2, 3, 3, 1, 3, 1, 2, 2, 3, 3),
    },
    "en": {
        1: (0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
        2: (1, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1),
        3: (0, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2),
    },
    "ru": {
        1: (0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
        2: (1, 0, 1, 1, 1, 1, 1, 0, 1, 0, 1, 1, 1, 1),
        3: (0, 1, 2, 2, 2, 2, 2, 1, 2, 1, 2, 2, 2, 2),
        4: (0, 1, 2, 2, 2, 3, 3, 1, 3, 1, 2, 2, 3, 3),
        5: (0, 1, 2, 2, 2, 3, 3, 1, 3, 1, 2, 2, 3, 3),
    },
    "ar": {
        1: (0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
        # n = 0 is CLDR `zero` for Arabic; with no `zero` form to land on it falls forward to `one`.
        2: (0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1),
        3: (0, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2),
        4: (0, 1, 2, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3),
        5: (0, 1, 2, 3, 3, 3, 4, 4, 4, 4, 4, 3, 4, 4),
        6: (0, 1, 2, 3, 3, 3, 4, 4, 5, 5, 5, 3, 4, 5),
    },
    "ja": {
        1: (0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
        # Japanese has no `one`, so a second form can only be the explicit `zero`.
        2: (0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1),
    },
    "pl": {
        1: (0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
        2: (1, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1),
        3: (0, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2),
        4: (0, 1, 2, 2, 2, 3, 3, 3, 3, 3, 2, 2, 3, 3),
        5: (0, 1, 2, 2, 2, 3, 3, 3, 3, 3, 2, 2, 3, 3),
    },
    "cy": {
        1: (0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
        2: (0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1),
        3: (0, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2),
        4: (0, 1, 2, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3),
        5: (0, 1, 2, 3, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4),
        6: (0, 1, 2, 3, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5),
    },
}

EXPECTED_PRECEDENCE = {
    "sl": ("other", "one", "zero", "two", "few"),
    "hr": ("other", "one", "zero", "few"),
    "en": ("other", "one", "zero"),
    "ru": ("other", "one", "zero", "few", "many"),
    "ar": ("other", "one", "zero", "two", "few", "many"),
    "ja": ("other", "zero"),
    "pl": ("other", "one", "zero", "few", "many"),
    "cy": ("other", "one", "zero", "two", "few", "many"),
}


@pytest.mark.parametrize(("locale", "expected"), sorted(EXPECTED_PRECEDENCE.items()))
def test_precedence_list(locale: str, expected: tuple[str, ...]) -> None:
    assert plural_precedence(locale) == expected


@pytest.mark.parametrize(
    ("locale", "arity", "count", "expected"),
    [
        (locale, arity, count, index)
        for locale, by_arity in sorted(EXPECTED.items())
        for arity, indexes in sorted(by_arity.items())
        for count, index in zip(COUNTS, indexes, strict=True)
    ],
)
def test_plural_index_table(locale: str, arity: int, count: int, expected: int) -> None:
    assert plural_index(locale, count, arity) == expected


@pytest.mark.parametrize("locale", sorted(EXPECTED))
def test_table_covers_every_arity(locale: str) -> None:
    """The tables above must run from arity 1 to the locale's full ladder, with no gaps."""
    assert sorted(EXPECTED[locale]) == list(range(1, len(plural_precedence(locale)) + 1))


# ------------------------------------------------------------------------------------------- #
# The Slovenian ladder table of PROGRESS.md item 4, asserted literally
# ------------------------------------------------------------------------------------------- #


def test_slovenian_ladders_match_progress_table() -> None:
    assert plural_ladder("sl", 1) == ("other",)
    assert plural_ladder("sl", 2) == ("one", "other")
    assert plural_ladder("sl", 3) == ("zero", "one", "other")
    assert plural_ladder("sl", 4) == ("zero", "one", "two", "other")
    assert plural_ladder("sl", 5) == ("zero", "one", "two", "few", "other")


def test_slovenian_five_forms_reads_like_the_message() -> None:
    """The five-form Slovenian message, spelled out: 0 / 1 / 2 / 3-4 / the rest."""
    forms = ("ni oken", "{n} okno", "{n} okni", "{n} okna", "{n} oken")
    picked = {n: forms[plural_index("sl", n, 5)] for n in (0, 1, 2, 3, 4, 5, 101, 102, 103, 105)}
    assert picked == {
        0: "ni oken",
        1: "{n} okno",
        2: "{n} okni",
        3: "{n} okna",
        4: "{n} okna",
        5: "{n} oken",
        101: "{n} okno",
        102: "{n} okni",
        103: "{n} okna",
        105: "{n} oken",
    }


# ------------------------------------------------------------------------------------------- #
# Ladder mechanics
# ------------------------------------------------------------------------------------------- #


@pytest.mark.parametrize("locale", sorted(EXPECTED_PRECEDENCE))
def test_other_is_always_reachable(locale: str) -> None:
    """Every ladder ends in `other`, which is why falling forward always terminates."""
    for arity in range(1, len(plural_precedence(locale)) + 1):
        assert plural_ladder(locale, arity)[-1] == "other"


@pytest.mark.parametrize("locale", sorted(EXPECTED_PRECEDENCE))
def test_ladder_is_canonically_ordered(locale: str) -> None:
    for arity in range(1, len(plural_precedence(locale)) + 1):
        ladder = plural_ladder(locale, arity)
        assert list(ladder) == [category for category in CANONICAL_ORDER if category in ladder]
        assert len(ladder) == arity


def test_arity_above_the_full_ladder_leaves_forms_unreachable() -> None:
    """Surplus forms are simply never selected; the index stays inside the real ladder."""
    assert plural_ladder("en", 9) == ("zero", "one", "other")
    assert plural_index("en", 5, 9) == 2
    assert plural_index("sl", 3, 12) == 3


def test_arity_below_one_is_rejected() -> None:
    with pytest.raises(ValueError, match="at least one form"):
        plural_index("sl", 1, 0)


def test_fall_forward_stops_at_the_first_present_category() -> None:
    """`two` is absent from the three-form Slovenian ladder, so n = 2 walks few -> many -> other."""
    assert plural_category("sl", 2) == "two"
    assert plural_ladder("sl", 3) == ("zero", "one", "other")
    assert plural_index("sl", 2, 3) == 2


# ------------------------------------------------------------------------------------------- #
# The explicit `zero` category
# ------------------------------------------------------------------------------------------- #


def test_zero_form_wins_at_zero_even_though_cldr_says_other() -> None:
    assert plural_category("sl", 0) == "other"
    assert plural_index("sl", 0, 3) == 0
    # Without a `zero` form, n = 0 is plain CLDR again.
    assert plural_index("sl", 0, 2) == 1


def test_zero_form_is_only_about_zero() -> None:
    for count in (1, 2, 3, 5, 10, 100, 1000):
        assert plural_index("sl", count, 3) != 0


def test_cldr_zero_categories_survive_away_from_zero() -> None:
    """Latvian's CLDR `zero` also covers 10 and 20; the explicit rule must not narrow it."""
    assert plural_category("lv", 0) == "zero"
    assert plural_category("lv", 10) == "zero"
    assert plural_category("lv", 20) == "zero"
    assert plural_precedence("lv") == ("other", "one", "zero")
    assert plural_index("lv", 10, 3) == 0
    assert plural_index("lv", 0, 3) == 0
    # Two forms cannot express `zero`, so it falls forward one step — onto `one`, not all the way to
    # `other`. That is the rule applied uniformly; a locale whose CLDR carries `zero` therefore reads
    # its singular for 0 when the message declines to supply a zero form.
    assert plural_index("lv", 10, 2) == 0
    assert plural_index("lv", 0, 2) == 0


# ------------------------------------------------------------------------------------------- #
# Counts
# ------------------------------------------------------------------------------------------- #


def test_negative_counts_use_the_absolute_value() -> None:
    """CLDR's `n` is an absolute value, and vue-i18n's own rules start with Math.abs(choice)."""
    for count in (1, 2, 3, 5, 101):
        assert plural_index("sl", -count, 5) == plural_index("sl", count, 5)
    # vue-i18n passes -1 when a message has no count at all; that must behave like 1.
    assert plural_index("en", -1, 2) == 0


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (1, (1, 1, 0, 0, 0, 0)),
        (0, (0, 0, 0, 0, 0, 0)),
        (Decimal("1.0"), (Decimal("1.0"), 1, 1, 0, 0, 0)),
        (Decimal("1.230"), (Decimal("1.230"), 1, 3, 2, 230, 23)),
        (Decimal("-1.5"), (Decimal("1.5"), 1, 1, 1, 5, 5)),
        ("2.03", (Decimal("2.03"), 2, 2, 2, 3, 3)),
        (1.5, (Decimal("1.5"), 1, 1, 1, 5, 5)),
        (Decimal("1E+2"), (Decimal("100"), 100, 0, 0, 0, 0)),
    ],
)
def test_operands(value: object, expected: tuple[object, ...]) -> None:
    ops = operands(value)  # type: ignore[arg-type]
    assert (ops.n, ops.i, ops.v, ops.w, ops.f, ops.t) == expected
    # i18n-united never formats a count in compact notation, so the exponent operands are always 0.
    assert (ops.c, ops.e) == (0, 0)


def test_visible_fraction_digits_change_the_category() -> None:
    """Slovenian sends every decimal to `few`, which is the whole point of the `v` operand."""
    assert plural_category("sl", 1) == "one"
    assert plural_category("sl", Decimal("1.0")) == "few"
    assert plural_category("sl", Decimal("5.5")) == "few"
    assert plural_index("sl", Decimal("1.0"), 5) == 3


def test_ranges_only_match_integers() -> None:
    """CLDR's `=` against a range implies an integer test, so 3.5 is not Arabic `few`."""
    assert plural_category("ar", 3) == "few"
    assert plural_category("ar", Decimal("3.5")) == "other"


def test_large_integer_counts_keep_every_digit() -> None:
    """The digits a rule looks at are the last ones, which is exactly what rounding eats.

    A count over 28 significant digits used to be routed through the default ``decimal`` context,
    which rounds there: 10**28 + 1 arrived as 10**28 and answered for the wrong final digit.
    """
    count = 10**28 + 1
    assert operands(count).i == count
    assert plural_category("ru", count) == "one"  # v = 0 and i % 10 = 1 and i % 100 != 11
    assert plural_category("sl", count) == "one"  # v = 0 and i % 100 = 1
    assert plural_category("sl", 10**28 + 2) == "two"
    assert plural_category("ru", 10**28 + 11) == "many"  # i % 100 = 11 is the exception to `one`


def test_a_long_integer_part_does_not_eat_the_fraction_digits() -> None:
    """Rounding to the context precision dropped the written ``.0``, and with it the `v` operand."""
    value = Decimal("1" + "0" * 27 + ".0")
    ops = operands(value)
    assert (ops.i, ops.v, ops.w, ops.f, ops.t) == (10**27, 1, 0, 0, 0)
    assert ops.n == Fraction(10**27)
    # Slovenian sends anything with visible fraction digits to `few`, so `v` is observable.
    assert plural_category("sl", value) == "few"


def test_counts_are_exact_on_both_sides_of_the_point() -> None:
    ops = operands(Decimal("1" + "0" * 27 + ".5"))
    assert (ops.i, ops.v, ops.w, ops.f, ops.t) == (10**27, 1, 1, 5, 5)
    assert ops.n == Fraction(2 * 10**27 + 1, 2)


#: Every locale whose CLDR rules take ``n`` modulo something — the ones a ``Decimal`` modulus
#: refused outright once the integer quotient needed more than the context's 28 digits.
MODULUS_LOCALES = ("ar", "ars", "be", "br", "kw", "lt", "lv", "mo", "mt", "prg", "ro", "sgs")


@pytest.mark.parametrize("locale", MODULUS_LOCALES)
def test_a_modulus_of_a_large_count_answers_instead_of_raising(locale: str) -> None:
    assert plural_category(locale, 10**30) in CANONICAL_ORDER


def test_large_counts_under_a_modulus_answer_by_the_rule() -> None:
    assert plural_category("ar", 10**30) == "other"  # n % 100 = 0, so neither `few` nor `many`
    assert plural_category("br", 10**30) == "many"  # n % 1000000 = 0
    assert plural_category("ar", 10**30 + 3) == "few"  # n % 100 = 3


def test_a_count_past_the_int_string_limit_is_refused() -> None:
    """CPython will not convert an arbitrarily long digit string to `int`, and says so obscurely."""
    limit = sys.get_int_max_str_digits()
    with pytest.raises(ValueError, match="get_int_max_str_digits"):
        operands("1" * (limit + 1))
    with pytest.raises(ValueError, match="fraction digits"):
        operands(Decimal("0." + "1" * (limit + 1)))
    # One digit below the limit is an ordinary count, and an `int` needs no digit string at all, so
    # the limit does not reach it.
    assert operands("1" * limit).v == 0
    assert plural_category("sl", 10**5000 + 1) == "one"


def test_compact_decimal_operands_are_always_zero() -> None:
    """Deviation from upstream: `c` and `e` are hard-wired to 0. See PROGRESS.md."""
    for value in (0, 1, 1_500_000, Decimal("1.5"), 2.5, "1E+9"):
        assert (operands(value).c, operands(value).e) == (0, 0)  # type: ignore[arg-type]
    # French `many` is `e = 0 and i != 0 and i % 1000000 = 0 and v = 0 or e != 0..5`. Asked with
    # `{notation: "compact"}`, Intl reports `many` for 1 500 000 because e is then 6; i18n-united
    # never formats a count in compact notation, so the plain answer is the only one it can give.
    assert plural_category("fr", 1_500_000) == "other"
    assert plural_category("fr", 1_000_000) == "many"


def test_non_numbers_are_rejected() -> None:
    with pytest.raises(TypeError):
        operands(None)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="bool"):
        operands(True)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="finite"):
        operands(float("nan"))


# ------------------------------------------------------------------------------------------- #
# Locale resolution
# ------------------------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("tag", "expected"),
    [
        ("sl", "sl"),
        ("SL", "sl"),
        ("sl_SI", "sl"),
        ("sl-SI", "sl"),
        ("zh-Hant-TW", "zh"),
        ("pt-PT", "pt-pt"),  # CLDR carries pt-PT separately from pt
        ("pt-BR", "pt"),
        ("kok-Latn", "kok-latn"),
        ("xx-YY", "und"),
        ("", "und"),
    ],
)
def test_resolve_locale(tag: str, expected: str) -> None:
    assert resolve_locale(tag) == expected


def test_unknown_locale_behaves_like_root() -> None:
    assert plural_precedence("xx") == plural_precedence("und")
    assert plural_index("xx", 5, 2) == plural_index("und", 5, 2)


@pytest.mark.parametrize(
    ("tag", "expected"),
    [
        ("iw", "he"),  # the three ISO 639 renames every codebase still carries
        ("in", "id"),
        ("ji", "yi"),
        ("iw-IL", "he"),  # the alias replaces the language subtag, then widening carries on
        ("IW_il", "he"),
        ("slv", "sl"),  # ISO 639-2, which CLDR files under the two-letter code
        ("heb", "he"),
        ("zho-Hans-CN", "zh"),
        ("hbs", "sr"),  # a replacement that brings a script with it: hbs -> sr-Latn -> sr
        ("cnr", "sr"),  # ... and one that brings a region: cnr -> sr-ME -> sr
        ("swc", "sw"),
    ],
)
def test_deprecated_language_subtags_resolve_the_way_intl_canonicalizes_them(tag: str, expected: str) -> None:
    assert resolve_locale(tag) == expected


def test_a_deprecated_tag_answers_with_its_own_rules() -> None:
    """The point of the alias table: `iw` is Hebrew, not an unknown tag that says `other` forever."""
    assert plural_category("iw", 2) == "two"
    assert plural_index("iw", 2, 4) == 2


def test_vendored_cldr_rules_win_over_icu_aliasing() -> None:
    """ICU aliases these four away, but cldr/plurals.json still publishes rules for each of them.

    The vendored file is the source of truth (PROGRESS.md decision 3), and these are exactly the
    ids the Node cross-check excludes for the same reason.
    """
    for tag in ("jw", "mo", "sh", "tl"):
        assert tag not in LANGUAGE_ALIASES
        assert resolve_locale(tag) == tag


@pytest.mark.parametrize(("tag", "replacement"), sorted(LANGUAGE_ALIASES.items()))
def test_every_alias_is_worth_its_row(tag: str, replacement: str) -> None:
    assert tag not in RULES, "a tag CLDR itself carries must keep its vendored rules"
    assert resolve_locale(replacement) != ROOT_LOCALE, "an alias onto nothing is worse than no alias"
    assert resolve_locale(tag) == resolve_locale(replacement)
    # One substitution is enough because no replacement is itself deprecated; `resolve_locale` does
    # not loop, and this is what says it does not have to.
    assert replacement.partition("-")[0] not in LANGUAGE_ALIASES


# ------------------------------------------------------------------------------------------- #
# The vue-i18n-shaped entry point
# ------------------------------------------------------------------------------------------- #


def test_rule_for_matches_the_vue_i18n_signature() -> None:
    rule = rule_for("sl")
    assert [rule(n, 5) for n in COUNTS] == list(EXPECTED["sl"][5])


# ------------------------------------------------------------------------------------------- #
# Generated artefacts
# ------------------------------------------------------------------------------------------- #


def test_conformance_corpus_matches_the_runtime() -> None:
    """`conformance/plurals.json` is the contract the TypeScript port is held to; keep it honest."""
    corpus = load_corpus()
    assert corpus["cldr_version"] == CLDR_VERSION
    for locale, precedence in corpus["precedence"].items():
        assert list(plural_precedence(locale)) == precedence
        assert [list(ladder) for ladder in corpus["ladders"][locale]] == [
            list(plural_ladder(locale, arity)) for arity in range(1, len(precedence) + 1)
        ]
    assert corpus["cases"], "empty corpus"
    for row in corpus["cases"]:
        count = Decimal(row["n"])
        assert plural_category(row["locale"], count) == row["category"], row
        assert [plural_index(row["locale"], count, arity) for arity in range(1, len(row["indexes"]) + 1)] == (
            row["indexes"]
        ), row


def test_corpus_pins_locale_resolution() -> None:
    """Every other locale in the corpus is an exact rule-table key, so nothing would pin widening.

    A replay that never has to resolve a tag would go green against any resolution at all, including
    one that dropped `pt-BR` onto `pt-PT` or answered `iw` from the root.
    """
    locales = {row["locale"] for row in load_corpus()["cases"]}
    assert {"sl_SI", "sl-SI", "zh-Hant-TW", "pt-BR", "sr-Latn-RS", "xx-YY", "und", "iw", "in", "ji"} <= locales


def test_corpus_counts_stay_below_the_double_limit() -> None:
    """Above 2**53 the two languages cannot agree, so the corpus must not ask them to.

    A JavaScript count is an IEEE double: `10**28 + 1` is not that integer there, and `Intl` sees
    the rounded value. Python is exact. See PROGRESS.md.
    """
    for row in load_corpus()["cases"]:
        assert abs(Decimal(row["n"])) < 2**53, row


def test_generator_refuses_the_archaic_relation_forms() -> None:
    """Deviation from upstream CLDR syntax: `is` / `in` / `within` are refused. See PROGRESS.md.

    Modern CLDR does not emit them, and mis-parsing them silently would be worse than refusing.
    """
    generator = load_generator()
    for text in ("n is 1", "n is not 1", "n in 0..2", "n not in 0..2", "n within 0..2"):
        with pytest.raises(ValueError, match="unsupported CLDR plural relation"):
            generator.parse_condition(text)
    # The modern spelling of the same conditions still parses.
    assert generator.parse_condition("n = 1").groups
    assert generator.parse_condition("n != 0..2").groups


def test_generated_modules_are_up_to_date() -> None:
    """Regenerating from `cldr/plurals.json` must be a no-op; otherwise someone hand-edited."""
    module = load_generator()
    version, rules = module.load_rules()
    assert version == CLDR_VERSION
    assert module.generate_python(version, rules) == module.PY_OUT.read_text(encoding="utf-8")
