"""Turning a dotted message key into a value inside a nested message object.

Port of ``packages/core-base/src/resolver.ts``.

Two things a reader has to hold on to.

**JavaScript object semantics are part of the contract.** Upstream reads a message resource that
came out of ``JSON.parse``, so the only two container types it ever walks are objects and arrays;
here that is ``dict`` and ``list``, and :func:`is_object` says so. Every lookup goes through
:func:`_has_own`, which models JavaScript's *own* properties: a ``dict``'s keys, and for a ``list``
the canonical index strings plus ``"length"`` — because ``hasOwn(arr, 'length')`` really is true in
JavaScript and ``t('items.length')`` really does return the count. Nothing is ever read as a Python
attribute, so a path can never reach into an object's internals no matter what it spells.

**``None`` stands in for ``undefined``.** Upstream distinguishes a stored ``null`` from an absent
value; this port cannot, and does not need to — see the note in :func:`resolve_value`.
"""

import re

from dataclasses import dataclass
from enum import IntEnum
from typing import Any

Path = str
PathValue = Any


class Actions(IntEnum):
    APPEND = 0
    PUSH = 1
    INC_SUB_PATH_DEPTH = 2
    PUSH_SUB_PATH = 3


class States(IntEnum):
    BEFORE_PATH = 0
    IN_PATH = 1
    BEFORE_IDENT = 2
    IN_IDENT = 3
    IN_SUB_PATH = 4
    IN_SINGLE_QUOTE = 5
    IN_DOUBLE_QUOTE = 6
    AFTER_PATH = 7
    ERROR = 8


class PathCharTypes:
    """Upstream's ``PathCharTypes`` const enum, values unchanged because they are also table keys.

    ``WORKSPACE`` is upstream's spelling of "whitespace" and ``ASTARISK`` of "asterisk"; both are
    kept as they are so a reader can grep the two files against each other.
    """

    WORKSPACE = "w"
    IDENT = "i"
    LEFT_BRACKET = "["
    RIGHT_BRACKET = "]"
    DOT = "."
    ASTARISK = "*"
    ZERO = "0"
    ELSE = "l"
    END_OF_FAIL = "o"
    SINGLE_QUOTE = "'"
    DOUBLE_QUOTE = '"'


@dataclass(frozen=True)
class Transition:
    """One cell of the state table: the next state, and optionally an action to run first."""

    state: States
    action: Actions | None = None


# Upstream's table holds either a `[state, action?]` tuple or the bare `States.ERROR`, and tells the
# two apart with `transition === States.ERROR`. No cell is ever a tuple whose state is ERROR, so a
# single `Transition` type carrying ERROR in `state` says exactly the same thing with one less case.
_ERROR = Transition(States.ERROR)

PATH_STATE_MACHINE: dict[States, dict[str, Transition]] = {
    States.BEFORE_PATH: {
        PathCharTypes.WORKSPACE: Transition(States.BEFORE_PATH),
        PathCharTypes.IDENT: Transition(States.IN_IDENT, Actions.APPEND),
        PathCharTypes.LEFT_BRACKET: Transition(States.IN_SUB_PATH),
        PathCharTypes.END_OF_FAIL: Transition(States.AFTER_PATH),
    },
    States.IN_PATH: {
        PathCharTypes.WORKSPACE: Transition(States.IN_PATH),
        PathCharTypes.DOT: Transition(States.BEFORE_IDENT),
        PathCharTypes.LEFT_BRACKET: Transition(States.IN_SUB_PATH),
        PathCharTypes.END_OF_FAIL: Transition(States.AFTER_PATH),
    },
    # No END_OF_FAIL and no ELSE here, which is what makes a path ending in a dot ("a.") a parse
    # error rather than a path with a trailing empty segment.
    States.BEFORE_IDENT: {
        PathCharTypes.WORKSPACE: Transition(States.BEFORE_IDENT),
        PathCharTypes.IDENT: Transition(States.IN_IDENT, Actions.APPEND),
        PathCharTypes.ZERO: Transition(States.IN_IDENT, Actions.APPEND),
    },
    States.IN_IDENT: {
        PathCharTypes.IDENT: Transition(States.IN_IDENT, Actions.APPEND),
        PathCharTypes.ZERO: Transition(States.IN_IDENT, Actions.APPEND),
        PathCharTypes.WORKSPACE: Transition(States.IN_PATH, Actions.PUSH),
        PathCharTypes.DOT: Transition(States.BEFORE_IDENT, Actions.PUSH),
        PathCharTypes.LEFT_BRACKET: Transition(States.IN_SUB_PATH, Actions.PUSH),
        PathCharTypes.END_OF_FAIL: Transition(States.AFTER_PATH, Actions.PUSH),
    },
    States.IN_SUB_PATH: {
        PathCharTypes.SINGLE_QUOTE: Transition(States.IN_SINGLE_QUOTE, Actions.APPEND),
        PathCharTypes.DOUBLE_QUOTE: Transition(States.IN_DOUBLE_QUOTE, Actions.APPEND),
        PathCharTypes.LEFT_BRACKET: Transition(States.IN_SUB_PATH, Actions.INC_SUB_PATH_DEPTH),
        PathCharTypes.RIGHT_BRACKET: Transition(States.IN_PATH, Actions.PUSH_SUB_PATH),
        PathCharTypes.END_OF_FAIL: _ERROR,
        PathCharTypes.ELSE: Transition(States.IN_SUB_PATH, Actions.APPEND),
    },
    States.IN_SINGLE_QUOTE: {
        PathCharTypes.SINGLE_QUOTE: Transition(States.IN_SUB_PATH, Actions.APPEND),
        PathCharTypes.END_OF_FAIL: _ERROR,
        PathCharTypes.ELSE: Transition(States.IN_SINGLE_QUOTE, Actions.APPEND),
    },
    States.IN_DOUBLE_QUOTE: {
        PathCharTypes.DOUBLE_QUOTE: Transition(States.IN_SUB_PATH, Actions.APPEND),
        PathCharTypes.END_OF_FAIL: _ERROR,
        PathCharTypes.ELSE: Transition(States.IN_DOUBLE_QUOTE, Actions.APPEND),
    },
}

# ECMAScript's `\s` (WhiteSpace + LineTerminator), spelled out. Python's `\s` is a different set on
# both ends - it has \x1c-\x1f and \x85, it lacks the BOM - and `str.strip()` with no argument uses
# yet another one. A path is user input, so the two ports have to agree on it character for
# character rather than nearly.
_JS_WHITESPACE = (
    "\t\n\v\f\r \u00a0\u1680"
    "\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a"
    "\u2028\u2029\u202f\u205f\u3000\ufeff"
)
_JS_WHITESPACE_CLASS = r"\t\n\v\f\r \u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000\ufeff"

# Upstream's `literalValueRE`. `[0-9]` rather than `\d` because JavaScript's `\d` is ASCII-only
# while Python's also matches Devanagari and Arabic-Indic digits, and `\Z` rather than `$` because
# Python's `$` would also match in front of a trailing newline.
_LITERAL_VALUE_RE = re.compile(
    rf"^[{_JS_WHITESPACE_CLASS}]?(?:true|false|-?[0-9.]+|'[^']*'|\"[^\"]*\")[{_JS_WHITESPACE_CLASS}]?\Z"
)

# A JavaScript array's own properties are exactly the canonical index strings - decimal, no sign, no
# leading zero, no fraction - below its length. "01", "1.0", "+0" and "-1" are none of them.
_ARRAY_INDEX_RE = re.compile(r"^(?:0|[1-9][0-9]*)\Z")


def _at(buf: str, index: int) -> str | None:
    """``buf[index]`` with JavaScript's out-of-range behaviour: ``None`` rather than an exception."""
    if index < 0 or index >= len(buf):
        return None
    return buf[index]


def _js_trim(value: str) -> str:
    return value.strip(_JS_WHITESPACE)


def _js_parse_int(value: str) -> int | None:
    """``parseInt(value)`` — leading whitespace and junk tolerated. ``None`` where JavaScript says NaN.

    Only :func:`_format_sub_path` calls it, and only to ask whether a sub-path that starts with a
    zero is one of the handful that ``parseInt`` cannot read at all; see there.
    """
    text = _js_trim(value)
    sign = 1
    if text[:1] in ("+", "-"):
        sign = -1 if text[0] == "-" else 1
        text = text[1:]
    # parseInt sniffs a 0x prefix even with no radix argument, so `parseInt('0x10')` is 16.
    if text[:2].lower() == "0x":
        digits = re.match(r"[0-9a-fA-F]*", text[2:]).group(0)
        return sign * int(digits, 16) if digits else None
    digits = re.match(r"[0-9]*", text).group(0)
    return sign * int(digits) if digits else None


def is_literal(exp: str) -> bool:
    """Is the expression a literal value — a boolean, a number, or a quoted string?"""
    return _LITERAL_VALUE_RE.match(exp) is not None


def strip_quotes(value: str) -> str:
    """Drop a matching pair of single or double quotes from the ends of the string."""
    # Upstream reads `charCodeAt` past both ends of an empty string and gets NaN, which is not equal
    # to itself, so the empty string falls through unchanged. `None == None` would be true here, so
    # the empty string is taken out first instead of being allowed to compare equal to itself.
    if not value:
        return value
    first, last = ord(value[0]), ord(value[-1])
    return value[1:-1] if first == last and first in (0x22, 0x27) else value


def get_path_char_type(ch: str | None) -> str:
    """Classify one character of a key path.

    Plain space (0x20) is deliberately absent from the whitespace list: upstream treats it as part
    of an identifier, so ``a b`` is the single key ``"a b"`` and not two keys. A tab is not, so
    ``a\\tb`` is a parse error.

    Upstream walks the path one UTF-16 code unit at a time and reads ``charCodeAt(0)``, so an emoji
    reaches here twice, as two surrogate halves; here it arrives once, as one code point. Neither a
    surrogate half nor an astral code point is in any of the three lists below, so both fall through
    to IDENT and the key that gets assembled is the same string either way. Unlike the compiler,
    this file reports no offsets, so the difference in step size costs nothing.
    """
    if ch is None:
        return PathCharTypes.END_OF_FAIL

    code = ord(ch)

    if code in (0x5B, 0x5D, 0x2E, 0x22, 0x27):  # [ ] . " '
        return ch

    if code in (0x5F, 0x24, 0x2D):  # _ $ -
        return PathCharTypes.IDENT

    # Tab, LF, CR, NBSP, BOM, LS, PS.
    if code in (0x09, 0x0A, 0x0D, 0xA0, 0xFEFF, 0x2028, 0x2029):
        return PathCharTypes.WORKSPACE

    return PathCharTypes.IDENT


def _format_sub_path(path: str) -> str | bool:
    """Reduce a bracketed sub-path to its plain form, or mark it dynamic with a leading ``*``.

    ``False`` means the sub-path is invalid and the whole parse fails.
    """
    trimmed = _js_trim(path)

    # Upstream's "invalid leading 0" guard. It does fire, on exactly one shape: parseInt sniffs the
    # 0x/0X radix prefix even with no radix argument, and with no hex digit behind it there is
    # nothing left to parse, so `parseInt('0x')` is NaN where `parseInt('0b')` is 0. That makes
    # `a[0x]`, `a[0X]`, `a[0xg]` and `a[0x ]` parse errors while `a[0x10]` (16) and `a[0b]` are
    # ordinary dynamic keys. The test is on the *untrimmed* path, which is upstream's own asymmetry:
    # `a[ 0x]` never reaches the guard and comes out as the dynamic key `*0x`.
    if path[0:1] == "0" and _js_parse_int(path) is None:
        return False

    return strip_quotes(trimmed) if is_literal(trimmed) else PathCharTypes.ASTARISK + trimmed


def parse(path: Path) -> list[str] | None:
    """Split a key path into its segments. ``None`` — upstream's ``undefined`` — on a parse error."""
    keys: list[str] = []
    index = -1
    mode = States.BEFORE_PATH
    sub_path_depth = 0
    key: str | None = None
    new_char: str | None = None

    def append() -> None:
        nonlocal key
        if key is None:
            key = new_char
        else:
            key = key + new_char

    def push() -> None:
        nonlocal key
        # `key is not None`, not truthiness: "" is a key a quoted sub-path can legitimately produce.
        if key is not None:
            keys.append(key)
            key = None

    def inc_sub_path_depth() -> None:
        nonlocal sub_path_depth
        append()
        sub_path_depth += 1

    def push_sub_path() -> bool | None:
        nonlocal sub_path_depth, mode, key
        if sub_path_depth > 0:
            sub_path_depth -= 1
            mode = States.IN_SUB_PATH
            append()
            return None

        sub_path_depth = 0
        if key is None:
            return False
        formatted = _format_sub_path(key)
        if formatted is False:
            return False
        key = formatted
        push()
        return None

    actions = {
        Actions.APPEND: append,
        Actions.PUSH: push,
        Actions.INC_SUB_PATH_DEPTH: inc_sub_path_depth,
        Actions.PUSH_SUB_PATH: push_sub_path,
    }

    def maybe_unescape_quote() -> bool:
        """A backslash before the quote that opened the current segment escapes it.

        The backslash is kept, not dropped, so ``['a\\'b']`` ends up as the *dynamic* key
        ``*'a\\'b'`` rather than as ``a'b``. That is upstream's behaviour, odd as it looks.
        """
        nonlocal index, new_char
        next_char = _at(path, index + 1)
        if (mode is States.IN_SINGLE_QUOTE and next_char == PathCharTypes.SINGLE_QUOTE) or (
            mode is States.IN_DOUBLE_QUOTE and next_char == PathCharTypes.DOUBLE_QUOTE
        ):
            index += 1
            new_char = "\\" + next_char
            append()
            return True
        return False

    # Upstream loops on `mode !== null` and never assigns null, so the loop only ever leaves through
    # one of the three returns below.
    while True:
        index += 1
        c = _at(path, index)

        if c == "\\" and maybe_unescape_quote():
            continue

        char_type = get_path_char_type(c)
        type_map = PATH_STATE_MACHINE[mode]
        transition = type_map.get(char_type, type_map.get(PathCharTypes.ELSE, _ERROR))

        if transition.state is States.ERROR:
            return None

        mode = transition.state
        if transition.action is not None:
            # `c` is None only past the end of the path, and the one end-of-path cell that carries
            # an action is IN_IDENT's PUSH, which does not look at `new_char`.
            new_char = c
            if actions[transition.action]() is False:
                return None

        if mode is States.AFTER_PATH:
            return keys


def is_object(val: Any) -> bool:
    """Port of shared's ``isObject``: true for everything JavaScript calls an object except null.

    A message resource is JSON, so the containers a path can walk are objects and arrays and nothing
    else. Restricting this to ``dict`` and ``list`` is what keeps a crafted path from reaching a
    Python attribute; anything else - a dataclass, a compiled message, a callable - ends the walk
    with ``None``, which is the same answer upstream's AST guard gives for the case that actually
    arises in practice.
    """
    return isinstance(val, (dict, list))


def is_function(val: Any) -> bool:
    return callable(val)


def _array_index(seq: list, key: str) -> int | None:
    if _ARRAY_INDEX_RE.match(key) is None:
        return None
    # A canonical index string carries no leading zero, so one longer than the decimal width of the
    # length is already past the end and needs no conversion to say so. That is not an optimisation:
    # CPython refuses `int()` on more than 4300 digits and raises, while JavaScript never converts
    # an index at all, so without this a long enough run of digits in a path would turn "no such
    # key" into a ValueError. Upstream answers null for it.
    if len(key) > len(str(len(seq))):
        return None
    index = int(key)
    return index if index < len(seq) else None


def _has_own(obj: dict | list, key: str) -> bool:
    """Port of shared's ``hasOwn``, i.e. ``Object.prototype.hasOwnProperty``.

    For a ``dict`` that is simply its keys - Python dicts have no prototype chain to inherit from,
    so ``constructor`` and ``toString`` are absent here exactly as they are absent from
    ``hasOwnProperty`` in JavaScript. For a ``list`` the own properties are the in-range canonical
    index strings and ``length``, which is a real own property of a JavaScript array.
    """
    if isinstance(obj, dict):
        return key in obj
    return key == "length" or _array_index(obj, key) is not None


def _get_own(obj: dict | list, key: str) -> Any:
    if isinstance(obj, dict):
        return obj[key]
    if key == "length":
        return len(obj)
    return obj[_array_index(obj, key)]


_PROPS_BODY = ["b", "body"]
_PROPS_CASES = ["c", "cases"]
_PROPS_STATIC = ["s", "static"]
_PROPS_ITEMS = ["i", "items"]
_PROPS_KEY = ["k", "key"]
_PROPS_MODIFIER = ["m", "modifier"]
_PROPS_VALUE = ["v", "value"]
_PROPS_TYPE = ["t", "type"]

#: Every field name a serialised message AST can use, long form and minified alike. From
#: ``packages/core-base/src/ast.ts``; only this list and :func:`_is_message_ast` are needed here, so
#: the rest of that file is not ported.
AST_NODE_PROPS_KEYS = [
    *_PROPS_BODY,
    *_PROPS_CASES,
    *_PROPS_STATIC,
    *_PROPS_ITEMS,
    *_PROPS_KEY,
    *_PROPS_MODIFIER,
    *_PROPS_VALUE,
    *_PROPS_TYPE,
]


def _resolve_props(node: dict | list, props: list[str]) -> Any:
    for prop in props:
        if _has_own(node, prop):
            value = _get_own(node, prop)
            if value is not None:
                return value
    return None


def _is_message_ast(val: Any) -> bool:
    """Port of ``ast.ts``'s ``isMessageAST``: a serialised resource node, minified or not."""
    if not is_object(val):
        return False
    node_type = _resolve_props(val, _PROPS_TYPE)
    # `resolveType(val) === 0` is false for `false` in JavaScript, but `False == 0` is true in
    # Python, so a boolean type field has to be rejected before the comparison - otherwise
    # `{"t": false, "b": "x"}` would be mistaken for an AST and its "b" would stop resolving.
    if isinstance(node_type, bool) or node_type != 0:
        return False
    return _has_own(val, "b") or _has_own(val, "body")


# Path token cache, unbounded exactly as upstream's is. Message keys come from the application's own
# source, not from user input, so the set of distinct paths is bounded by the code.
_cache: dict[Path, list[str]] = {}


def resolve_with_key_value(obj: Any, path: Path) -> PathValue:
    """Resolve a message with a flat key-value structure: the path is the key, dots and all.

    DEVIATION: upstream is ``isObject(obj) ? obj[path] : null``, a plain property read that answers
    from the prototype chain — ``resolveWithKeyValue({}, 'constructor')`` hands back the ``Object``
    constructor, ``'toString'`` a native function, ``'__proto__'`` the prototype object. This port
    reads own properties only and returns ``None`` for those paths. Reproducing the leak would mean
    resolving a message key into Python internals, which is a worse thing than a documented
    difference on keys no message resource has.
    """
    if not is_object(obj):
        return None
    return _get_own(obj, path) if _has_own(obj, path) else None


def resolve_value(obj: Any, path: Path) -> PathValue:
    """Resolve a message inside a nested structure, following the path segment by segment."""
    if not is_object(obj):
        return None

    # `hit is not None` rather than a truthiness test: parse("") returns an *empty* list, which is
    # truthy in JavaScript and falsy in Python. Getting this wrong would make the empty path reparse
    # on every call and - worse, below - resolve to None instead of to `obj` itself.
    hit = _cache.get(path)
    if hit is None:
        hit = parse(path)
        if hit is not None:
            _cache[path] = hit

    if hit is None:
        return None

    last: Any = obj
    for key in hit:
        # An AST node is not a key-value structure: a message compiled ahead of time has fields
        # named "b", "i", "v" and so on, and a path must not be able to walk into them.
        if key in AST_NODE_PROPS_KEYS and _is_message_ast(last):
            return None
        if not is_object(last):
            return None
        if not _has_own(last, key):
            return None
        val = _get_own(last, key)
        # Upstream checks for `undefined`, a key that exists with no value. `None` here is also how
        # a JSON null arrives, so a stored null returns None instead of being carried on as `last`.
        # The two agree regardless: a null `last` fails the `is_object` test on the next segment,
        # and if there is no next segment then null is the answer either way.
        if val is None:
            return None
        # Dead upstream - `typeof fn` is "function", never "object", so `isObject` above has already
        # turned every callable away and JavaScript reaches this line only for things it is false
        # for. Not dead here: `callable()` and `isinstance(_, dict)` are independent, so a callable
        # dict or list subclass gets this far, and then this is the line that stops it. It stops it
        # with the same answer JavaScript gives for a callable container one line earlier - None -
        # so the port is faithful either way; ported rather than dropped because a resolver that
        # walks into a callable is not something to leave to a type check elsewhere.
        if is_function(last):
            return None
        last = val

    return last
