"""The translation call.

Port of ``packages/core-base/src/translate.ts``.

This is where everything else meets. A key comes in; the fallback chain decides which locale to look
in; the resolver finds a message format; the compiler turns it into a message function; the message
context supplies the values; and a string comes out. Every one of those steps lives in its own
module and was validated on its own — this file is the order they happen in, and the decisions made
when a step comes back empty.

Two things a reader should expect and not mistake for bugs, because both are upstream's:

* **A missing key renders as the key itself.** Not as an empty string, not as an exception. An
  untranslated string should be visible in the interface rather than a hole in a sentence.
* **A message that fails to compile renders as its own source.** The raw format is returned so the
  broken message is on screen where someone will see it.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from ..compiler.nodes import NodeTypes, ResourceNode
from ..compiler.parser import create_parser
from .context import (
    CoreContext,
    handle_missing,
    is_almost_same_locale,
    is_implicit_fallback,
    is_translate_fallback_warn,
    NOT_RESOLVED,
)
from .errors import CoreErrorCodes, create_core_error
from .fallbacker import get_locale
from .format import compile_message
from .message_context import MessageContext, MessageContextOptions
from .sanitize import escape_html, warn_output_not_sanitized
from .warnings import CoreWarnCodes, get_warn_message

#: What a linked key that resolved to nothing renders as.
NOOP_MESSAGE_FUNCTION: Callable[[MessageContext], str] = lambda _ctx: ""  # noqa: E731


@dataclass
class TranslateOptions:
    """The options half of a translate call, whatever shape the caller spelled them in."""

    list: list[Any] | None = None
    named: dict[str, Any] | None = None
    plural: int | None = None
    default: str | bool | None = None
    locale: str | None = None
    missing_warn: bool | None = None
    fallback_warn: bool | None = None
    escape_parameter: bool | None = None
    #: The key is already a compiled message or an AST; skip resolution entirely.
    resolved_message: bool = False
    extra: dict[str, Any] = field(default_factory=dict)


def is_message_function(value: Any) -> bool:
    return callable(value)


def is_message_ast(value: Any) -> bool:
    """An already-parsed message, as `compile()` hands back."""
    return isinstance(value, ResourceNode) and value.type == NodeTypes.RESOURCE


def parse_translate_args(*args: Any) -> tuple[Any, TranslateOptions]:
    """Sort a translate call's positional arguments into a key and options.

    vue-i18n lets the same call be spelled several ways, and the rules are positional rather than
    typed: the second argument is a plural count if it is a number, a default message if it is a
    string, named values if it is a mapping, and a positional list if it is a sequence. The third
    argument repeats the first two rules and otherwise merges into the options.
    """
    arg1 = args[0] if len(args) > 0 else None
    arg2 = args[1] if len(args) > 1 else None
    arg3 = args[2] if len(args) > 2 else None

    if not (
        isinstance(arg1, str)
        or (isinstance(arg1, (int, float)) and not isinstance(arg1, bool))
        or is_message_ast(arg1)
        or is_message_function(arg1)
    ):
        raise create_core_error(CoreErrorCodes.INVALID_ARGUMENT)

    key = str(arg1) if isinstance(arg1, (int, float)) and not isinstance(arg1, bool) else arg1

    options = TranslateOptions()
    _apply_positional(options, arg2, merge_mapping=False)
    _apply_positional(options, arg3, merge_mapping=True)
    return key, options


def _apply_positional(options: TranslateOptions, arg: Any, *, merge_mapping: bool) -> None:
    if isinstance(arg, bool):
        return
    if isinstance(arg, (int, float)):
        options.plural = int(arg)
    elif isinstance(arg, str):
        options.default = arg
    elif isinstance(arg, dict):
        if merge_mapping:
            _merge_options(options, arg)
        elif arg:
            # An empty mapping is ignored, so `t('key', {})` is `t('key')` rather than a call with
            # no named values that shadows the plural argument.
            options.named = arg
    elif isinstance(arg, (list, tuple)):
        options.list = list(arg)


_OPTION_FIELDS = {
    "list",
    "named",
    "plural",
    "default",
    "locale",
    "missing_warn",
    "fallback_warn",
    "escape_parameter",
    "resolved_message",
}


def _merge_options(options: TranslateOptions, mapping: dict[str, Any]) -> None:
    for name, value in mapping.items():
        if name in _OPTION_FIELDS:
            setattr(options, name, value)
        else:
            options.extra[name] = value


def _escape_params(options: TranslateOptions) -> None:
    """Escape every string parameter in place, as upstream's `escapeParams` does."""
    if isinstance(options.list, list):
        options.list = [escape_html(item) if isinstance(item, str) else item for item in options.list]
    elif isinstance(options.named, dict):
        options.named = {
            key: escape_html(value) if isinstance(value, str) else value
            for key, value in options.named.items()
        }


def default_message_compiler(source: str | ResourceNode, ctx: dict[str, Any]) -> Callable:
    """Parse a message and hand back the function that renders it.

    Upstream's core-base ships no compiler and expects one to be registered, because a Vue build can
    pre-compile every message and leave the compiler out of the bundle. There is no such trade-off
    here — there is no bundle — so this port compiles by default and a caller who has parsed ahead
    of time can still pass an AST straight through.
    """
    ast = source if is_message_ast(source) else create_parser(on_error=ctx.get("on_error")).parse(source)
    return compile_message(ast)


def resolve_message_format(
    context: CoreContext,
    key: str,
    locale: str,
    fallback_locale: Any,
    fallback_warn: Any,
    missing_warn: Any,
) -> tuple[Any, str | None, Any]:
    """Walk the fallback chain until a locale has the key.

    Returns the format found, the locale it was found in, and that locale's whole message object -
    the third is what linked messages are later resolved against.
    """
    locales = context.locale_fallbacker(context, fallback_locale, locale)

    message: Any = {}
    target_locale: str | None = None
    format_: Any = None

    for target_locale in locales:
        if (
            locale != target_locale
            and not is_almost_same_locale(locale, target_locale)
            and is_translate_fallback_warn(fallback_warn, key)
        ):
            context.on_warn(
                get_warn_message(
                    CoreWarnCodes.FALLBACK_TO_TRANSLATE, {"key": key, "target": target_locale}
                )
            )

        message = context.messages.get(target_locale) or {}

        format_ = context.message_resolver(message, key)
        if format_ is None:
            # The resolver walks a path; a flat resource may hold the dotted key verbatim.
            format_ = message.get(key) if isinstance(message, dict) else None

        if isinstance(format_, str) or is_message_ast(format_) or is_message_function(format_):
            break

        # Falling back from `sl-SI` to `sl` is not a missing translation, it is the same language
        # spelled less specifically, so it does not go through the missing handler.
        if not is_implicit_fallback(target_locale, locales):
            missing_result = handle_missing(context, key, target_locale, missing_warn, "translate")
            if missing_result != key:
                format_ = missing_result

    return format_, target_locale, message


def compile_message_format(
    context: CoreContext,
    key: str,
    target_locale: str,
    format_: Any,
    cache_base_key: str,
    on_error: Callable[[Exception], None],
) -> Callable:
    """Turn a format into a message function, reusing an earlier compilation where possible."""
    if is_message_function(format_):
        return format_

    compiler = context.message_compiler or default_message_compiler
    cache_key = f"{target_locale}__{cache_base_key}"
    cached = context.message_cache.get(cache_key)
    if cached is not None:
        return cached

    msg = compiler(format_, {"locale": target_locale, "key": key, "on_error": on_error})
    context.message_cache[cache_key] = msg
    return msg


def get_message_context_options(
    context: CoreContext, locale: str, message: Any, options: TranslateOptions
) -> MessageContextOptions:
    """Build what the message context needs, including how `@:linked` keys are looked up."""

    def resolve_message(key: str, use_linked: bool = False) -> Callable:
        value = context.message_resolver(message, key)

        # A linked key that is not in this locale's messages is looked up again through the whole
        # fallback chain, so `@:brand` resolves from the fallback locale like any other key.
        if value is None and (context.fallback_context or use_linked):
            source = context.fallback_context or context
            found, _target, found_message = resolve_message_format(
                source, key, locale, context.fallback_locale, context.fallback_warn, context.missing_warn
            )
            value = found if found is not None else context.message_resolver(found_message, key)

        if isinstance(value, str) or is_message_ast(value):
            failed = False

            def on_error(_error: Exception) -> None:
                nonlocal failed
                failed = True

            msg = compile_message_format(context, key, locale, value, key, on_error)
            return NOOP_MESSAGE_FUNCTION if failed else msg

        if is_message_function(value):
            return value
        return NOOP_MESSAGE_FUNCTION

    ctx_options = MessageContextOptions(
        locale=locale,
        modifiers=context.modifiers,
        plural_rules=context.plural_rules,
        messages=resolve_message,
    )
    if context.processor is not None:
        processor = context.processor
        ctx_options.processor_type = getattr(processor, "type", "text")
        ctx_options.processor_interpolate = getattr(processor, "interpolate", None)
        ctx_options.processor_normalize = getattr(processor, "normalize", None)
    if options.list:
        ctx_options.list = options.list
    if options.named:
        ctx_options.named = options.named
    if options.plural is not None:
        ctx_options.plural_index = options.plural
    return ctx_options


def translate(context: CoreContext, *args: Any) -> Any:
    """Translate a key against a context. The core-base entry point.

    Returns the rendered string, or :data:`~i18n_united.runtime.context.NOT_RESOLVED` when the key
    could not be resolved and the context was built with ``unresolving=True``.
    """
    key, options = parse_translate_args(*args)

    missing_warn = options.missing_warn if isinstance(options.missing_warn, bool) else context.missing_warn
    fallback_warn = (
        options.fallback_warn if isinstance(options.fallback_warn, bool) else context.fallback_warn
    )
    escape_parameter = (
        options.escape_parameter
        if isinstance(options.escape_parameter, bool)
        else context.escape_parameter
    )
    resolved_message = bool(options.resolved_message)

    # What to render when the key resolves to nothing: an explicit `default`, or the key itself when
    # `fallback_format` is on. `default=True` means "use the key".
    if isinstance(options.default, str):
        default_msg_or_key: Any = options.default
    elif options.default is True or context.fallback_format:
        default_msg_or_key = key
    else:
        default_msg_or_key = None
    enable_default_msg = context.fallback_format or isinstance(default_msg_or_key, str)

    locale = get_locale(context, options)

    if escape_parameter:
        _escape_params(options)

    if not resolved_message:
        format_, target_locale, message = resolve_message_format(
            context, key, locale, context.fallback_locale, fallback_warn, missing_warn
        )
    else:
        format_, target_locale, message = key, locale, context.messages.get(locale) or {}

    cache_base_key: Any = key
    is_usable = isinstance(format_, str) or is_message_ast(format_) or is_message_function(format_)
    if not resolved_message and not is_usable and enable_default_msg:
        format_ = default_msg_or_key
        cache_base_key = format_
        is_usable = isinstance(format_, str) or is_message_function(format_)

    if not resolved_message and (not is_usable or not isinstance(target_locale, str)):
        return NOT_RESOLVED if context.unresolving else key

    failed = False

    def on_error(_error: Exception) -> None:
        nonlocal failed
        failed = True

    msg = (
        format_
        if is_message_function(format_)
        else compile_message_format(context, key, target_locale, format_, cache_base_key, on_error)
    )
    if failed:
        # The message is broken; render its source so it is visible rather than swallowed.
        return format_

    ctx_options = get_message_context_options(context, target_locale, message, options)
    result = msg(MessageContext(ctx_options))

    if context.post_translation:
        result = context.post_translation(result, key)

    if escape_parameter and isinstance(result, str):
        warn_output_not_sanitized()

    return result
