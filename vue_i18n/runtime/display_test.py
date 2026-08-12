"""The Python runner for the display corpus.

``conformance/display.json`` records, for a wide sweep of values, what JavaScript's ``String()`` and
``toDisplayString()`` produce. The Python port must agree, because these two functions decide what a
``{placeholder}`` looks like once a non-string value reaches it — a difference here is a difference
in the rendered translation.

The corpus carries 600 random 64-bit float patterns on purpose. Shortest-round-trip formatting is
where a hand-written port goes wrong, and it goes wrong on values nobody would think to write down.
"""

import json

from pathlib import Path

import pytest

from .display import js_string, to_display_string

CORPUS = Path(__file__).resolve().parent.parent.parent / "conformance" / "display.json"

with CORPUS.open(encoding="utf-8") as _fh:
    CORPUS_DATA = json.load(_fh)

CASES = CORPUS_DATA["cases"]
NUMBER_CASES = [c for c in CASES if c["kind"] == "number"]


def test_corpus_is_present_and_populated() -> None:
    """A corpus that silently shrank would let every other test in this file pass."""
    assert len(CASES) >= 1600, f"corpus has {len(CASES)} cases; it should only ever grow"
    assert len(NUMBER_CASES) >= 1500
    assert CORPUS_DATA["upstream"].startswith("intlify/vue-i18n@")


def test_every_case_is_read() -> None:
    """Guards against a runner that filters the corpus down and still reports green."""
    kinds = {c["kind"] for c in CASES}
    assert kinds == {"number", "boolean", "string", "object", "container"}, kinds
    assert len(CASES) == len(NUMBER_CASES) + len([c for c in CASES if c["kind"] != "number"])


@pytest.mark.parametrize("case", CASES, ids=lambda c: f"{c['kind']}:{c['display'][:24]}")
def test_display_matches_javascript(case: dict) -> None:
    assert to_display_string(case["value"]) == case["display"]


@pytest.mark.parametrize("case", NUMBER_CASES, ids=lambda c: c["string"])
def test_string_matches_javascript(case: dict) -> None:
    assert js_string(case["value"]) == case["string"]


def test_python_int_beyond_double_precision_is_exact_not_javascript_shaped() -> None:
    """The one place the two languages cannot agree, asserted so it stays deliberate.

    A Python ``int`` is exact at any size; a JavaScript number is a double, so past 2**53 it is not
    the integer that was written. ``String(12345678901234567890)`` is "12345678901234567000" there.
    Reproducing that rounding would mean throwing away precision Python actually has, in a value the
    caller passed deliberately — so this port prints the integer it was given.
    """
    assert js_string(12345678901234567890) == "12345678901234567890"
    assert js_string(2**53) == "9007199254740992"
    # A float of the same magnitude follows JavaScript, because there the precision really is gone.
    assert js_string(float(12345678901234567890)) == "12345678901234567000"
