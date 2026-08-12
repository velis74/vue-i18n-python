#!/usr/bin/env python3
"""Turn ``cldr/plurals.json`` into ``vue_i18n/plurals/_generated.py``.

This is the one place the CLDR plural syntax is understood. It reads the vendored CLDR cardinal
rules and writes a category function per distinct rule set, a locale-to-function
table, and the *precedence list* per locale (see ``PRECEDENCE_ORDER`` below). The ladder arithmetic
itself lives in the hand-written runtimes, because it is derived from the precedence list alone and
does not need generating.

Run it with no arguments::

    python scripts/generate_plurals.py

Rule syntax being parsed (UTS #35, "Language Plural Rules")::

    condition   = and_condition ('or' and_condition)*
    and_condition = relation ('and' relation)*
    relation    = expr ('=' | '!=') range_list
    expr        = operand ('%' int)?
    operand     = 'n' | 'i' | 'f' | 't' | 'v' | 'w' | 'c' | 'e'
    range_list  = (range | int) (',' (range | int))*
    range       = int '..' int

The archaic ``is`` / ``in`` / ``within`` forms are not accepted: modern CLDR does not emit them, and
silently mis-parsing them would be worse than refusing. ``@integer``/``@decimal`` sample lists are
stripped before parsing.
"""

import json
import re

from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CLDR_JSON = REPO_ROOT / "cldr" / "plurals.json"
PY_OUT = REPO_ROOT / "vue_i18n" / "plurals" / "_generated.py"

#: The order CLDR itself lists plural categories in, and the order a message's forms are written in.
CANONICAL_ORDER = ("zero", "one", "two", "few", "many", "other")

#: The order in which categories earn a form as a message adds them — the *precedence* order of
#: settled decision 4. Read it as "what does the k-th form buy you":
#:
#: 1. ``other``  — one form is always legal and is never inflected.
#: 2. ``one``    — the singular/plural split every message author reaches for first.
#: 3. ``zero``   — the hand-written special case ("no items"); an explicit extra category that CLDR
#:                 does not carry for most locales (decision 5).
#: 4. the remaining CLDR categories in canonical order.
#:
#: A locale's precedence list is this sequence filtered to the categories it supports, where
#: "supports" means its CLDR categories plus ``zero``. For ``sl`` that yields
#: ``[other, one, zero, two, few]``, which is the table in PROGRESS.md item 4.
PRECEDENCE_ORDER = ("other", "one", "zero", "two", "few", "many")

OPERANDS = ("n", "i", "v", "w", "f", "t", "c", "e")

# Operands other than `n` are integers by construction, so only `n` ever needs the integer guard
# that CLDR's `=` relation implies (a range only ever contains integers).
NON_INTEGER_OPERAND = "n"


@dataclass(frozen=True)
class Relation:
    """One comparison, e.g. ``i % 100 = 3..4`` or ``v != 0``."""

    operand: str
    modulus: int | None
    negated: bool
    #: ``(lo, hi)`` pairs; a bare value is stored as ``(v, v)``.
    ranges: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class Condition:
    """A rule body: OR of AND-groups of relations. An empty ``groups`` means "always true"."""

    groups: tuple[tuple[Relation, ...], ...]


@dataclass(frozen=True)
class Rule:
    category: str
    condition: Condition


_RELATION_RE = re.compile(
    r"""^\s*
        (?P<operand>[nivwftce])\s*
        (?:%\s*(?P<mod>\d+)\s*)?
        (?P<op>!=|=)\s*
        (?P<ranges>[\d.,\s]+?)
        \s*$""",
    re.VERBOSE,
)


def parse_condition(text: str) -> Condition:
    """Parse a CLDR rule body (samples already stripped) into a :class:`Condition`."""
    body = text.split("@")[0].strip()
    if not body:
        # `other` has an empty body: it is the catch-all and matches unconditionally.
        return Condition(groups=())
    groups: list[tuple[Relation, ...]] = []
    for or_part in re.split(r"\bor\b", body):
        relations = tuple(parse_relation(part) for part in re.split(r"\band\b", or_part))
        groups.append(relations)
    return Condition(groups=tuple(groups))


def parse_relation(text: str) -> Relation:
    match = _RELATION_RE.match(text)
    if match is None:
        raise ValueError(f"unsupported CLDR plural relation: {text.strip()!r}")
    ranges: list[tuple[int, int]] = []
    for item in match["ranges"].split(","):
        item = item.strip()
        if ".." in item:
            lo, hi = item.split("..")
            ranges.append((int(lo), int(hi)))
        else:
            ranges.append((int(item), int(item)))
    return Relation(
        operand=match["operand"],
        modulus=int(match["mod"]) if match["mod"] else None,
        negated=match["op"] == "!=",
        ranges=tuple(ranges),
    )


def load_rules() -> tuple[str, dict[str, tuple[Rule, ...]]]:
    """Return ``(cldr_version, {locale: rules})`` with each locale's rules in canonical order."""
    data = json.loads(CLDR_JSON.read_text(encoding="utf-8"))
    version = data["supplemental"]["version"]["_cldrVersion"]
    out: dict[str, tuple[Rule, ...]] = {}
    for locale, raw in data["supplemental"]["plurals-type-cardinal"].items():
        by_category = {key.removeprefix("pluralRule-count-"): value for key, value in raw.items()}
        unknown = set(by_category) - set(CANONICAL_ORDER)
        if unknown:
            raise ValueError(f"{locale}: unknown plural categories {sorted(unknown)}")
        if "other" not in by_category:
            raise ValueError(f"{locale}: no `other` category, so no rule can terminate")
        out[locale] = tuple(
            Rule(category=category, condition=parse_condition(by_category[category]))
            for category in CANONICAL_ORDER
            if category in by_category
        )
    return version, out


def precedence_for(rules: tuple[Rule, ...]) -> tuple[str, ...]:
    """Derive a locale's precedence list from its CLDR categories. See ``PRECEDENCE_ORDER``."""
    supported = {rule.category for rule in rules} | {"zero"}
    return tuple(category for category in PRECEDENCE_ORDER if category in supported)


# --------------------------------------------------------------------------------------------- #
# Code generation
# --------------------------------------------------------------------------------------------- #


# How loosely a rendered fragment binds. `and` binds tighter than `or`, so an `and` fragment never
# needs parentheses, while an `or` fragment needs them inside an `and`.
ATOM, AND, OR = 0, 1, 2

#: What may stand unbracketed as an operand of `or`. Precedence would allow AND here, but a
#: generated rule set is something a human has to be able to audit against the CLDR source, and
#: `v == 0 and i % 100 == 2 or v != 0` does not read as one condition. Bracket AND groups too.
INSIDE_OR = ATOM


def parenthesize(text: str, level: int, allowed: int) -> str:
    return text if level <= allowed else f"({text})"


def emit_relation(relation: Relation) -> tuple[str, int]:
    """Render one comparison; returns the text and how loosely its top-level operator binds."""
    expr = relation.operand if relation.modulus is None else f"{relation.operand} % {relation.modulus}"
    parts: list[tuple[str, int]] = []
    singles = [lo for lo, hi in relation.ranges if lo == hi]
    spans = [(lo, hi) for lo, hi in relation.ranges if lo != hi]
    for value in singles:
        parts.append((f"{expr} == {value}", ATOM))
    for lo, hi in spans:
        parts.append((f"{lo} <= {expr} <= {hi}", ATOM))
    if len(parts) == 1:
        body, level = parts[0]
    else:
        body = " or ".join(parenthesize(text, part_level, INSIDE_OR) for text, part_level in parts)
        level = OR
    # CLDR's `=` only ever matches integers, so a fractional `n` fails the relation outright — and,
    # because that check happens before the negation, `n != 3..4` is *true* for n = 3.5.
    if spans and relation.operand == NON_INTEGER_OPERAND:
        guard = f"{relation.operand} == int({relation.operand})"
        body = guard + " and " + parenthesize(body, level, AND)
        level = AND
    if relation.negated:
        body = f"not ({body})"
        level = ATOM
    return body, level


def emit_condition(condition: Condition) -> str:
    groups: list[tuple[str, int]] = []
    for group in condition.groups:
        rendered = [emit_relation(relation) for relation in group]
        if len(rendered) == 1:
            groups.append(rendered[0])
        else:
            text = " and ".join(parenthesize(body, level, AND) for body, level in rendered)
            groups.append((text, AND))
    if len(groups) == 1:
        return groups[0][0]
    return " or ".join(parenthesize(text, level, INSIDE_OR) for text, level in groups)


def group_locales(rules_by_locale: dict[str, tuple[Rule, ...]]) -> list[tuple[tuple[Rule, ...], list[str]]]:
    """Collapse locales that share an identical rule set; CLDR 48's 224 locales need 40 of them."""
    grouped: dict[tuple[Rule, ...], list[str]] = {}
    for locale in sorted(rules_by_locale):
        grouped.setdefault(rules_by_locale[locale], []).append(locale)
    # Order by the first locale in each group so the output is stable across runs.
    return sorted(grouped.items(), key=lambda item: item[1][0])


def used_operands(rules: tuple[Rule, ...]) -> set[str]:
    """Which of the eight operands a rule set actually reads."""
    return {relation.operand for rule in rules for group in rule.condition.groups for relation in group}


def parameter_names(rules: tuple[Rule, ...]) -> list[str]:
    """Operand names for one rule function, underscore-prefixed where the rule ignores them.

    Every rule shares one eight-operand signature, so most rules ignore most of it. A leading
    underscore is what ruff reads as "deliberately unused" (``dummy-variable-rgx`` in
    ``pyproject.toml``), which keeps the generated output lint-clean without a blanket per-file
    suppression.
    """
    used = used_operands(rules)
    return [operand if operand in used else f"_{operand}" for operand in OPERANDS]


def header(version: str, prefix: str) -> list[str]:
    return [
        f"{prefix}Generated by scripts/generate_plurals.py from cldr/plurals.json (CLDR {version}).",
        f"{prefix}Do not edit by hand: re-run the generator instead.",
    ]


def generate_python(version: str, rules_by_locale: dict[str, tuple[Rule, ...]]) -> str:
    groups = group_locales(rules_by_locale)
    lines: list[str] = []
    lines.append('"""CLDR cardinal plural rules, generated.')
    lines.append("")
    lines.extend(header(version, ""))
    lines.append("")
    lines.append("Each ``_rule_N`` takes the CLDR plural operands and returns the plural category. The")
    lines.append("operands are ``n`` (absolute value), ``i`` (integer digits), ``v``/``w`` (count of visible")
    lines.append("fraction digits with/without trailing zeros), ``f``/``t`` (those digits as an integer) and")
    lines.append("``c``/``e`` (compact decimal exponent).")
    lines.append("")
    lines.append("``n`` is a ``Fraction`` because the rules take it modulo something and a fractional count")
    lines.append("has to survive that exactly; see ``Operands`` in the runtime. Every other operand is an")
    lines.append("integer by construction, so plain ``int`` arithmetic is exact at any magnitude.")
    lines.append('"""')
    lines.append("")
    lines.append("from collections.abc import Callable")
    lines.append("from fractions import Fraction")
    lines.append("")
    lines.append(f'CLDR_VERSION = "{version}"')
    lines.append("")
    lines.append("#: What every rule function looks like: the eight CLDR operands in, a category out.")
    lines.append("RuleFn = Callable[[Fraction, int, int, int, int, int, int, int], str]")
    lines.append("")
    lines.append("#: Categories in the order CLDR lists them, which is also the order a message writes its forms.")
    lines.append("CANONICAL_ORDER = (" + ", ".join(f'"{category}"' for category in CANONICAL_ORDER) + ")")
    lines.append("")
    lines.append("")

    for index, (rules, locales) in enumerate(groups):
        names = parameter_names(rules)
        signature = ", ".join(f"{name}: {'Fraction' if name.lstrip('_') == 'n' else 'int'}" for name in names)
        lines.append(f"def _rule_{index}({signature}) -> str:")
        lines.append(f'    """{", ".join(locales)}"""')
        for rule in rules:
            if rule.category == "other":
                continue
            lines.append(f"    if {emit_condition(rule.condition)}:")
            lines.append(f'        return "{rule.category}"')
        lines.append('    return "other"')
        lines.append("")
        lines.append("")

    lines.append("#: Locale (CLDR identifier, lowercase) to the function returning its plural category.")
    lines.append("RULES: dict[str, RuleFn] = {")
    for index, (_rules, locales) in enumerate(groups):
        for locale in locales:
            lines.append(f'    "{locale.lower()}": _rule_{index},')
    lines.append("}")
    lines.append("")
    lines.append("#: Locale to precedence list: the order in which categories earn a form as arity grows.")
    lines.append("PRECEDENCE: dict[str, tuple[str, ...]] = {")
    for _rules, locales in groups:
        precedence = "(" + "".join(f'"{category}", ' for category in precedence_for(_rules)).rstrip() + ")"
        for locale in locales:
            lines.append(f'    "{locale.lower()}": {precedence},')
    lines.append("}")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    version, rules_by_locale = load_rules()
    PY_OUT.parent.mkdir(parents=True, exist_ok=True)
    PY_OUT.write_text(generate_python(version, rules_by_locale), encoding="utf-8")
    distinct = len(group_locales(rules_by_locale))
    print(f"CLDR {version}: {len(rules_by_locale)} locales, {distinct} distinct rule sets")
    print(f"wrote {PY_OUT}")


if __name__ == "__main__":
    main()
