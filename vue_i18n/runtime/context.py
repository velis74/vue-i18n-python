"""The core context: everything a translation call needs that is not the call itself.

Port of ``packages/core-base/src/context.ts``.

A context holds the loaded messages, the current locale and its fallback chain, the modifiers, the
plural rules and the handful of policies that decide what happens when a key is not found. It is
built once and passed to every :func:`~vue_i18n.runtime.translate.translate` call, which is
exactly upstream's shape.

Not ported: the devtools hooks (``__v_emitter``, ``initI18nDevTools``, ``setAdditionalMeta``) and
the ``__LITE__`` build branches. The first has no counterpart outside a browser, and the second is a
bundle-size dial for a build system this package does not have.
"""

from __future__ import annotations

import re

from collections.abc import Callable
from dataclasses import dataclass, field
from itertools import count
from typing import Any

from .. import VUE_I18N_VERSION
from .fallbacker import DEFAULT_LOCALE, fallback_with_locale_chain
from .message_context import DEFAULT_MODIFIERS
from .resolver import resolve_value
from .warnings import CoreWarnCodes, default_warn, get_warn_message

#: What ``translate`` returns for a key it could not resolve when ``unresolving`` is set. Upstream
#: spells this ``NOT_REOSLVED``; the typo is upstream's and is aliased below for anyone grepping
#: across the two codebases.
NOT_RESOLVED = -1
NOT_REOSLVED = NOT_RESOLVED

#: What a missing message resolves to before the missing handler gets a say.
MISSING_RESOLVE_VALUE = ""

_cid_counter = count(1)

#: Registered globally by upstream so a host framework can swap them once for every context. Kept
#: because the same override point is useful here, and because a context built with no explicit
#: resolver must pick up a registered one rather than the built-in default.
_registered_message_compiler: Callable[..., Any] | None = None
_registered_message_resolver: Callable[..., Any] | None = None
_registered_locale_fallbacker: Callable[..., Any] | None = None


def register_message_compiler(compiler: Callable[..., Any] | None) -> None:
    global _registered_message_compiler
    _registered_message_compiler = compiler


def register_message_resolver(resolver: Callable[..., Any] | None) -> None:
    global _registered_message_resolver
    _registered_message_resolver = resolver


def register_locale_fallbacker(fallbacker: Callable[..., Any] | None) -> None:
    global _registered_locale_fallbacker
    _registered_locale_fallbacker = fallbacker


@dataclass
class CoreContext:
    """The object every translation call is made against.

    Field names are vue-i18n's, in snake_case: ``fallbackLocale`` is ``fallback_locale``,
    ``missingWarn`` is ``missing_warn``, and so on. The concepts and their defaults are unchanged.
    """

    version: str
    cid: int
    #: A locale string, or a callable returning one - upstream's ``LocaleDetector``.
    locale: str | Callable[..., str]
    fallback_locale: str | list[str] | dict[str, list[str]] | bool
    messages: dict[str, Any]
    datetime_formats: dict[str, Any]
    number_formats: dict[str, Any]
    modifiers: dict[str, Callable[..., Any]]
    plural_rules: dict[str, Callable[..., int]]
    #: ``(context, locale, key, type) -> str | None``. When it returns a string, that string is the
    #: translation; anything else means "fall through to the key".
    missing: Callable[..., Any] | None
    missing_warn: bool | re.Pattern
    fallback_warn: bool | re.Pattern
    fallback_format: bool
    unresolving: bool
    post_translation: Callable[..., Any] | None
    processor: Any
    escape_parameter: bool
    message_compiler: Callable[..., Any] | None
    message_resolver: Callable[..., Any]
    locale_fallbacker: Callable[..., Any]
    fallback_context: CoreContext | None
    on_warn: Callable[[str], None]
    #: Caches keyed as upstream keys them. `locale_chain_cache` is read by `fallback_with_locale_chain`.
    locale_chain_cache: dict[str, list[str]] = field(default_factory=dict)
    #: Keyed by (locale, cache base key, source) - the source is what makes a changed message
    #: recompile instead of being served from here. Upstream keys the same three things.
    message_cache: dict[tuple[str, str, str], Any] = field(default_factory=dict)
    #: Upstream caches built `Intl` formatter objects here. This port caches the *merged option
    #: mapping* instead, because a babel call takes its options each time rather than being
    #: constructed once - the work worth saving is the merge, not an object.
    datetime_format_cache: dict[str, Any] = field(default_factory=dict)
    number_format_cache: dict[str, Any] = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def current_locale(self) -> str:
        """``locale`` resolved to a string, calling the detector if that is what it is."""
        return self.locale() if callable(self.locale) else self.locale


def _resources_for(locale: str) -> dict[str, Any]:
    return {locale: {}}


def create_core_context(
    *,
    locale: str | Callable[..., str] | None = None,
    fallback_locale: str | list[str] | dict[str, list[str]] | bool | None = None,
    messages: dict[str, Any] | None = None,
    datetime_formats: dict[str, Any] | None = None,
    number_formats: dict[str, Any] | None = None,
    modifiers: dict[str, Callable[..., Any]] | None = None,
    plural_rules: dict[str, Callable[..., int]] | None = None,
    missing: Callable[..., Any] | None = None,
    missing_warn: bool | re.Pattern = True,
    fallback_warn: bool | re.Pattern = True,
    fallback_format: bool = False,
    unresolving: bool = False,
    post_translation: Callable[..., Any] | None = None,
    processor: Any = None,
    escape_parameter: bool = False,
    message_compiler: Callable[..., Any] | None = None,
    message_resolver: Callable[..., Any] | None = None,
    locale_fallbacker: Callable[..., Any] | None = None,
    fallback_context: CoreContext | None = None,
    on_warn: Callable[[str], None] | None = None,
    version: str | None = None,
) -> CoreContext:
    """Build a context, normalising each option the way upstream does.

    Every option that is not of the type upstream expects falls back to the default rather than
    raising - a translation layer that refuses to start because one option was misspelled is worse
    than one that warns and translates.
    """
    resolved_locale: str | Callable[..., str]
    if isinstance(locale, str) or callable(locale):
        resolved_locale = locale
    else:
        resolved_locale = DEFAULT_LOCALE

    # A detector cannot be called this early, so the resources default to the static default locale.
    base_locale = DEFAULT_LOCALE if callable(resolved_locale) else resolved_locale

    if isinstance(fallback_locale, (list, dict, str)) or fallback_locale is False:
        resolved_fallback = fallback_locale
    else:
        resolved_fallback = base_locale

    # `DEFAULT_MODIFIERS` last, so upstream's precedence holds: the built-ins win over a caller's
    # modifier of the same name. It reads backwards, and it is what `assign(create(), options.modifiers,
    # getDefaultLinkedModifiers())` does.
    resolved_modifiers = {**(modifiers or {}), **DEFAULT_MODIFIERS}

    return CoreContext(
        # Upstream defaults this to `core-base`'s own `VERSION`, so the field answers "which
        # vue-i18n is this", not "which package build is this". Reporting this package's
        # `__version__` here would answer a question nobody asked it - and a caller comparing
        # against a vue-i18n version, as devtools does, would read 0.1.0 and conclude nothing.
        version=version if isinstance(version, str) else VUE_I18N_VERSION,
        cid=next(_cid_counter),
        locale=resolved_locale,
        fallback_locale=resolved_fallback,
        messages=messages if isinstance(messages, dict) else _resources_for(base_locale),
        datetime_formats=(
            datetime_formats if isinstance(datetime_formats, dict) else _resources_for(base_locale)
        ),
        number_formats=number_formats if isinstance(number_formats, dict) else _resources_for(base_locale),
        modifiers=resolved_modifiers,
        plural_rules=plural_rules if isinstance(plural_rules, dict) else {},
        missing=missing if callable(missing) else None,
        missing_warn=missing_warn if isinstance(missing_warn, (bool, re.Pattern)) else True,
        fallback_warn=fallback_warn if isinstance(fallback_warn, (bool, re.Pattern)) else True,
        fallback_format=bool(fallback_format),
        unresolving=bool(unresolving),
        post_translation=post_translation if callable(post_translation) else None,
        processor=processor,
        escape_parameter=bool(escape_parameter),
        message_compiler=(
            message_compiler if callable(message_compiler) else _registered_message_compiler
        ),
        # DEVIATION, and the same one twice: core-base falls back to `resolveWithKeyValue` and
        # `fallbackWithSimple`, then expects `@intlify/core` to register the real ones. There is no
        # separate core package here, so the defaults are the ones a vue-i18n application actually
        # runs with - nested path resolution, and the full fallback chain. Passing the flat resolver
        # or the simple fallbacker explicitly still works.
        message_resolver=(
            message_resolver
            if callable(message_resolver)
            else (_registered_message_resolver or resolve_value)
        ),
        locale_fallbacker=(
            locale_fallbacker
            if callable(locale_fallbacker)
            else (_registered_locale_fallbacker or fallback_with_locale_chain)
        ),
        fallback_context=fallback_context,
        on_warn=on_warn if callable(on_warn) else default_warn,
    )


def is_translate_fallback_warn(fallback: bool | re.Pattern, key: str) -> bool:
    """A regular expression narrows warnings to the keys that match it; a bool is all or nothing."""
    if isinstance(fallback, re.Pattern):
        return fallback.search(key) is not None
    return bool(fallback)


def is_translate_missing_warn(missing: bool | re.Pattern, key: str) -> bool:
    if isinstance(missing, re.Pattern):
        return missing.search(key) is not None
    return bool(missing)


def handle_missing(
    context: CoreContext,
    key: str,
    locale: str,
    missing_warn: bool | re.Pattern,
    type_: str,
) -> Any:
    """What a key that resolved to nothing becomes.

    With a missing handler installed, its return value wins if it is a string - anything else, and
    the key itself is used. Without one, the key is used and a warning is raised. Returning the key
    is what makes an untranslated string visible in the interface instead of blank.
    """
    if context.missing is not None:
        result = context.missing(context, locale, key, type_)
        return result if isinstance(result, str) else key

    if is_translate_missing_warn(missing_warn, key):
        context.on_warn(get_warn_message(CoreWarnCodes.NOT_FOUND_KEY, {"key": key, "locale": locale}))
    return key


def update_fallback_locale(
    context: CoreContext, locale: str, fallback: str | list[str] | dict[str, list[str]] | bool
) -> None:
    """Point the context at a new fallback and drop the chain cache.

    The cache has to go: `fallback_with_locale_chain` keys it by start locale alone, so without this
    a changed `fallback_locale` would keep answering with the chain computed from the old one.
    """
    context.locale_chain_cache = {}
    context.locale_fallbacker(context, fallback, locale)


def is_almost_same_locale(locale: str, compare: str) -> bool:
    """True when two different tags share a language subtag - ``sl-SI`` and ``sl``, not ``sl`` and ``sl``."""
    if locale == compare:
        return False
    return locale.split("-")[0] == compare.split("-")[0]


def is_implicit_fallback(target: str, locales: list[str]) -> bool:
    """True when `target` is followed in the chain by a tag of the same language.

    Used to decide whether falling back counts as "the same language, less specific" - which is not
    worth warning about - or as a genuine switch to another language, which is.
    """
    try:
        index = locales.index(target)
    except ValueError:
        return False
    return any(is_almost_same_locale(target, other) for other in locales[index + 1 :])
