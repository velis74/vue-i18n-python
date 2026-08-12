"""The Python runner for the compile corpus.

``conformance/compile.json`` holds, for every source message, the AST that
``intlify/vue-i18n``'s own parser produces and the errors it reports. This file checks that this
port produces exactly that.

The fixture is the contract and the port is the thing being held to it. If a change here makes a
case fail, the port is wrong until proven otherwise - do not edit the corpus to match the port.
"""

import json

from pathlib import Path

import pytest

from .nodes import to_dict
from .parser import create_parser

CORPUS = Path(__file__).resolve().parent.parent.parent / "conformance" / "compile.json"


def _load() -> dict:
    with CORPUS.open(encoding="utf-8") as fh:
        return json.load(fh)


def _case_id(case: dict) -> str:
    return repr(case["source"])[:40]


CORPUS_DATA = _load()
CASES = CORPUS_DATA["cases"]


def test_corpus_is_present_and_populated() -> None:
    """A corpus that silently shrank to nothing would let every other test in this file pass."""
    assert len(CASES) >= 128, f"corpus has {len(CASES)} cases; it should only ever grow"
    assert CORPUS_DATA["upstream"].startswith("intlify/vue-i18n@")


@pytest.mark.parametrize("case", CASES, ids=_case_id)
def test_ast_matches_upstream(case: dict) -> None:
    errors: list[dict] = []
    parser = create_parser(on_error=lambda e: errors.append({"code": int(e.code), "message": str(e)}))
    ast = to_dict(parser.parse(case["source"]))

    if "upstream_throws" in case:
        # Upstream raises a RangeError out of `String.fromCodePoint` for a code point past U+10FFFF
        # and produces no AST at all. This port substitutes U+FFFD - the same thing upstream already
        # does for a lone surrogate - so that one malformed escape cannot abort the load of a whole
        # translation file. The deviation is deliberate, is the only one in the compiler, and is
        # asserted here so it cannot widen unnoticed.
        assert ast is not None
        assert "�" in json.dumps(ast, ensure_ascii=False)
        return

    assert ast == case["ast"]
    assert errors == case["errors"]
