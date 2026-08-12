"""``n()`` — number formatting.

Port of ``packages/core-base/src/number.ts``, except for the formatting itself.

Everything around the format is a faithful port: the argument shapes, the named format resources,
the fallback walk that finds which locale defines a format, the missing handling, the override
merging and the formatter cache. What could not be ported is ``Intl.NumberFormat``, which does not
exist in Python. :func:`_format` maps the Intl option object onto ``babel.numbers`` instead.

**The output is not expected to match ``Intl`` character for character**, and no corpus pins it.
The two carry different CLDR data versions, so a fixture comparing their strings would be testing
someone else's data rather than this port. What is tested is the logic: which locale is chosen,
which format name resolves, how overrides merge, what a missing format does.
"""

from __future__ import annotations

from typing import Any

from .context import CoreContext, MISSING_RESOLVE_VALUE, NOT_RESOLVED
from .errors import CoreErrorCodes, create_core_error
from .fallbacker import get_locale
from .formatter import (
    get_formatter_cache_key,
    parse_format_args,
    resolve_format_locale,
    to_babel_locale,
)
from .warnings import CoreWarnCodes, get_warn_message

#: Upstream's `NUMBER_FORMAT_OPTIONS_KEYS`: the names that belong to `Intl.NumberFormat` rather than
#: to vue-i18n, and are therefore split off into the overrides.
NUMBER_FORMAT_OPTIONS_KEYS = frozenset(
    {
        "localeMatcher",
        "style",
        "currency",
        "currencyDisplay",
        "currencySign",
        "useGrouping",
        "minimumIntegerDigits",
        "minimumFractionDigits",
        "maximumFractionDigits",
        "minimumSignificantDigits",
        "maximumSignificantDigits",
        "compactDisplay",
        "notation",
        "signDisplay",
        "unit",
        "unitDisplay",
        "roundingMode",
        "roundingPriority",
        "roundingIncrement",
        "trailingZeroDisplay",
    }
)

#: Accepted, passed through, and then ignored, because babel has nothing to map them onto. They are
#: named here rather than dropped silently so that `unsupported_number_options()` can report them.
UNSUPPORTED_OPTIONS = frozenset(
    {
        "localeMatcher",
        "currencySign",
        "signDisplay",
        "unit",
        "unitDisplay",
        "roundingMode",
        "roundingPriority",
        "roundingIncrement",
        "trailingZeroDisplay",
        "minimumSignificantDigits",
        "maximumSignificantDigits",
    }
)


def unsupported_number_options(options: dict[str, Any]) -> set[str]:
    """Which of ``options`` this port cannot honour. Useful in a test, and in a bug report."""
    return {name for name in options if name in UNSUPPORTED_OPTIONS}


def _decimal_pattern(options: dict[str, Any], *, suffix: str = "") -> str | None:
    """Build a CLDR number pattern from the digit-count options, or ``None`` to use babel's default.

    babel takes a pattern where `Intl` takes minimum/maximum digit counts, so the counts have to be
    spelled out: `0` is a required digit and `#` an optional one.
    """
    min_int = options.get("minimumIntegerDigits")
    min_frac = options.get("minimumFractionDigits")
    max_frac = options.get("maximumFractionDigits")
    grouping = options.get("useGrouping", True)

    if min_int is None and min_frac is None and max_frac is None and grouping is not False:
        return None

    integer = "0" * int(min_int) if min_int else "0"
    if grouping is not False:
        integer = "#,##" + integer if len(integer) < 4 else integer

    low = int(min_frac) if min_frac is not None else 0
    high = int(max_frac) if max_frac is not None else max(low, 3)
    fraction = "0" * low + "#" * max(0, high - low)

    return f"{integer}.{fraction}{suffix}" if fraction else f"{integer}{suffix}"


def _format(value: float, locale: str, options: dict[str, Any]) -> str:
    """Render ``value`` through babel, honouring what of the Intl options babel can express."""
    from babel import numbers as babel_numbers  # imported lazily: only `d()`/`n()` need babel

    babel_locale = to_babel_locale(locale)
    style = options.get("style", "decimal")
    grouping = options.get("useGrouping", True) is not False

    if options.get("notation") == "compact":
        format_type = "long" if options.get("compactDisplay") == "long" else "short"
        fraction_digits = int(options.get("maximumFractionDigits") or 0)
        if style == "currency":
            return babel_numbers.format_compact_currency(
                value,
                options.get("currency", "EUR"),
                format_type=format_type,
                locale=babel_locale,
                fraction_digits=fraction_digits,
            )
        return babel_numbers.format_compact_decimal(
            value, format_type=format_type, locale=babel_locale, fraction_digits=fraction_digits
        )

    if style == "currency":
        currency = options.get("currency")
        if not currency:
            # `Intl` throws a TypeError for `style: 'currency'` with no `currency`; so does this.
            raise create_core_error(CoreErrorCodes.INVALID_ARGUMENT)
        pattern = _decimal_pattern(options, suffix=" ¤")
        return babel_numbers.format_currency(
            value,
            currency,
            format=pattern,
            locale=babel_locale,
            group_separator=grouping,
            # `currency_digits` picks the currency's own default precision. An explicit
            # `minimumFractionDigits` or `maximumFractionDigits` is the caller overriding that.
            currency_digits=pattern is None,
        )

    if style == "percent":
        # `Intl` multiplies by 100 for percent and so does babel, so the value is passed as given.
        return babel_numbers.format_percent(
            value, format=_decimal_pattern(options, suffix="%"), locale=babel_locale, group_separator=grouping
        )

    return babel_numbers.format_decimal(
        value,
        format=_decimal_pattern(options),
        locale=babel_locale,
        group_separator=grouping,
        # Without this babel rounds to its pattern's precision and refuses values that do not fit;
        # `Intl` simply formats what it was given.
        decimal_quantization=False if _decimal_pattern(options) is None else True,
    )


def parse_number_args(*args: Any) -> tuple[str, float, dict[str, Any], dict[str, Any]]:
    value = args[0] if args else None
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise create_core_error(CoreErrorCodes.INVALID_ARGUMENT)

    options: dict[str, Any] = {}
    overrides = parse_format_args(args, options, {}, NUMBER_FORMAT_OPTIONS_KEYS)
    return options.get("key") or "", value, options, overrides


def number(context: CoreContext, *args: Any) -> Any:
    """Format a number. ``n()`` in vue-i18n.

    ``number(ctx, 12.5)`` formats with the locale's defaults; ``number(ctx, 12.5, 'currency')``
    looks up a named format in ``number_formats``; a mapping in the second or a later position
    supplies Intl options directly.
    """
    if not args or not isinstance(args[0], (int, float)) or isinstance(args[0], bool):
        context.on_warn(
            get_warn_message(CoreWarnCodes.INVALID_NUMBER_ARGUMENT, {"value": args[0] if args else None})
        )
        return MISSING_RESOLVE_VALUE

    key, value, options, overrides = parse_number_args(*args)
    missing_warn = options["missingWarn"] if isinstance(options.get("missingWarn"), bool) else context.missing_warn
    fallback_warn = (
        options["fallbackWarn"] if isinstance(options.get("fallbackWarn"), bool) else context.fallback_warn
    )
    if options.get("part"):
        # `Intl.NumberFormat.formatToParts` has no babel equivalent. Recorded in GAPS.md; refused
        # rather than approximated, because a caller asking for parts wants the structure.
        raise NotImplementedError("number(part=True) is not supported: babel has no formatToParts")

    locale = get_locale(context, _AttrOptions(options))

    if not isinstance(key, str) or key == "":
        return _format(value, locale, overrides)

    target_locale = resolve_format_locale(
        context, key, locale, context.number_formats, missing_warn, fallback_warn, "number format"
    )
    if not isinstance(target_locale, str):
        return NOT_RESOLVED if context.unresolving else key

    fmt = context.number_formats[target_locale][key]
    ident = get_formatter_cache_key(target_locale, key, overrides)
    merged = context.number_format_cache.get(ident)
    if merged is None:
        merged = {**fmt, **overrides}
        context.number_format_cache[ident] = merged
    return _format(value, target_locale, merged)


class _AttrOptions:
    """`get_locale` reads a `locale` attribute; these options are a mapping."""

    def __init__(self, options: dict[str, Any]) -> None:
        self.locale = options.get("locale")
