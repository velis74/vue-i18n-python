"""Plural form selection: locale + count + number of forms -> index of the form to use.

This module is **not** a port. vue-i18n resolves plurals through ``Intl.PluralRules``, which is not
available to Python and which handles a message with fewer forms than the locale has categories by
clamping (``Math.min(index, choicesLength - 1)``). Clamping puts ``two``, ``few`` and ``many`` on
the *last* form, so a three-form Slovenian message reads its plural text for n = 2 and cannot say
"no items" at all — vue-i18n's own ``zero | one | other`` convention is lost. vue-i18n-python instead
uses the arity model of PROGRESS.md item 4, which is what the hand-written rules in real projects
actually do.

The model:

* Every locale has a **precedence list** — the order in which categories earn a form as a message
  adds them. It is derived from the locale's CLDR categories by ``scripts/generate_plurals.py``;
  see ``PRECEDENCE_ORDER`` there for the rule and its rationale. For ``sl`` it is
  ``[other, one, zero, two, few]``.
* The **ladder** for arity k is the first k entries of that list, re-sorted into canonical category
  order (``zero, one, two, few, many, other``) — which is the order a message writes its forms in.
* A count is mapped to its CLDR category, and a category the ladder does not carry **falls forward**
  toward ``other``. ``other`` is always the first entry of the precedence list, so every ladder
  contains it and the walk always terminates.
* ``zero`` is an explicit extra category (PROGRESS.md item 5). Most locales have no CLDR ``zero``;
  when the ladder carries one it wins at exactly n == 0, on top of whatever CLDR says. For the few
  locales that *do* have a CLDR ``zero`` (ar, cy, lv, ...) this changes nothing at n == 0 and leaves
  the rest of their ``zero`` rule intact — ``lv`` still reports ``zero`` for 10 and 20. Their
  fall-forward is worth knowing about, though: those locales reach ``zero`` from CLDR, so a message
  that supplies no zero form sends n = 0 one step forward onto ``one``, not to ``other``.

The counterpart of vue-i18n's ``PluralizationRule`` is :func:`rule_for`, which returns a
``(choice, choices_length) -> index`` callable.
"""

import sys

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction

from ._aliases import LANGUAGE_ALIASES
from ._generated import CANONICAL_ORDER, CLDR_VERSION, PRECEDENCE, RULES

__all__ = [
    "CANONICAL_ORDER",
    "CLDR_VERSION",
    "LANGUAGE_ALIASES",
    "ROOT_LOCALE",
    "Operands",
    "operands",
    "plural_category",
    "plural_index",
    "plural_ladder",
    "plural_precedence",
    "resolve_locale",
    "rule_for",
]

#: The locale CLDR uses for "undetermined"; every lookup terminates here.
ROOT_LOCALE = "und"

Number = int | float | Decimal | str


@dataclass(frozen=True)
class Operands:
    """The CLDR plural operands of a number (UTS #35).

    ``n`` absolute value, ``i`` integer digits, ``v``/``w`` count of visible fraction digits with and
    without trailing zeros, ``f``/``t`` those digits as an integer, ``c``/``e`` the compact decimal
    exponent. ``c`` and ``e`` are always 0: vue-i18n-python never formats counts in compact notation, and
    a rule such as French ``e != 0..5`` is therefore always false.

    ``n`` is a :class:`~fractions.Fraction` rather than a ``Decimal`` because rules take it modulo
    something (``n % 100 = 3..10``) and ``Decimal`` arithmetic runs under a context: the default one
    rounds to 28 significant digits and refuses a modulus whose integer quotient needs more than
    that. ``Fraction`` is exact and unbounded, so ``n`` means the same thing at 10**30 as at 3.
    """

    n: Fraction
    i: int
    v: int
    w: int
    f: int
    t: int
    c: int = 0
    e: int = 0


def operands(value: Number) -> Operands:
    """Decompose a count into CLDR plural operands.

    "Visible fraction digits" means as written, so the type of ``value`` is load-bearing: ``1`` has
    none, ``Decimal("1.0")`` has one. A ``float`` is read through ``repr``, which is the shortest
    round-tripping form — ``1.0`` therefore has one visible fraction digit, where JavaScript's
    ``String(1.0)`` is ``"1"`` and has none. The two languages agree on every integer count, which is
    what a message's ``count`` is in practice; ``conformance/plurals.json`` carries only counts whose
    digits both languages read the same way, so it never pins that difference.

    Every operand is exact at any magnitude: the digits are read off the value and assembled with
    plain ``int`` arithmetic, so nothing here is subject to a ``decimal`` context's precision.

    Raises:
        TypeError: ``value`` is not a number, or is a ``bool``.
        ValueError: ``value`` is not finite, or has more integer or fraction digits than CPython
            will convert between ``int`` and ``str`` (``sys.get_int_max_str_digits()``, 4300 by
            default). Raising ``sys.set_int_max_str_digits`` is the caller's decision to make, not a
            library's — it is process-global state.
    """
    if isinstance(value, bool):
        raise TypeError("plural count must be a number, not a bool")
    if isinstance(value, int):
        # An `int` count has no fraction digits at all, so there is nothing here for `decimal` to do
        # — and everything for it to break: `abs(Decimal(10**28 + 1))` rounds under the default
        # context and turns a count whose last digit decides the category into one that does not.
        # CLDR's `n` is the *absolute* value of the source number, and vue-i18n's own rules likewise
        # start with `Math.abs(choice)`. A missing count reaches vue-i18n as -1 and must behave as 1.
        magnitude = abs(value)
        return Operands(n=Fraction(magnitude), i=magnitude, v=0, w=0, f=0, t=0)
    if isinstance(value, Decimal):
        decimal = value
    elif isinstance(value, float):
        decimal = Decimal(repr(value))
    elif isinstance(value, str):
        decimal = Decimal(value)
    else:
        raise TypeError(f"plural count must be a number, got {type(value).__name__}")
    if not decimal.is_finite():
        raise ValueError(f"plural count must be finite, got {value!r}")
    # `as_tuple` is the exact written form — sign, digits, exponent — and reading it costs no
    # arithmetic, so the context never gets a chance to round. The sign is dropped rather than
    # negated because every operand is defined on the absolute value.
    _sign, digit_tuple, exponent = decimal.as_tuple()
    digits = "".join(str(digit) for digit in digit_tuple)
    if exponent >= 0:
        # A positive exponent is trailing zeros the number does not spell out, so it has no visible
        # fraction digits: `Decimal("1E+2")` is 100 with v = 0.
        integer, fraction = digits + "0" * exponent, ""
    else:
        padded = digits.rjust(-exponent, "0")
        integer, fraction = padded[:exponent] or "0", padded[exponent:]
    _check_digit_limit(integer, fraction)
    i = int(integer)
    f = int(fraction) if fraction else 0
    stripped = fraction.rstrip("0")
    scale = 10 ** len(fraction)
    return Operands(
        n=Fraction(i * scale + f, scale),
        i=i,
        v=len(fraction),
        w=len(stripped),
        f=f,
        t=int(stripped) if stripped else 0,
    )


def _check_digit_limit(integer: str, fraction: str) -> None:
    """Refuse a count whose digits CPython will not convert to ``int``.

    A count with thousands of digits is not a plural problem, it is a limit of the interpreter:
    ``int(digits)`` raises below only when the string is long enough, and the message it raises does
    not mention plurals. Say what happened instead. Lifting the limit is deliberately not done here
    — ``sys.set_int_max_str_digits`` is process-global, and a library does not get to set it.
    """
    limit = sys.get_int_max_str_digits()
    if not limit:  # 0 means the limit is switched off
        return
    for digits, part in ((integer, "integer"), (fraction, "fraction")):
        if len(digits) > limit:
            raise ValueError(
                f"plural count has {len(digits)} {part} digits, more than the {limit} CPython will "
                f"convert between int and str (sys.get_int_max_str_digits()); it cannot be "
                f"decomposed into plural operands"
            )


def resolve_locale(locale: str) -> str:
    """Map a locale tag onto a key of the generated tables, widening one subtag at a time.

    ``sl_SI`` and ``sl-SI`` both reach ``sl``; ``zh-Hant-TW`` reaches ``zh``; anything unknown ends at
    ``und``, whose only category is ``other``.

    A deprecated language subtag is replaced first (``iw`` → ``he``, ``slv`` → ``sl``), because a tag
    CLDR no longer lists is not an unknown tag: dropping it to ``und`` would answer ``other`` for
    every count of a language whose plurals are perfectly well known. See ``_aliases.py``.
    """
    tag = locale.replace("_", "-").lower()
    language, separator, rest = tag.partition("-")
    if tag in LANGUAGE_ALIASES:
        # A handful of legacy identifiers are more than one subtag long (`art-lojban`), so the whole
        # tag has to be offered to the table before its language subtag is.
        tag = LANGUAGE_ALIASES[tag]
    elif language in LANGUAGE_ALIASES:
        tag = LANGUAGE_ALIASES[language] + separator + rest
    while tag:
        if tag in RULES:
            return tag
        tag, _, _ = tag.rpartition("-")
    return ROOT_LOCALE


def plural_category(locale: str, value: Number) -> str:
    """The plain CLDR category of ``value`` — no ``zero`` override, no arity."""
    rule = RULES[resolve_locale(locale)]
    ops = operands(value)
    return rule(ops.n, ops.i, ops.v, ops.w, ops.f, ops.t, ops.c, ops.e)


def plural_precedence(locale: str) -> tuple[str, ...]:
    """The locale's precedence list: the order in which categories earn a form as arity grows."""
    return PRECEDENCE[resolve_locale(locale)]


def plural_ladder(locale: str, arity: int) -> tuple[str, ...]:
    """The categories a message with ``arity`` forms distinguishes, in the order it writes them.

    Arity above the precedence list's length yields the full ladder: the surplus forms are simply
    unreachable. Returning an index into them instead would mean inventing a category the locale
    does not have.
    """
    if arity < 1:
        raise ValueError(f"a message needs at least one form, got arity {arity}")
    precedence = plural_precedence(locale)
    selected = set(precedence[:arity])
    return tuple(category for category in CANONICAL_ORDER if category in selected)


def plural_index(locale: str, choice: Number, choices_length: int) -> int:
    """Index of the form to use for ``choice`` in a message with ``choices_length`` forms."""
    ladder = plural_ladder(locale, choices_length)
    ops = operands(choice)
    # The explicit `zero` form wins outright at n == 0, whatever CLDR would have said. Most locales
    # have no CLDR `zero` at all - for `sl`, 0 is plain `other` - so without this a message that
    # spells out "ni povezav" as its first form would never reach it.
    if ops.n == 0 and "zero" in ladder:
        return ladder.index("zero")
    rule = RULES[resolve_locale(locale)]
    category = rule(ops.n, ops.i, ops.v, ops.w, ops.f, ops.t, ops.c, ops.e)
    # Fall forward toward `other`, which every ladder carries because it heads every precedence list.
    for candidate in CANONICAL_ORDER[CANONICAL_ORDER.index(category) :]:
        if candidate in ladder:
            return ladder.index(candidate)
    raise AssertionError(f"{locale}: ladder {ladder} has no `other` to fall forward to")


def rule_for(locale: str) -> Callable[[Number, int], int]:
    """A ``(choice, choices_length) -> index`` callable, the shape vue-i18n's ``pluralRules`` takes."""

    def rule(choice: Number, choices_length: int) -> int:
        return plural_index(locale, choice, choices_length)

    return rule
