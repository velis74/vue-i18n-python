"""The context a message is rendered against.

Port of ``createMessageContext`` and its helpers in ``packages/core-base/src/runtime.ts``.

A message's AST is inert. Everything it needs to become a string — the named values, the positional
list, the linked-message lookup, the modifiers, and which plural form to pick — arrives through this
object. Upstream builds it as a bag of closures keyed by short helper names, because the AST is
compiled into JavaScript that calls those names; this port interprets the AST directly, so it is an
ordinary class with ordinary methods.

**Plural selection is vue-i18n's, not ours.** With no ``plural_rules`` entry for the locale, this
port uses :func:`plural_default` — the same locale-independent rule vue-i18n 11 uses — because the
port's job is to behave identically, not better. Correct CLDR forms come from the same place they
come from in a Vue application: a rule the caller supplies. :mod:`i18n_united.plurals` ships one
ready to pass in, but it is opt-in and nothing here reaches for it.
"""

# Deferred annotations are load-bearing here, not a style choice. This module keeps upstream's names,
# and two of them - the `list` option and the `list()` method - shadow the builtin inside their class
# body. Without this import, the very next annotation spelled `list[Any]` resolves to the dataclass
# field or to the method rather than to the type, and the class fails to define itself.
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from .display import to_display_string

#: What a message function returns when the key resolved to nothing.
DEFAULT_MESSAGE_DATA_TYPE = "text"

#: vue-i18n reaches here with -1 when a translation call carried no count at all.
NO_PLURAL_INDEX = -1


def default_modifier(value: str, _type: str = DEFAULT_MESSAGE_DATA_TYPE) -> str:
    return value


def _js_capitalize(text: str) -> str:
    """Upstream's ``str.charAt(0).toLocaleUpperCase() + str.substr(1)``.

    ``charAt(0)`` reads one UTF-16 code unit, so for a string starting with an astral character it
    returns a lone surrogate — which has no uppercase — and ``substr(1)`` then resumes in the middle
    of the same pair. The character therefore survives unchanged, and a Python implementation that
    naively uppercased the first *code point* would differ on exactly those strings: "𐐨test"
    capitalises to "𐐀test" here and stays "𐐨test" there.
    """
    if not text:
        return text
    first = text[0]
    if ord(first) >= 0x10000:
        return text
    return first.upper() + text[1:]


def _modifier_upper(value: Any, type_: str = DEFAULT_MESSAGE_DATA_TYPE) -> Any:
    return value.upper() if type_ == DEFAULT_MESSAGE_DATA_TYPE and isinstance(value, str) else value


def _modifier_lower(value: Any, type_: str = DEFAULT_MESSAGE_DATA_TYPE) -> Any:
    return value.lower() if type_ == DEFAULT_MESSAGE_DATA_TYPE and isinstance(value, str) else value


def _modifier_capitalize(value: Any, type_: str = DEFAULT_MESSAGE_DATA_TYPE) -> Any:
    return _js_capitalize(value) if type_ == DEFAULT_MESSAGE_DATA_TYPE and isinstance(value, str) else value


#: The modifiers every message can use without the application declaring anything, from
#: ``context.ts``. Upstream's ``vnode`` branches are absent: they unwrap a Vue VNode's children, and
#: there are no VNodes in Python.
DEFAULT_MODIFIERS: dict[str, Callable[..., Any]] = {
    "upper": _modifier_upper,
    "lower": _modifier_lower,
    "capitalize": _modifier_capitalize,
}


def default_normalize(values: list[Any]) -> str:
    return "" if not values else "".join(str(value) for value in values)


def plural_default(choice: int, choices_length: int) -> int:
    """vue-i18n's own plural rule, and this port's default, exactly as it is upstream's.

    It ignores the locale entirely: two forms mean singular/plural, and anything more clamps at index
    2, so a message can never reach a fourth or fifth form. That is wrong for most Slavic, Celtic and
    Semitic languages — and it is what vue-i18n does, which is what this port has to do. A Vue
    application fixes it by passing ``pluralRules`` to ``createI18n``; the Python equivalent is
    ``plural_rules`` here, and :mod:`i18n_united.plurals` has a CLDR-derived rule ready to pass.
    """
    choice = abs(choice)
    if choices_length == 2:
        return 0 if choice == 1 else 1
    return min(choice, 2)


@dataclass
class MessageContextOptions:
    parent: MessageContext | None = None
    locale: str | None = None
    list: list[Any] = field(default_factory=list)
    named: dict[str, Any] = field(default_factory=dict)
    modifiers: dict[str, Callable[..., Any]] = field(default_factory=dict)
    plural_index: int | None = None
    #: Per-locale overrides, ``(choice, choices_length) -> index``, exactly vue-i18n's shape.
    plural_rules: dict[str, Callable[..., int]] = field(default_factory=dict)
    #: Either a mapping of key to message function, or a callable ``(key, use_linked)``.
    messages: dict[str, Callable] | Callable[[str, bool], Callable] | None = None
    processor_type: str = DEFAULT_MESSAGE_DATA_TYPE
    processor_interpolate: Callable[[Any], Any] | None = None
    processor_normalize: Callable[[list[Any]], Any] | None = None


def _default_message(_ctx: MessageContext) -> str:
    return ""


def _resolve_plural_count(options: MessageContextOptions) -> int:
    """An explicit ``plural_index`` wins; otherwise ``count`` and then ``n`` from the named values."""
    if options.plural_index is not None:
        return options.plural_index
    for key in ("count", "n"):
        value = options.named.get(key)
        if isinstance(value, int) and not isinstance(value, bool):
            return value
        if isinstance(value, float):
            return int(value)
    return NO_PLURAL_INDEX


class MessageContext:
    def __init__(self, options: MessageContextOptions | None = None) -> None:
        self._options = options or MessageContextOptions()
        opts = self._options

        self.locale = opts.locale
        self.type = opts.processor_type
        self.interpolate = opts.processor_interpolate or to_display_string
        self.normalize = opts.processor_normalize or default_normalize

        self._plural_count = _resolve_plural_count(opts)
        self._list = opts.list
        self._named = dict(opts.named)
        # Upstream mirrors an explicit plural index into `count` and `n` so a message can write
        # `{count}` without the caller having passed it. `??=` there, so an existing value wins.
        if opts.plural_index is not None:
            self._named.setdefault("count", opts.plural_index)
            self._named.setdefault("n", opts.plural_index)

        # `Object.assign({}, list, named)` in upstream: a JavaScript array assigned into an object
        # contributes its indices as string keys.
        self.values: dict[str, Any] = {str(i): v for i, v in enumerate(self._list)}
        self.values.update(self._named)

    # -- value access -----------------------------------------------------------------------------

    def list(self, index: int) -> Any:
        """Positional value for ``{0}``. Out of range is ``None``, as a JavaScript array read is."""
        if 0 <= index < len(self._list):
            return self._list[index]
        return None

    def named(self, key: str) -> Any:
        return self._named.get(key)

    # -- plurals ----------------------------------------------------------------------------------

    def _plural_rule(self, choices_length: int) -> int:
        locale = self.locale
        custom = self._options.plural_rules.get(locale) if isinstance(locale, str) else None
        if callable(custom):
            # Upstream hands the built-in rule through as a third argument so a custom rule can
            # delegate. Callers that take two arguments must keep working, hence the try.
            try:
                return custom(self._plural_count, choices_length, plural_default)
            except TypeError:
                return custom(self._plural_count, choices_length)
        return plural_default(self._plural_count, choices_length)

    def plural(self, messages: list[Any]) -> Any:
        if not messages:
            return ""
        index = self._plural_rule(len(messages))
        # A rule is application-supplied code and may return anything; upstream would simply read
        # past the end and yield undefined, which renders as "". Clamping instead keeps a bad custom
        # rule from turning a translated message into an empty one.
        if not isinstance(index, int) or isinstance(index, bool):
            index = plural_default(self._plural_count, len(messages))
        return messages[max(0, min(index, len(messages) - 1))]

    # -- linked messages --------------------------------------------------------------------------

    def message(self, key: str, use_linked: bool = False) -> Callable[[MessageContext], Any]:
        messages = self._options.messages
        msg: Any = False
        if callable(messages):
            msg = messages(key, use_linked)
        elif isinstance(messages, dict):
            msg = messages.get(key)

        if not msg:
            if self._options.parent is not None:
                return self._options.parent.message(key)
            return _default_message
        return msg

    def _modifier(self, name: str) -> Callable[..., Any]:
        # An application-supplied modifier shadows a built-in of the same name, which is what
        # upstream's `options.modifiers` object does once merged over DEFAULT_MODIFIERS.
        if name in self._options.modifiers:
            return self._options.modifiers[name]
        return DEFAULT_MODIFIERS.get(name, default_modifier)

    def linked(self, key: str, modifier: str | None = None, type_: str | None = None) -> Any:
        """Render ``@:key`` — the message named by ``key``, optionally through a modifier."""
        message_type = type_ or DEFAULT_MESSAGE_DATA_TYPE
        resolved = self.message(key, True)(self)
        # An unresolved link renders as its own key rather than as nothing, so a missing translation
        # is visible in the output instead of silently deleting a sentence.
        if resolved == "" or resolved is None:
            resolved = key
        if message_type == "vnode" and isinstance(resolved, list) and modifier:
            resolved = resolved[0]
        return self._modifier(modifier)(resolved, message_type) if modifier else resolved


def create_message_context(options: MessageContextOptions | None = None) -> MessageContext:
    return MessageContext(options)
