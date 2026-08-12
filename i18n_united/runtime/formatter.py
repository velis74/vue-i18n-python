"""Shared machinery for ``d()`` and ``n()``.

Port of ``packages/core-base/src/formatter.ts``: finding which locale holds a named format, keying
the formatter cache, clearing it, and sorting a call's positional arguments into options and
overrides.

Nothing here formats anything. The formatting itself is in :mod:`~i18n_united.runtime.number` and
:mod:`~i18n_united.runtime.datetime`, and is the one part of this library that cannot be a port —
``Intl.NumberFormat`` and ``Intl.DateTimeFormat`` have no Python equivalent, so those two modules
sit on ``babel`` instead.
"""

from __future__ import annotations

import json

from typing import Any

from .context import CoreContext, handle_missing, is_translate_fallback_warn
from .warnings import CoreWarnCodes, get_warn_message


def resolve_format_locale(
    context: CoreContext,
    key: str,
    locale: str,
    formats: dict[str, dict[str, Any]],
    missing_warn: Any,
    fallback_warn: Any,
    type_: str,
) -> str | None:
    """The first locale in the chain that defines a format named ``key``, or ``None``."""
    locales = context.locale_fallbacker(context, context.fallback_locale, locale)

    for target_locale in locales:
        if locale != target_locale and is_translate_fallback_warn(fallback_warn, key):
            code = (
                CoreWarnCodes.FALLBACK_TO_DATE_FORMAT
                if type_ == "datetime format"
                else CoreWarnCodes.FALLBACK_TO_NUMBER_FORMAT
            )
            context.on_warn(get_warn_message(code, {"key": key, "target": target_locale}))

        fmt = (formats.get(target_locale) or {}).get(key)
        if isinstance(fmt, dict) and isinstance(target_locale, str):
            return target_locale

        handle_missing(context, key, target_locale, missing_warn, type_)

    return None


def get_formatter_cache_key(locale: str, key: str, overrides: Any) -> str:
    """Cache identity for one formatter. Overrides are part of it, or two calls that differ only
    in their overrides would share a formatter built for the first one's."""
    ident = f"{locale}__{key}"
    if isinstance(overrides, dict) and overrides:
        # `sort_keys` because a Python dict preserves insertion order and two callers spelling the
        # same overrides in a different order must still hit the same entry.
        ident = f"{ident}__{json.dumps(overrides, sort_keys=True, default=str)}"
    return ident


def clear_format_cache(formatters: dict[str, Any], locale: str, format_: dict[str, Any]) -> None:
    """Drop every cached formatter belonging to ``locale`` and the format names in ``format_``."""
    for key in format_:
        prefix = f"{locale}__{key}"
        for ident in [i for i in formatters if i == prefix or i.startswith(f"{prefix}__")]:
            del formatters[ident]


def parse_format_args(
    args: tuple[Any, ...],
    options: dict[str, Any],
    initial_overrides: dict[str, Any],
    option_keys: frozenset[str],
) -> dict[str, Any]:
    """Sort a ``d()``/``n()`` call's arguments into options and Intl overrides.

    The rules are positional and untyped, as upstream's are: the second argument is a format name if
    it is a string, or a mapping that is split between real options and Intl overrides by name; the
    third is a locale if it is a string and overrides if it is a mapping; a fourth mapping is
    overrides too.
    """
    arg2 = args[1] if len(args) > 1 else None
    arg3 = args[2] if len(args) > 2 else None
    arg4 = args[3] if len(args) > 3 else None

    overrides = initial_overrides

    if isinstance(arg2, str):
        options["key"] = arg2
    elif isinstance(arg2, dict):
        for name, value in arg2.items():
            if name in option_keys:
                overrides[name] = value
            else:
                options[name] = value

    if isinstance(arg3, str):
        options["locale"] = arg3
    elif isinstance(arg3, dict):
        overrides = arg3

    if isinstance(arg4, dict):
        overrides = arg4

    return overrides


def to_babel_locale(locale: str) -> str:
    """``sl-SI`` to ``sl_SI``, and drop the ``!`` a fallback chain may carry.

    BCP-47 uses hyphens and babel's `Locale.parse` wants underscores. The `!` is vue-i18n's
    "stop here" marker on a fallback entry; upstream strips it before handing the tag to `Intl` too.
    """
    return locale.replace("!", "").replace("-", "_")
