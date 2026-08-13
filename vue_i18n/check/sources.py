"""Find the keys a codebase asks for.

Python is read with the ``ast`` module, so a call is a call and a string literal is a string literal.
``.vue``, ``.ts`` and ``.js`` are read with a regular expression, because parsing them properly would
mean shipping a JavaScript toolchain and this package has none - a deliberate limit, reported on
every finding through ``approximate`` rather than hidden.

A key that is not a literal is not a failure. It is recorded as unchecked and counted separately,
because a checker that cannot tell "wrong" from "cannot tell" trains people to ignore it.
"""

import ast
import re

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .messages import resolves
from .report import Problem, Report, Severity

#: Function name -> which positional argument carries the key. ``translate`` is this library's own
#: signature, ``t`` the wrapper almost everyone writes around it.
PYTHON_CALLS = {"translate": 1, "t": 0}

#: `$t('key')`, `t("key")`, `tc(...)`, `te(...)`, with or without the Vue `$` prefix. The lookbehind
#: is what stops `format(`, `split(` and every other word ending in t from matching.
SCRIPT_CALL = re.compile(r"""(?<![\w$.])\$?t[ce]?\s*\(\s*(['"`])((?:[^'"`\\]|\\.)*)\1""")

TEXT_SUFFIXES = frozenset({".vue", ".ts", ".js", ".mjs", ".cjs", ".tsx", ".jsx"})
PYTHON_SUFFIXES = frozenset({".py"})

#: `<!-- -->` in a Vue template, `/* */` in a script. Line comments are handled while scanning,
#: because they end at a newline and the blanking below has to keep newlines where they are.
BLOCK_COMMENT = re.compile(r"<!--.*?-->|/\*.*?\*/", re.DOTALL)


def _blank_comments(source: str) -> str:
    """Replace commented-out regions with spaces, keeping every offset and line break in place.

    Blanking rather than deleting is what lets the reported line and column still point at the real
    file after a comment above them has been removed from consideration.
    """
    return BLOCK_COMMENT.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), source)


@dataclass(frozen=True)
class KeyUse:
    """One place the code asks for a translation."""

    #: ``None`` when the key is computed rather than written down.
    key: str | None
    file: str
    line: int
    column: int | None = None
    #: True when found by regular expression rather than by parsing.
    approximate: bool = False


def _call_name(node: ast.Call) -> str | None:
    """``t(...)``, ``i18n.t(...)`` and ``self.t(...)`` all answer ``t``."""
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def extract_from_python(source: str, file: str, calls: dict[str, int] | None = None) -> list[KeyUse]:
    """Every translation call in one Python module."""
    wanted = PYTHON_CALLS if calls is None else calls
    try:
        tree = ast.parse(source)
    except SyntaxError:
        # Not this tool's job to report; a file that does not parse has louder problems.
        return []

    uses: list[KeyUse] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _call_name(node)
        if name not in wanted:
            continue
        index = wanted[name]
        if index >= len(node.args):
            continue
        argument = node.args[index]
        if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
            uses.append(KeyUse(argument.value, file, argument.lineno, argument.col_offset + 1))
        else:
            uses.append(KeyUse(None, file, argument.lineno, argument.col_offset + 1))
    return uses


def extract_from_text(source: str, file: str) -> list[KeyUse]:
    """Every translation call in a `.vue`, `.ts` or `.js` file, by regular expression."""
    uses: list[KeyUse] = []
    scanned = _blank_comments(source)
    starts = [match.start() for match in re.finditer(r"\n", scanned)]

    def line_of(offset: int) -> int:
        low, high = 0, len(starts)
        while low < high:
            middle = (low + high) // 2
            if starts[middle] < offset:
                low = middle + 1
            else:
                high = middle
        return low + 1

    for match in SCRIPT_CALL.finditer(scanned):
        line_start = scanned.rfind("\n", 0, match.start()) + 1
        before = scanned[line_start : match.start()]
        if "//" in before:
            continue
        key = match.group(2)
        # A template literal with a substitution is computed, however literal its quotes look.
        dynamic = match.group(1) == "`" and "${" in key
        uses.append(
            KeyUse(
                None if dynamic else key,
                file,
                line_of(match.start()),
                match.start() - line_start + 1,
                approximate=True,
            )
        )
    return uses


def extract_from_path(path: Path, calls: dict[str, int] | None = None) -> list[KeyUse]:
    """Read one file or walk one directory, dispatching on suffix."""
    if path.is_dir():
        uses: list[KeyUse] = []
        for child in sorted(path.rglob("*")):
            if child.is_file():
                uses.extend(extract_from_path(child, calls))
        return uses

    suffix = path.suffix.lower()
    if suffix in PYTHON_SUFFIXES:
        return extract_from_python(path.read_text(encoding="utf-8"), str(path), calls)
    if suffix in TEXT_SUFFIXES:
        return extract_from_text(path.read_text(encoding="utf-8"), str(path))
    return []


def check_sources(uses: list[KeyUse], resources: dict[str, Any], report_unused: bool = True) -> Report:
    """Match what the code asks for against what the messages provide.

    A key is satisfied when *any* locale has it, because the fallback chain is what makes a key
    present in one locale usable from another. Which locales are missing it is
    :func:`check_messages`'s question, not this one's.
    """
    report = Report()
    asked: set[str] = set()
    saw_dynamic = False

    for use in uses:
        if use.key is None:
            saw_dynamic = True
            report.add(
                Problem(
                    severity=Severity.NOTE,
                    kind="dynamic-key",
                    detail="key is computed at runtime, so it was not checked",
                    file=use.file,
                    line=use.line,
                    column=use.column,
                )
            )
            continue
        asked.add(use.key)
        if not any(resolves(resource, use.key) for resource in resources.values()):
            report.add(
                Problem(
                    severity=Severity.ERROR,
                    kind="unknown-key",
                    detail=f"{use.key!r} is in no locale"
                    + (" (found by pattern, so check it by hand)" if use.approximate else ""),
                    file=use.file,
                    line=use.line,
                    column=use.column,
                    key=use.key,
                )
            )

    if report_unused and not saw_dynamic:
        from .messages import flatten

        defined: set[str] = set()
        for resource in resources.values():
            defined.update(flatten(resource))
        for key in sorted(defined - asked):
            report.add(
                Problem(
                    severity=Severity.NOTE,
                    kind="unused-key",
                    detail=f"{key!r} is defined but nothing asks for it",
                    key=key,
                )
            )

    return report
