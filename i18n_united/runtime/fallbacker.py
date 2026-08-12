"""The locale fallback chain.

Port of ``packages/core-base/src/fallbacker.ts``. Given a starting locale and the ``fallbackLocale``
option, this produces the ordered list of locales a lookup walks before giving up.

Two algorithms, both upstream's:

- :func:`fallback_with_simple` - the start locale followed by whatever the option names, deduplicated
  and otherwise untouched.
- :func:`fallback_with_locale_chain` - the default. It also walks a locale down its subtags
  (``sr-Latn-RS`` -> ``sr-Latn`` -> ``sr``), follows a map's entries into further blocks, stops at a
  locale suffixed ``!``, and finishes with the ``default`` block.

:func:`get_locale` and :func:`resolve_locale` come from the same upstream file. They resolve the
*locale option*, which may be a locale detector - a callable, a Vue-reactivity idiom that this port
keeps because a Python caller can want a locale computed per call just as much.

The port has to be careful about four JavaScript facts that Python does not share:

- **every object is truthy in JS, empty ones included.** ``{'sl-SI': []}`` sets ``follow`` to that
  empty array, which is *not* ``true``, which stops the subtag walk - so ``sl-SI`` does not fall back
  to ``sl``. A plain Python truth test would fall back to ``sl`` and diverge. :func:`_js_truthy`
  keeps the JS answer.
- **an array is an object, and both have a prototype.** ``blocks[locale]`` on an array fallback reads
  an array index when the locale looks like one, ``length`` when the locale is ``length``, and a
  method off ``Array.prototype`` or ``Object.prototype`` when the locale happens to be named after
  one. :func:`_block_lookup` reproduces all three.
- **``Object.keys`` is not insertion order.** Canonical array-index keys come first, ascending
  numerically, and only then the rest in insertion order. :func:`_js_object_keys` reproduces that.
- **a ``Set`` compares with SameValueZero.** ``1`` and ``1.0`` are one number there and Python keeps
  them apart; ``true`` and ``1`` are two values there and Python's ``True == 1`` merges them.
  :func:`_unique` corrects both directions.
"""

import inspect
import math

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from .errors import CoreErrorCodes, create_core_error

#: Mirrors ``DEFAULT_LOCALE`` in ``packages/core-base/src/context.ts``. Kept here rather than
#: imported so this module stands on its own; the definition moves to ``context.py`` and is imported
#: from there once that module lands.
DEFAULT_LOCALE = "en-US"

Locale = str

#: Upstream's ``LocaleDetector``: called with the arguments of the lookup and answering a locale.
#: Setting a ``resolved_once`` attribute on it makes :func:`resolve_locale` reuse its previous
#: answer, which is ``resolvedOnce`` on the JavaScript side.
LocaleDetector = Callable[..., Any]

#: Upstream's ``FallbackLocale``: ``Locale | Locale[] | { [locale: string]: Locale[] } | false``.
#: ``None`` stands in for ``undefined`` and behaves like ``False`` in every branch below. The
#: annotation is loose on purpose - JavaScript happily passes a map whose value is a bare string or a
#: boolean, and this port answers those the same way upstream does.
FallbackLocale = str | list[Any] | dict[str, Any] | bool | None


class ChainCacheContext(Protocol):
    """All :func:`fallback_with_locale_chain` wants of a context: somewhere to keep its cache.

    Upstream stashes a ``Map`` on the context as ``__localeChainCache`` by casting the context to an
    internal type. The eventual ``CoreContext`` port satisfies this by declaring the same attribute.
    """

    locale_chain_cache: dict[Locale, list[Locale]] | None


@dataclass
class FallbackContext:
    """A context that is nothing but the cache, for callers (and tests) that have no fuller one."""

    locale_chain_cache: dict[Locale, list[Locale]] | None = None


class LocaleOptions(Protocol):
    """Upstream's ``LocaleOptions``: the locale a single lookup may run in instead of the context's."""

    locale: Locale | LocaleDetector | None


class LocaleContext(Protocol):
    """As much of ``CoreContext`` as :func:`get_locale` reads."""

    locale: Locale | LocaleDetector


#: Upstream's module-level ``_resolveLocale``: the last locale a detector produced, remembered for
#: the whole process rather than per context, and handed back to any detector marked
#: ``resolved_once``. Reproduced as module state because that is exactly what it is upstream.
_resolved_locale: str | None = None


def get_locale(context: LocaleContext, options: LocaleOptions) -> str:
    """The locale one lookup runs in: the option's if it names one, the context's otherwise."""
    # `options.locale != null` upstream: an empty string is an override, `None` is not, and an
    # options object that has no `locale` at all reads as `undefined`, i.e. as no override either.
    locale = getattr(options, "locale", None)
    return resolve_locale(locale if locale is not None else context.locale)


def resolve_locale(locale: Locale | LocaleDetector) -> str:
    """A locale as given, or a locale detector called to produce one.

    The detector may not be asynchronous, in either of the two ways JavaScript can be asynchronous:
    upstream refuses an ``async function`` before calling it (``locale.constructor.name`` is
    ``'AsyncFunction'``, not ``'Function'``) and refuses a plain function that returned a promise
    after calling it. Python's equivalents are an ``async def`` and an awaitable return value, and
    both are refused with the same error code. A generator function joins them: JavaScript reports
    ``'GeneratorFunction'`` there and takes the same branch.
    """
    global _resolved_locale

    if isinstance(locale, str):
        return locale
    if not callable(locale):
        raise create_core_error(CoreErrorCodes.NOT_SUPPORT_LOCALE_TYPE)

    # `locale.resolvedOnce` upstream: a detector the caller has marked as worth asking only once, so
    # that a re-render reuses the answer instead of calling out again.
    if getattr(locale, "resolved_once", False) and _resolved_locale is not None:
        return _resolved_locale

    if inspect.iscoroutinefunction(locale) or inspect.isasyncgenfunction(locale) or inspect.isgeneratorfunction(locale):
        raise create_core_error(CoreErrorCodes.NOT_SUPPORT_LOCALE_ASYNC_FUNCTION)

    resolved = locale()
    if inspect.isawaitable(resolved):
        raise create_core_error(CoreErrorCodes.NOT_SUPPORT_LOCALE_PROMISE_VALUE)

    # Upstream assigns and returns in one expression, so every successful detector call - not only a
    # `resolvedOnce` one - overwrites what the next `resolvedOnce` detector will be handed.
    _resolved_locale = resolved
    return resolved


def _js_truthy(value: Any) -> bool:
    """JavaScript truthiness. Differs from Python's for ``[]`` and ``{}``, which JS calls true."""
    if isinstance(value, (list, dict)):
        return True
    return bool(value)


#: Everything an object literal inherits from ``Object.prototype`` in a current engine (read off
#: ``Object.getOwnPropertyNames(Object.prototype)`` in Node 26). Every one of them is a function or,
#: for ``__proto__``, the prototype object itself, so every one is truthy and none is an array.
_OBJECT_PROTOTYPE_KEYS = frozenset(
    {
        "__defineGetter__",
        "__defineSetter__",
        "__lookupGetter__",
        "__lookupSetter__",
        "__proto__",
        "constructor",
        "hasOwnProperty",
        "isPrototypeOf",
        "propertyIsEnumerable",
        "toLocaleString",
        "toString",
        "valueOf",
    }
)

#: What an array inherits on top of that, from ``Array.prototype``. ``length`` is left out: an array
#: has its own, and ``Array.prototype.length`` is 0 anyway, which is falsy.
_ARRAY_PROTOTYPE_KEYS = _OBJECT_PROTOTYPE_KEYS | {
    "at", "concat", "copyWithin", "entries", "every", "fill", "filter", "find", "findIndex",
    "findLast", "findLastIndex", "flat", "flatMap", "forEach", "includes", "indexOf", "join",
    "keys", "lastIndexOf", "map", "pop", "push", "reduce", "reduceRight", "reverse", "shift",
    "slice", "some", "sort", "splice", "toReversed", "toSorted", "toSpliced", "unshift", "values",
    "with",
}  # fmt: skip

#: The largest JavaScript *array index*. ``'4294967295'`` is one past it and is an ordinary string
#: property, which is why ``Object.keys`` leaves it among the insertion-ordered keys.
_MAX_ARRAY_INDEX = 2**32 - 2


class _PrototypeMember:
    """Stands in for the function a prototype-chain read hands back in JavaScript.

    Nothing here ever calls it or prints it. Upstream asks two questions of what ``blocks[locale]``
    returned - is it truthy, is it an array - and a native method answers yes and no. An instance of
    this class answers the same, and unlike an actual Python callable it cannot be mistaken for a
    locale detector by a later reader.
    """


_PROTOTYPE_MEMBER = _PrototypeMember()


def _is_array_index(key: Any) -> bool:
    """Is ``key`` the canonical decimal spelling of an array index, 0 through 2**32 - 2?

    Canonical rules out ``'00'``, ``'+0'``, ``'0.0'`` and ``'1e1'``: JavaScript reads all of those as
    ordinary string properties, so ``['a']['00']`` is ``undefined``.
    """
    if not isinstance(key, str) or not key.isascii() or not key.isdigit():
        return False
    if key != "0" and key.startswith("0"):
        return False
    return int(key) <= _MAX_ARRAY_INDEX


def _block_lookup(blocks: Any, key: str) -> Any:
    """``blocks[key]`` with JavaScript property semantics, prototype chain included.

    For a map this starts as an ordinary lookup. For an array it does not: JS arrays are objects, so
    ``['de', 'fr']['0']`` is ``'de'`` and ``['de', 'fr']['length']`` is ``2``. A locale named ``0``
    really does pick up a whole block that way.

    When there is no own property, JavaScript keeps looking up the prototype chain, and upstream's
    ``blocks[locale]`` has no ``hasOwnProperty`` guard to stop it. A locale named ``toString`` or
    ``map`` therefore finds a native method: truthy, not an array, so upstream's ``follow`` stops
    being a boolean and the rest of the block is dropped. That is emulated rather than skipped,
    because unlike the resolver's ``resolveWithKeyValue`` it leaks nothing - the value never reaches
    the chain, only its truthiness and its array-ness are ever asked about.
    """
    if isinstance(blocks, dict):
        if key in blocks:
            # An own key wins, and JSON really can carry `__proto__` as one: `JSON.parse` defines the
            # property where an object literal would have reassigned the prototype instead.
            return blocks[key]
        return _PROTOTYPE_MEMBER if key in _OBJECT_PROTOTYPE_KEYS else None
    if key == "length":
        return len(blocks)
    if _is_array_index(key):
        index = int(key)
        return blocks[index] if index < len(blocks) else None
    if key == "__proto__":
        # `Array.prototype` is itself an array - an empty one - so this is the one prototype read
        # that leaves `follow` an array and lets the caller go round its loop once more.
        return []
    return _PROTOTYPE_MEMBER if key in _ARRAY_PROTOTYPE_KEYS else None


def _js_object_keys(obj: dict[Any, Any]) -> list[Any]:
    """``Object.keys``: array-index keys first in ascending numeric order, then the rest as inserted.

    ``{b: 1, 2: 1, 1: 1, a: 1}`` gives ``['1', '2', 'b', 'a']``, not the order it was written in.
    """
    indexes: list[Any] = []
    rest: list[Any] = []
    for key in obj:
        (indexes if _is_array_index(key) else rest).append(key)
    indexes.sort(key=int)
    return indexes + rest


def _set_key(value: Any) -> tuple[Any, ...]:
    """What a JavaScript ``Set`` would consider this value's identity."""
    if isinstance(value, bool):
        # `true` is not `1` in a Set, but it is in Python: `True == 1` and their hashes agree.
        return "bool", value
    if isinstance(value, (int, float)):
        # ... and `1` *is* `1.0` there, JavaScript having a single numeric type. An integer too big
        # for a double is Infinity once it crosses into JavaScript, which is what float() refusing it
        # means here. NaN is one member of a Set even though it is not equal to itself.
        try:
            number = float(value)
        except OverflowError:
            number = math.inf if value > 0 else -math.inf
        return "number", "nan" if math.isnan(number) else number
    if isinstance(value, (list, dict)):
        # Objects are compared by identity, so two equal-but-distinct arrays are two members.
        return "ref", id(value)
    return type(value).__name__, value


def _unique(values: list[Any]) -> list[Any]:
    """``[...new Set(values)]``: first occurrence wins, order kept.

    Locales are strings, where this is nothing but deduplication. Everything interesting happens for
    the values JavaScript lets through the types - a number, a boolean, a nested array inside an
    array-shaped ``fallbackLocale`` - and :func:`_set_key` is what keeps those answers upstream's.
    """
    seen: list[tuple[Any, ...]] = []
    out: list[Any] = []
    for value in values:
        key = _set_key(value)
        if key in seen:
            continue
        seen.append(key)
        out.append(value)
    return out


def fallback_with_simple(_ctx: Any, fallback: FallbackLocale, start: Locale) -> list[Locale]:
    """The start locale plus whatever ``fallbackLocale`` names, deduplicated.

    No subtag walking, no ``!``, no following of map values - a map contributes its *keys*, which is
    rarely what an author means but is what upstream does.
    """
    if isinstance(fallback, list):
        rest: list[Any] = fallback
    elif isinstance(fallback, dict):
        rest = _js_object_keys(fallback)
    elif isinstance(fallback, str):
        rest = [fallback]
    else:
        rest = [start]
    return _unique([start, *rest])


def fallback_with_locale_chain(ctx: ChainCacheContext, fallback: FallbackLocale, start: Locale) -> list[Locale]:
    """The full chain algorithm, and vue-i18n's default.

    Note the cache: it is keyed by the *start locale alone*, so a second call with the same start and
    a different ``fallbackLocale`` gets the first call's answer. That is upstream's behaviour and it
    is reproduced here rather than fixed - see ``fallbacker_test.py``.
    """
    start_locale = start if isinstance(start, str) else DEFAULT_LOCALE

    cache = getattr(ctx, "locale_chain_cache", None)
    if cache is None:
        cache = {}
        ctx.locale_chain_cache = cache

    # `if (!chain)` upstream, where an empty *array* is truthy: a cached empty chain is returned as
    # is, only a missing one is computed.
    chain = cache.get(start_locale)
    if chain is None:
        chain = []

        # The first block is the start locale.
        block: Any = [start]

        # Every block that resolves to another block extends the chain. `follow` stops being an
        # array as soon as a locale has no entry of its own, which is what ends this loop - and what
        # makes a cyclic map (a -> b -> a) terminate: the second visit to `a` finds it in the chain
        # already and answers False.
        while isinstance(block, list):
            block = _append_block_to_chain(chain, block, fallback)

        # The last block is the default one. An array or a non-map fallback *is* its own default;
        # a map contributes its "default" entry, if it has a truthy one.
        if isinstance(fallback, list) or not isinstance(fallback, dict):
            defaults: Any = fallback
        else:
            defaults = fallback["default"] if _js_truthy(fallback.get("default")) else None

        block = [defaults] if isinstance(defaults, str) else defaults
        if isinstance(block, list):
            # `False` for the blocks argument: the default block is terminal, its entries are not
            # followed any further.
            _append_block_to_chain(chain, block, False)
        cache[start_locale] = chain

    return chain


def _append_block_to_chain(chain: list[Locale], block: list[Any], blocks: FallbackLocale) -> Any:
    """Append each locale of one block, stopping as soon as ``follow`` is no longer a boolean.

    A non-string entry is skipped without disturbing ``follow``, exactly as upstream's ``isString``
    guard inside the loop does.
    """
    follow: Any = True
    index = 0
    while index < len(block) and isinstance(follow, bool):
        locale = block[index]
        if isinstance(locale, str):
            follow = _append_locale_to_chain(chain, locale, blocks)
        index += 1
    return follow


def _append_locale_to_chain(chain: list[Locale], locale: Locale, blocks: FallbackLocale) -> Any:
    """Append a locale and then its shortening subtag prefixes: ``sr-Latn-RS``, ``sr-Latn``, ``sr``.

    The walk continues only while ``follow`` is exactly ``True``, so a locale that has an entry of
    its own (or that ends in ``!``) never reaches its own language subtag.
    """
    follow: Any = None
    tokens = locale.split("-")
    while True:
        target = "-".join(tokens)
        follow = _append_item_to_chain(chain, target, blocks)
        del tokens[-1:]  # `tokens.splice(-1, 1)`, which removes nothing from an empty array
        if not (tokens and follow is True):
            break
    return follow


def _append_item_to_chain(chain: list[Locale], target: Locale, blocks: FallbackLocale) -> Any:
    """Append one locale, and report whether the caller should keep going.

    Three upstream oddities, all preserved:

    - the already-in-chain check tests ``target`` *with* its ``!`` still attached while what gets
      appended is the stripped locale, so ``['en', 'en!']`` puts ``en`` in the chain twice;
    - ``!`` is stripped everywhere in the locale, not just at the end, so ``e!n`` becomes ``en`` -
      but only a trailing ``!`` stops the walk;
    - an entry found in ``blocks`` replaces ``follow`` with the entry itself, which is how a map
      leads into the next block.
    """
    follow: Any = False
    if target not in chain:
        follow = True
        if target:
            follow = target[-1] != "!"
            locale = target.replace("!", "")
            chain.append(locale)
            if isinstance(blocks, (list, dict)):
                value = _block_lookup(blocks, locale)
                if _js_truthy(value):
                    follow = value
    return follow
