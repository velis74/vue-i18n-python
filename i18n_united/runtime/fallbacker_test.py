"""The Python runner for the fallback corpus.

``conformance/fallback.json`` holds, for every (start locale, ``fallbackLocale``) pair, what
``intlify/vue-i18n``'s own ``fallbackWithSimple`` and ``fallbackWithLocaleChain`` return. This file
checks that this port returns exactly that; its TypeScript twin reads the same file.

A fixture is the contract and the two ports are the things being held to it. If a change here makes
a case fail, the port is wrong until proven otherwise - do not edit the corpus to match the port.

The tests below the corpus runner are not extra cases: each one pins a piece of upstream behaviour
that is surprising enough that a later "cleanup" would plausibly break it. Their expected values were
read off upstream too.
"""

import json

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from . import fallbacker
from .errors import CoreErrorCodes
from .fallbacker import fallback_with_locale_chain, fallback_with_simple, FallbackContext, get_locale, resolve_locale

CORPUS = Path(__file__).resolve().parent.parent.parent / "conformance" / "fallback.json"


def _load() -> dict:
    with CORPUS.open(encoding="utf-8") as fh:
        return json.load(fh)


def _case_id(case: dict) -> str:
    return f"{case['start']!r}+{json.dumps(case['fallback'])}"[:60]


CORPUS_DATA = _load()
CASES = CORPUS_DATA["cases"]


def test_corpus_is_present_and_populated() -> None:
    """A corpus that silently shrank to nothing would let every other test in this file pass."""
    assert len(CASES) >= 361, f"corpus has {len(CASES)} cases; it should only ever grow"
    assert CORPUS_DATA["upstream"].startswith("intlify/vue-i18n@")


@pytest.mark.parametrize("case", CASES, ids=_case_id)
def test_fallback_matches_upstream(case: dict) -> None:
    # A fresh context per case: the chain cache is keyed by the start locale alone, so a shared one
    # would make a case's result depend on which cases ran before it.
    assert fallback_with_simple(None, case["fallback"], case["start"]) == case["simple"]
    assert fallback_with_locale_chain(FallbackContext(), case["fallback"], case["start"]) == case["chain"]


def test_chain_cache_is_keyed_by_the_start_locale_alone() -> None:
    """Upstream's cache ignores the fallback, so a second call gets the first call's answer.

    Verified against upstream: both calls return ``['sl-SI', 'sl', 'de']``, and ``fr`` never appears.
    """
    ctx = FallbackContext()
    assert fallback_with_locale_chain(ctx, ["de"], "sl-SI") == ["sl-SI", "sl", "de"]
    assert fallback_with_locale_chain(ctx, ["fr"], "sl-SI") == ["sl-SI", "sl", "de"]


def test_chain_cache_lives_on_the_context_and_is_reused() -> None:
    ctx = FallbackContext()
    first = fallback_with_locale_chain(ctx, ["en"], "sl-SI")
    assert ctx.locale_chain_cache == {"sl-SI": ["sl-SI", "sl", "en"]}
    # The very same list, not an equal one - upstream hands back the cached array itself.
    assert fallback_with_locale_chain(ctx, ["en"], "sl-SI") is first


def test_an_empty_block_stops_the_subtag_walk() -> None:
    """An empty array is truthy in JavaScript, so ``sl-SI`` does not go on to ``sl`` here.

    This is the one place where porting Python's truthiness instead of JavaScript's would silently
    change an answer, which is why ``_js_truthy`` exists.
    """
    assert fallback_with_locale_chain(FallbackContext(), {"sl-SI": []}, "sl-SI") == ["sl-SI"]
    # ... whereas a locale with no entry at all does walk down to its language subtag.
    assert fallback_with_locale_chain(FallbackContext(), {"hr": []}, "sl-SI") == ["sl-SI", "sl"]


def test_an_array_fallback_is_indexed_like_the_javascript_object_it_is() -> None:
    """``blocks['0']`` on an array reads element 0, so a locale named ``0`` pulls in a whole block."""
    assert fallback_with_locale_chain(FallbackContext(), [["de", "fr"], "en"], "0") == ["0", "de", "fr", "en"]
    # `length` is a property too. Here it only has to be truthy and not an array, so the chain is
    # the ordinary one - but the port must still not treat it as "no entry".
    assert fallback_with_locale_chain(FallbackContext(), ["en", "de"], "length") == ["length", "en", "de"]


def test_a_cyclic_map_terminates() -> None:
    fallback = {"a": ["b"], "b": ["a"]}
    assert fallback_with_locale_chain(FallbackContext(), fallback, "a") == ["a", "b"]
    assert fallback_with_locale_chain(FallbackContext(), fallback, "b") == ["b", "a"]


def test_a_bang_suffix_stops_the_chain_but_leaves_a_duplicate_behind() -> None:
    """``!`` means "stop here". The already-in-chain test misses the ``!`` form, so ``en`` repeats."""
    assert fallback_with_locale_chain(FallbackContext(), ["en", "en!"], "de") == ["de", "en", "en"]
    assert fallback_with_locale_chain(FallbackContext(), ["en!", "en"], "de") == ["de", "en"]
    # Every "!" is stripped, wherever it sits, but only a trailing one stops the walk.
    assert fallback_with_locale_chain(FallbackContext(), ["e!n", "de"], "sl-SI") == ["sl-SI", "sl", "en", "de"]


def test_simple_takes_a_maps_keys_and_ignores_the_context() -> None:
    fallback = {"en-US": ["en"], "default": ["ja"]}
    assert fallback_with_simple(None, fallback, "sl-SI") == ["sl-SI", "en-US", "default"]
    assert fallback_with_simple(None, False, "sl-SI") == ["sl-SI"]
    assert fallback_with_simple(None, "sl-SI", "sl-SI") == ["sl-SI"]


@pytest.mark.parametrize(
    "locale",
    ["toString", "constructor", "valueOf", "hasOwnProperty", "toLocaleString", "__proto__", "isPrototypeOf"],
)
def test_a_locale_named_after_an_object_prototype_member_ends_the_block(locale: str) -> None:
    """``blocks[locale]`` is a plain property read upstream, so it answers from the prototype chain.

    ``{'a': ['toString', 'fr']}`` therefore never reaches ``fr``: the read hands back
    ``Object.prototype.toString``, which is truthy and not an array, so ``follow`` stops being a
    boolean and the rest of the block is abandoned. Verified against upstream for each name here.
    """
    fallback = {"a": [locale, "fr"], "default": ["de"]}
    assert fallback_with_locale_chain(FallbackContext(), fallback, "a") == ["a", locale, "de"]


def test_an_own_key_still_wins_over_the_prototype() -> None:
    """A map really carrying ``__proto__`` is the JSON case, and JSON gives an *own* property.

    ``JSON.parse('{"__proto__": ...}')`` defines the key instead of reassigning the prototype, so
    upstream follows it like any other entry - and so must a Python ``dict`` that has the key.
    """
    fallback = {"__proto__": ["fr"], "a": ["__proto__"], "default": ["de"]}
    assert fallback_with_locale_chain(FallbackContext(), fallback, "a") == ["a", "__proto__", "fr", "de"]


@pytest.mark.parametrize("locale", ["map", "constructor", "toString", "length", "__proto__"])
def test_a_locale_named_after_an_array_prototype_member_ends_the_block(locale: str) -> None:
    """The same read against an array-shaped ``fallbackLocale``, which reaches ``Array.prototype``.

    The nested block is what makes the hit visible: an entry that follows the prototype-named one is
    never appended. ``length`` is an own property (the count, here 2) and ``__proto__`` is
    ``Array.prototype``, which *is* an array - but every one of them is truthy and none is a boolean,
    so all five end the block the same way.
    """
    fallback = [[locale, "fr"], "en"]
    assert fallback_with_locale_chain(FallbackContext(), fallback, "0") == ["0", locale, "en"]


def test_simple_lists_a_maps_keys_in_object_keys_order() -> None:
    """``Object.keys`` is not insertion order: array-index keys come first, ascending numerically.

    ``'01'``, ``'-1'``, ``'1.5'`` and ``'4294967295'`` (one past the last array index) are not
    canonical array indices, so they stay in insertion order among the string keys.
    """
    fallback = {"b": ["x"], "2": ["x"], "1": ["x"], "a": ["x"]}
    assert fallback_with_simple(None, fallback, "start") == ["start", "1", "2", "b", "a"]

    edges = {"10": ["x"], "9": ["x"], "01": ["x"], "": ["x"], "4294967295": ["x"], "4294967294": ["x"]}
    expected = ["start", "9", "10", "4294967294", "01", "", "4294967295"]
    assert fallback_with_simple(None, edges, "start") == expected


def test_unique_merges_what_a_javascript_set_merges_and_nothing_else() -> None:
    """``[...new Set(...)]`` compares with SameValueZero, which Python's ``==`` gets wrong twice.

    JavaScript has one numeric type, so ``1`` and ``1.0`` are one member - Python keeps them apart.
    And ``true`` is not ``1`` there, while Python's ``True == 1`` would merge them. Both directions
    are read off upstream.
    """
    assert fallback_with_simple(None, [1, "1", True, 1.0], "a") == ["a", 1, "1", True]
    assert fallback_with_simple(None, [True, 1, False, 0, "true"], "a") == ["a", True, 1, False, 0, "true"]
    # SameValueZero calls +0 and -0 the same member, and so does Python's float comparison.
    assert fallback_with_simple(None, [0, -0.0, 0.0], "a") == ["a", 0]
    # Objects are compared by identity: two equal arrays are two members.
    assert fallback_with_simple(None, [["en"], ["en"]], "a") == ["a", ["en"], ["en"]]


@dataclass
class _Holder:
    """Something with a ``locale`` attribute, standing in for both a context and an options object."""

    locale: Any = None


@pytest.fixture(autouse=True)
def _forget_the_resolved_locale() -> None:
    """``_resolved_locale`` is module state upstream too, so one test's detector must not leak."""
    fallbacker._resolved_locale = None


def test_get_locale_prefers_the_option_but_only_when_it_names_one() -> None:
    context = _Holder(locale="sl-SI")
    assert get_locale(context, _Holder(locale="de-DE")) == "de-DE"
    assert get_locale(context, _Holder()) == "sl-SI"
    # `options.locale != null`, not `options.locale`: an empty string is an override.
    assert get_locale(context, _Holder(locale="")) == ""
    # An options object without a `locale` at all is `undefined` upstream, i.e. no override either.
    assert get_locale(context, object()) == "sl-SI"


def test_resolve_locale_calls_a_detector_and_remembers_its_answer() -> None:
    calls = []

    def detector() -> str:
        calls.append(1)
        return "ja"

    assert resolve_locale(detector) == "ja"
    assert calls == [1]

    # Without `resolved_once` the detector is asked again, even though the answer is remembered.
    assert resolve_locale(detector) == "ja"
    assert calls == [1, 1]

    detector.resolved_once = True
    assert resolve_locale(detector) == "ja"
    assert calls == [1, 1], "a resolved_once detector answers from the remembered locale"


def test_a_resolved_once_detector_still_runs_when_nothing_is_remembered_yet() -> None:
    def detector() -> str:
        return "hr"

    detector.resolved_once = True
    assert resolve_locale(detector) == "hr"


def test_the_remembered_locale_is_process_wide_and_not_per_detector() -> None:
    """Upstream's ``_resolveLocale`` is one module-level variable, so any detector overwrites it.

    A ``resolvedOnce`` detector then gets whatever the *last* detector produced, which is startling
    enough to pin: reproduce it, do not tidy it.
    """

    def first() -> str:
        return "en"

    def second() -> str:
        return "de"

    second.resolved_once = True
    assert resolve_locale(first) == "en"
    assert resolve_locale(second) == "en", "the second detector is never called"


@pytest.mark.parametrize(
    ("locale", "code"),
    [
        (None, CoreErrorCodes.NOT_SUPPORT_LOCALE_TYPE),
        (42, CoreErrorCodes.NOT_SUPPORT_LOCALE_TYPE),
        (["en"], CoreErrorCodes.NOT_SUPPORT_LOCALE_TYPE),
    ],
)
def test_resolve_locale_refuses_a_locale_that_is_neither_a_string_nor_callable(locale: Any, code: int) -> None:
    with pytest.raises(SyntaxError) as excinfo:
        resolve_locale(locale)
    assert excinfo.value.code == code
    assert "cannot support locale type" in str(excinfo.value)


def test_resolve_locale_refuses_an_asynchronous_detector_before_calling_it() -> None:
    """Upstream reads ``locale.constructor.name`` and never calls an ``AsyncFunction``."""
    calls = []

    async def detector() -> str:
        calls.append(1)
        return "ja"

    with pytest.raises(SyntaxError) as excinfo:
        resolve_locale(detector)
    assert excinfo.value.code == CoreErrorCodes.NOT_SUPPORT_LOCALE_ASYNC_FUNCTION
    assert calls == []


def test_resolve_locale_refuses_a_plain_detector_that_returned_an_awaitable() -> None:
    """The other half of upstream's check: a `Function` is called, and its promise is refused after."""

    async def later() -> str:
        return "ja"

    pending = later()
    try:
        with pytest.raises(SyntaxError) as excinfo:
            resolve_locale(lambda: pending)
        assert excinfo.value.code == CoreErrorCodes.NOT_SUPPORT_LOCALE_PROMISE_VALUE
    finally:
        pending.close()
