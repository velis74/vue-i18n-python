"""The Python runner for the resolve corpus.

``conformance/resolve.json`` holds, for every (object, path) pair, what ``intlify/vue-i18n``'s own
``resolver.ts`` makes of it: the segments ``parse()`` produced, the value ``resolveValue()``
returned, and how ``resolveWithKeyValue()`` answered. This file checks that this port agrees.

A fixture is the contract and the two ports are the things being held to it. If a change here makes
a case fail, the port is wrong until proven otherwise - do not edit the corpus to match the port.
"""

import json

from pathlib import Path

import pytest

from .resolver import (
    _array_index,
    _at,
    _format_sub_path,
    _has_own,
    _js_parse_int,
    Actions,
    parse,
    PATH_STATE_MACHINE,
    PathCharTypes,
    resolve_value,
    resolve_with_key_value,
    States,
    strip_quotes,
)

CORPUS = Path(__file__).resolve().parent.parent.parent / "conformance" / "resolve.json"


def _load() -> dict:
    with CORPUS.open(encoding="utf-8") as fh:
        return json.load(fh)


def _case_id(case: dict) -> str:
    return repr(case["path"])[:40]


CORPUS_DATA = _load()
CASES = CORPUS_DATA["cases"]


def test_corpus_is_present_and_populated() -> None:
    """A corpus that silently shrank to nothing would let every other test in this file pass."""
    assert len(CASES) >= 200, f"corpus has {len(CASES)} cases; it should only ever grow"
    assert CORPUS_DATA["upstream"].startswith("intlify/vue-i18n@")


@pytest.mark.parametrize("case", CASES, ids=_case_id)
def test_parse_matches_upstream(case: dict) -> None:
    assert parse(case["path"]) == case["keys"]


@pytest.mark.parametrize("case", CASES, ids=_case_id)
def test_resolve_value_matches_upstream(case: dict) -> None:
    assert resolve_value(case["obj"], case["path"]) == case["value"]


@pytest.mark.parametrize("case", CASES, ids=_case_id)
def test_resolve_with_key_value_matches_upstream(case: dict) -> None:
    expected = case["keyValue"]
    result = resolve_with_key_value(case["obj"], case["path"])

    if expected["kind"] == "value":
        assert result == expected["value"]
    elif expected["kind"] == "prototype":
        # DEVIATION, asserted so it cannot widen unnoticed. Upstream's `obj[path]` answers from the
        # prototype chain for these paths - `constructor` and `toString` come back as native
        # functions, `__proto__` as the prototype object. This port reads own properties only, so
        # nothing here can resolve into Python internals.
        assert expected["typeof"] in ("function", "object")
        assert result is None
    else:
        # "undefined" (key absent) and "null" (the object was not an object at all).
        assert result is None


def test_resolve_value_returns_true_and_false_unchanged() -> None:
    """Booleans are values, not absences: `False` must survive the walk that `None` ends."""
    obj = {"yes": True, "no": False, "zero": 0, "blank": ""}
    assert resolve_value(obj, "yes") is True
    assert resolve_value(obj, "no") is False
    assert resolve_value(obj, "zero") == 0
    assert resolve_value(obj, "blank") == ""


def test_empty_path_returns_the_object_itself() -> None:
    """`parse("")` is the empty list, which is truthy in JavaScript - the port must not read it
    as "no segments, therefore no result"."""
    obj = {"a": 1}
    assert resolve_value(obj, "") is obj


def test_list_length_is_an_own_property() -> None:
    """A JavaScript array really does answer `hasOwn(arr, 'length')`, so upstream resolves it."""
    assert resolve_value({"items": ["a", "b", "c"]}, "items.length") == 3
    assert resolve_value({"items": ["a", "b"]}, "items.2") is None


def test_paths_cannot_reach_python_internals() -> None:
    """The whole point of resolving through own keys only: no attribute is ever read.

    The single-segment names matter as much as the dotted ones - `resolve_with_key_value` takes the
    whole path as one key, so a bare "keys" or "copy" is exactly the shape that would leak if it
    ever fell back to `getattr`.
    """
    obj = {"a": {"b": "x"}, "arr": [1, 2]}
    for path in (
        "keys",
        "items",
        "values",
        "copy",
        "pop",
        "get",
        "__class__",
        "__init__",
        "__builtins__",
        "a.__class__",
        "a.__dict__",
        "a.keys",
        "a.__init__",
        "arr.append",
        "arr.__class__",
        "a.__class__.__mro__",
        "a.b.upper",
        "a.b.__class__",
    ):
        assert resolve_value(obj, path) is None, path
        assert resolve_with_key_value(obj, path) is None, path
        assert resolve_with_key_value([1, 2], path) is None, path


def test_message_ast_fields_are_not_walkable() -> None:
    """A precompiled message is not a key-value structure, so its own field names must not resolve."""
    ast = {"t": 0, "b": {"t": 2, "i": [{"t": 3, "v": "hi"}]}}
    assert resolve_value({"msg": ast}, "msg") is ast
    assert resolve_value({"msg": ast}, "msg.b") is None
    assert resolve_value({"msg": ast}, "msg.t") is None
    # Not a resource node (type 1), so nothing is guarded and "b" resolves normally.
    assert resolve_value({"msg": {"t": 1, "b": "plural"}}, "msg.b") == "plural"


def test_a_boolean_type_field_is_not_an_ast() -> None:
    """`False == 0` in Python but `false === 0` is false in JavaScript; the guard must not fire."""
    assert resolve_value({"msg": {"t": False, "b": "value"}}, "msg.b") == "value"


def test_the_invalid_leading_zero_guard_rejects_an_empty_hex_prefix() -> None:
    """The one shape `_format_sub_path`'s guard exists for: a `0x` with no hex digit behind it.

    `parseInt` sniffs the radix prefix even with no radix argument, so `parseInt('0x')` has nothing
    left to read and is NaN, while `parseInt('0b')` stops at the 'b' and is 0. That is the whole
    reach of the guard, and it is what makes `[0x]` a parse error and `[0b]` a dynamic key.
    """
    for text in ("0x", "0X", "0xg", "0x ", "0x\t"):
        assert _js_parse_int(text) is None, text
        assert _format_sub_path(text) is False, text

    for text in ("0", "00", "0x10", "0abc", "0.", "0-", "0" * 40, "0١", "0b"):
        assert _js_parse_int(text) is not None, text
        assert _format_sub_path(text) is not False, text


def test_an_empty_hex_prefix_fails_the_whole_parse() -> None:
    """`_format_sub_path` returning False aborts `parse`, so the path resolves to nothing at all."""
    for path in ("a[0x]", "a[0X]", "a[0xg]", "a[0x ]", "[0x]", "nested[0x]"):
        assert parse(path) is None, path

    assert parse("a[0b]") == ["a", "*0b"]
    assert parse("a[0x10]") == ["a", "*0x10"]
    assert parse("a[01]") == ["a", "01"]
    # The guard reads the untrimmed sub-path, so a leading space takes `0x` out of its reach - it is
    # `trimmed` that is then tested for literalness. Upstream's asymmetry, reproduced.
    assert parse("a[ 0x]") == ["a", "*0x"]


def test_a_digit_run_too_long_for_int_is_simply_absent() -> None:
    """A path segment is user input; no length of it may turn a lookup into an exception.

    CPython raises on `int()` above 4300 digits. Upstream compares strings and never converts, so
    it answers "no such key" at any width, and so must this.
    """
    for width in (4300, 4301, 5000, 20000):
        digits = "9" * width
        assert resolve_value({"items": ["a"]}, f"items.{digits}") is None, width
        assert resolve_value([1, 2], digits) is None, width
        assert resolve_with_key_value([1, 2], digits) is None, width
        assert _has_own([1, 2], digits) is False, width


def test_array_index_is_the_length_and_the_regex_and_nothing_else() -> None:
    """The width short-circuit must decide exactly what the arithmetic would have decided.

    It is an early "out of range", so the only way it can be wrong is by rejecting an index that is
    in range - which is what this compares, at every length where the decimal width changes.
    """
    keys = ["0", "1", "9", "10", "11", "99", "100", "101", "999", "1000", "01", "1.0", "+1", "-1", "", "١٢٣"]
    for length in (0, 1, 2, 9, 10, 11, 99, 100, 101, 1000):
        seq = [None] * length
        for key in keys:
            canonical = key.isascii() and key.isdigit() and (key == "0" or key[0] != "0")
            expected = int(key) if canonical and int(key) < length else None
            assert _array_index(seq, key) == expected, (length, key)
        # No list here is 4301 digits long, so the short-circuit has to reject this one on width
        # alone - and reach no int() while doing it.
        assert _array_index(seq, "9" * 4301) is None, length


def test_reading_past_either_end_of_a_path_is_absence_not_wraparound() -> None:
    """`_at` is JavaScript indexing, where out of range is `undefined` at *both* ends.

    `parse` only ever reads forwards, so the negative half is a guard nothing currently trips - but
    without it Python would answer with the character at the other end of the path, which is a whole
    different key rather than an error, so it is pinned rather than left to inspection.
    """
    assert _at("abc", 0) == "a"
    assert _at("abc", 2) == "c"
    assert _at("abc", 3) is None
    assert _at("abc", -1) is None
    assert _at("", 0) is None


def test_only_one_end_of_path_cell_carries_an_action() -> None:
    """`parse` assigns `new_char = c` with `c` None past the end of the path; this is why that is safe.

    The corpus cannot see the difference - an action that ignored `new_char` and one that could not
    reach it look the same from outside - so the claim is pinned on the table instead. PUSH reads
    `key`; if another END_OF_FAIL cell ever gained an action, `None` would reach an APPEND.
    """
    at_end = {
        state: cells[PathCharTypes.END_OF_FAIL].action
        for state, cells in PATH_STATE_MACHINE.items()
        if cells.get(PathCharTypes.END_OF_FAIL) is not None and cells[PathCharTypes.END_OF_FAIL].action is not None
    }
    assert at_end == {States.IN_IDENT: Actions.PUSH}


def test_strip_quotes_leaves_the_empty_string_alone() -> None:
    """The guard that stands in for JavaScript's NaN, which is not equal to itself.

    `''.charCodeAt(0)` is NaN upstream, so the comparison of the two ends fails and the string comes
    back untouched. Comparing `ord()` of nothing would be an IndexError, and comparing None to None
    would be true and slice a string that has no quotes to lose.
    """
    assert strip_quotes("") == ""
    assert strip_quotes("'hello'") == "hello"
    assert strip_quotes('"hello"') == "hello"
    assert strip_quotes("'hello") == "'hello"
    assert strip_quotes("hello") == "hello"


def test_a_callable_container_ends_the_walk() -> None:
    """`is_function` is dead upstream and alive here, and both ports answer None.

    In JavaScript `typeof fn` is "function", so `isObject` turns every callable away before this
    check is reached. In Python `callable()` and `isinstance(_, dict)` are independent, so a
    callable dict gets past `is_object` and this is the check that stops it. Verified against
    upstream: `resolveValue({a: fn}, 'a.b')` is null there too.
    """

    class CallableDict(dict):
        def __call__(self) -> None:  # pragma: no cover - never called, only ever inspected
            raise AssertionError("the resolver must not invoke a container")

    container = CallableDict({"b": "reachable only by calling"})
    assert resolve_value({"a": container}, "a.b") is None
    assert resolve_value(container, "b") is None
    # The container itself is still a value, exactly as a function is in JavaScript.
    assert resolve_value({"a": container}, "a") is container


def test_the_path_cache_does_not_change_answers() -> None:
    """The cache is keyed by path alone, so the same path over two different objects must not stick."""
    first = {"a": {"b": "first"}}
    second = {"a": {"b": "second"}}
    assert resolve_value(first, "a.b") == "first"
    assert resolve_value(second, "a.b") == "second"
    assert resolve_value(first, "a.b") == "first"
