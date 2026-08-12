"""The Python runner for the end-to-end render corpus.

``conformance/render.json`` holds source messages rendered to strings by real vue-i18n. Every other
corpus in this repository pins one stage; this one pins the whole pipeline — tokenizer, parser, AST,
message context, interpolation, linked-message resolution, modifiers — against the thing a user
actually sees.

Plural *selection* is pinned to a fixed branch by the generator and is deliberately not tested here;
that question belongs to ``conformance/plurals.json``, because the two ports disagree about it on
purpose.
"""

import json

from pathlib import Path

import pytest

from ..compiler.parser import create_parser
from .format import compile_message, format_parts
from .message_context import MessageContext, MessageContextOptions
from .resolver import resolve_value

CORPUS = Path(__file__).resolve().parent.parent.parent / "conformance" / "render.json"

with CORPUS.open(encoding="utf-8") as _fh:
    CORPUS_DATA = json.load(_fh)

CASES = CORPUS_DATA["cases"]
LINKS = CORPUS_DATA["links"]

_parser = create_parser()


def _make_lookup(messages: dict):
    """``ctx.message(key)`` over a nested resource, the way vue-i18n resolves a linked key."""

    def lookup(key: str, _use_linked: bool = False):
        raw = resolve_value(messages, key)
        if not isinstance(raw, str):
            return None
        return compile_message(_parser.parse(raw))

    return lookup


def _render(case: dict) -> str:
    options = MessageContextOptions(
        locale="xx",
        list=case["list"] or [],
        named=case["named"] or {},
        messages=_make_lookup(LINKS),
        # The generator pinned vue-i18n to this branch; pin the port to the same one so the
        # comparison is about rendering and not about plural rules.
        plural_rules={"xx": lambda _choice, _length, _org=None, _b=case["branch"]: _b},
    )
    return format_parts(MessageContext(options), _parser.parse(case["source"]))


def test_corpus_is_present_and_populated() -> None:
    assert len(CASES) >= 74, f"corpus has {len(CASES)} cases; it should only ever grow"
    assert CORPUS_DATA["upstream"].startswith("intlify/vue-i18n@")
    assert LINKS, "the linked-message resources are what half these cases exercise"


def test_no_case_is_silently_unrendered() -> None:
    """A corpus entry whose expectation is null would pass any implementation at all."""
    unrendered = [c for c in CASES if c["rendered"] is None and c["threw"] is None]
    assert unrendered == [], unrendered


@pytest.mark.parametrize("case", CASES, ids=lambda c: f"{c['source'][:32]}#{c['branch']}")
def test_render_matches_vue_i18n(case: dict) -> None:
    if case["threw"] is not None:
        pytest.skip(f"vue-i18n itself raised: {case['threw']}")
    assert _render(case) == case["rendered"]
