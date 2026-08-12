"""``d()`` — date and time formatting.

Port of ``packages/core-base/src/datetime.ts``, except for the formatting itself.

Same shape as :mod:`~i18n_united.runtime.number`, and the same boundary: everything around the
format is a faithful port, and ``Intl.DateTimeFormat`` is replaced by ``babel.dates``.

The interesting half of the mapping is the component options. ``Intl`` takes them as a bag
(``{"year": "numeric", "month": "short", "day": "numeric"}``); babel takes a CLDR *skeleton*
(``"yMMMd"``). :func:`_skeleton` turns one into the other, which is what lets a message resource
written for a Vue front end be read here unchanged.

**The output is not expected to match ``Intl`` character for character**, and no corpus pins it —
the two carry different CLDR data versions.
"""

from __future__ import annotations

from datetime import date, datetime as datetime_type, timezone
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

#: Upstream's `DATETIME_FORMAT_OPTIONS_KEYS`.
DATETIME_FORMAT_OPTIONS_KEYS = frozenset(
    {
        "localeMatcher",
        "weekday",
        "era",
        "year",
        "month",
        "day",
        "hour",
        "minute",
        "second",
        "timeZoneName",
        "formatMatcher",
        "hour12",
        "timeZone",
        "dateStyle",
        "timeStyle",
        "calendar",
        "dayPeriod",
        "numberingSystem",
        "hourCycle",
        "fractionalSecondDigits",
    }
)

#: Accepted and then ignored, because babel's skeleton vocabulary has nothing for them. Named here
#: so `unsupported_datetime_options()` can report them rather than have them vanish.
UNSUPPORTED_OPTIONS = frozenset(
    {"localeMatcher", "formatMatcher", "calendar", "numberingSystem", "hourCycle", "fractionalSecondDigits"}
)

#: Intl component option -> the CLDR skeleton field that says the same thing.
_SKELETON_FIELDS: dict[str, dict[str, str]] = {
    "era": {"narrow": "GGGGG", "short": "G", "long": "GGGG"},
    "year": {"numeric": "y", "2-digit": "yy"},
    "month": {"numeric": "M", "2-digit": "MM", "short": "MMM", "long": "MMMM", "narrow": "MMMMM"},
    "day": {"numeric": "d", "2-digit": "dd"},
    "weekday": {"narrow": "EEEEE", "short": "E", "long": "EEEE"},
    # `H` rather than CLDR's locale-preferred `j`: `j` is a *request* symbol that only means
    # something to a skeleton negotiator, and babel matches against the locale's `availableFormats`
    # keys, which are spelled `Hm`, `hms` and so on. `hour12` picks the 12-hour spelling.
    "hour": {"numeric": "H", "2-digit": "HH"},
    "hour12": {"numeric": "h", "2-digit": "hh"},
    "minute": {"numeric": "m", "2-digit": "mm"},
    "second": {"numeric": "s", "2-digit": "ss"},
    "timeZoneName": {"short": "z", "long": "zzzz"},
}

#: Skeleton field order. CLDR skeletons are conventionally written in this order, and
#: `format_skeleton` matches better against a conventional one.
_SKELETON_ORDER = ("era", "year", "month", "weekday", "day", "hour", "minute", "second", "timeZoneName")

_STYLES = frozenset({"full", "long", "medium", "short"})


def unsupported_datetime_options(options: dict[str, Any]) -> set[str]:
    """Which of ``options`` this port cannot honour. Useful in a test, and in a bug report."""
    return {name for name in options if name in UNSUPPORTED_OPTIONS}


def _skeleton(options: dict[str, Any]) -> str:
    """Build a CLDR skeleton from the Intl component options, in conventional field order."""
    twelve_hour = options.get("hour12") is True
    parts = []
    for name in _SKELETON_ORDER:
        value = options.get(name)
        if value is None:
            continue
        table = _SKELETON_FIELDS["hour12"] if name == "hour" and twelve_hour else _SKELETON_FIELDS[name]
        field = table.get(value)
        if field:
            parts.append(field)
    return "".join(parts)


def _coerce(value: Any) -> datetime_type:
    """A ``datetime``, a ``date``, a POSIX timestamp or an ISO string, as upstream accepts."""
    if isinstance(value, datetime_type):
        return value
    if isinstance(value, date):
        return datetime_type(value.year, value.month, value.day)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        # `Date` takes milliseconds; upstream's `d(ctx, 1234567890)` is milliseconds too.
        return datetime_type.fromtimestamp(value / 1000, tz=timezone.utc)
    if isinstance(value, str):
        try:
            return datetime_type.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise create_core_error(CoreErrorCodes.INVALID_ISO_DATE_ARGUMENT) from exc
    raise create_core_error(CoreErrorCodes.INVALID_DATE_ARGUMENT)


def _format(value: Any, locale: str, options: dict[str, Any]) -> str:
    from babel import dates as babel_dates  # imported lazily: only `d()`/`n()` need babel

    moment = _coerce(value)
    babel_locale = to_babel_locale(locale)

    tzinfo = None
    tz_name = options.get("timeZone")
    if tz_name:
        try:
            from zoneinfo import ZoneInfo

            tzinfo = ZoneInfo(tz_name)
        except Exception:  # noqa: BLE001 - an unknown zone falls back to the value's own
            tzinfo = None

    date_style = options.get("dateStyle")
    time_style = options.get("timeStyle")
    if date_style in _STYLES or time_style in _STYLES:
        if date_style and time_style:
            # babel's `format_datetime` takes one style for both halves, so a call asking for two
            # different ones is composed by hand through the locale's own joining pattern - which is
            # what `{1}, {0}` is, date in `{1}` and time in `{0}`.
            joined = babel_dates.get_datetime_format(date_style, locale=babel_locale)
            return joined.format(
                babel_dates.format_time(moment, format=time_style, tzinfo=tzinfo, locale=babel_locale),
                babel_dates.format_date(moment, format=date_style, locale=babel_locale),
            )
        if date_style:
            return babel_dates.format_date(moment, format=date_style, locale=babel_locale)
        return babel_dates.format_time(moment, format=time_style, tzinfo=tzinfo, locale=babel_locale)

    skeleton = _skeleton(options)
    if skeleton:
        try:
            return babel_dates.format_skeleton(skeleton, moment, tzinfo=tzinfo, locale=babel_locale)
        except KeyError:
            # babel's fuzzy matcher gave up: the locale has no `availableFormats` entry close enough
            # to this combination of fields. `Intl` always produces *something*, so falling back to
            # a medium date-time is closer to upstream than raising at a caller who asked for an
            # unusual but legal option set.
            return babel_dates.format_datetime(moment, format="medium", tzinfo=tzinfo, locale=babel_locale)

    # No options at all: `Intl.DateTimeFormat()` defaults to a numeric date.
    return babel_dates.format_date(moment, format="medium", locale=babel_locale)


def parse_datetime_args(*args: Any) -> tuple[str, Any, dict[str, Any], dict[str, Any]]:
    value = args[0] if args else None
    if not isinstance(value, (str, date, datetime_type)) and not (
        isinstance(value, (int, float)) and not isinstance(value, bool)
    ):
        raise create_core_error(CoreErrorCodes.INVALID_ARGUMENT)

    options: dict[str, Any] = {}
    overrides = parse_format_args(args, options, {}, DATETIME_FORMAT_OPTIONS_KEYS)
    return options.get("key") or "", value, options, overrides


def datetime(context: CoreContext, *args: Any) -> Any:
    """Format a date or time. ``d()`` in vue-i18n."""
    first = args[0] if args else None
    if not isinstance(first, (str, date, datetime_type)) and not (
        isinstance(first, (int, float)) and not isinstance(first, bool)
    ):
        context.on_warn(get_warn_message(CoreWarnCodes.INVALID_DATE_ARGUMENT, {"value": first}))
        return MISSING_RESOLVE_VALUE

    key, value, options, overrides = parse_datetime_args(*args)
    missing_warn = options["missingWarn"] if isinstance(options.get("missingWarn"), bool) else context.missing_warn
    fallback_warn = (
        options["fallbackWarn"] if isinstance(options.get("fallbackWarn"), bool) else context.fallback_warn
    )
    if options.get("part"):
        raise NotImplementedError("datetime(part=True) is not supported: babel has no formatToParts")

    locale = get_locale(context, _AttrOptions(options))

    if not isinstance(key, str) or key == "":
        return _format(value, locale, overrides)

    target_locale = resolve_format_locale(
        context, key, locale, context.datetime_formats, missing_warn, fallback_warn, "datetime format"
    )
    if not isinstance(target_locale, str):
        return NOT_RESOLVED if context.unresolving else key

    fmt = context.datetime_formats[target_locale][key]
    ident = get_formatter_cache_key(target_locale, key, overrides)
    merged = context.datetime_format_cache.get(ident)
    if merged is None:
        merged = {**fmt, **overrides}
        context.datetime_format_cache[ident] = merged
    return _format(value, target_locale, merged)


class _AttrOptions:
    """`get_locale` reads a `locale` attribute; these options are a mapping."""

    def __init__(self, options: dict[str, Any]) -> None:
        self.locale = options.get("locale")
