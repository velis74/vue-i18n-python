"""The Python runner for the translate corpus.

``conformance/translate.json`` holds one `translate()` call per case and the string
`@intlify/core-base` returned for it. This is the corpus that matters most: it exercises the whole
library through the entry point an application actually uses.

The chain every case shares — `{'sl-SI': ['sl', 'en'], 'sl': ['en'], default: ['en']}` — means the
fallback walk, the missing-key path and linked-message resolution are all live in most cases rather
than being tested in isolation.
"""

import json

from pathlib import Path

import pytest

from .context import create_core_context
from .fallbacker import fallback_with_locale_chain
from .translate import translate

CORPUS = Path(__file__).resolve().parent.parent.parent / "conformance" / "translate.json"

with CORPUS.open(encoding="utf-8") as _fh:
    CORPUS_DATA = json.load(_fh)

CASES = CORPUS_DATA["cases"]
MESSAGES = CORPUS_DATA["messages"]
FALLBACK_LOCALE = CORPUS_DATA["fallbackLocale"]


def _context(locale: str):
    return create_core_context(
        locale=locale,
        fallback_locale=FALLBACK_LOCALE,
        messages=json.loads(json.dumps(MESSAGES)),
        missing_warn=False,
        fallback_warn=False,
        # The corpus was recorded with the chain fallbacker registered, which is what
        # `@intlify/core` does and what a vue-i18n application therefore gets.
        locale_fallbacker=fallback_with_locale_chain,
    )


def _args(case: dict) -> list:
    """Rebuild the call. JSON gives dicts and lists, which is what the Python signature takes."""
    return case["args"]


def test_corpus_is_present_and_populated() -> None:
    assert len(CASES) >= 57, f"corpus has {len(CASES)} cases; it should only ever grow"
    assert CORPUS_DATA["upstream"].startswith("intlify/vue-i18n@")
    assert MESSAGES
    assert FALLBACK_LOCALE


def test_no_case_recorded_an_exception() -> None:
    """If upstream threw, the case cannot say what correct behaviour is - and none should."""
    assert [c for c in CASES if c["threw"] is not None] == []


@pytest.mark.parametrize("case", CASES, ids=lambda c: f"{c['locale']}:{c['args'][0]}")
def test_translate_matches_core_base(case: dict) -> None:
    assert translate(_context(case["locale"]), *_args(case)) == case["result"]


def test_a_reloaded_message_is_not_served_from_the_compilation_cache() -> None:
    """Compiled messages are cached by (locale, key, source), so editing a resource takes effect.

    Keying on locale and key alone is the obvious mistake and it survives every corpus case, because
    a corpus never mutates its resource. A lazily loaded locale, a hot reload, or a test that edits
    messages between calls all do.
    """
    messages = {"sl": {"k": "prva različica"}}
    ctx = create_core_context(
        locale="sl", fallback_locale="sl", messages=messages, missing_warn=False, fallback_warn=False
    )
    assert translate(ctx, "k") == "prva različica"

    messages["sl"]["k"] = "druga različica"
    assert translate(ctx, "k") == "druga različica"
