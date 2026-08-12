"""Tests for ``d()`` and ``n()``.

These deliberately do **not** pin formatted output. `Intl` and `babel` carry different CLDR data
versions, so an assertion on the exact string would be testing someone else's data and would break
on a babel upgrade that is none of this project's business.

What is tested is everything this port is actually responsible for: which locale a named format is
found in, that the fallback chain is walked, that overrides merge over the named format, what a
missing format does, what an invalid argument does, and that the caches key on the right things.
"""

from datetime import datetime as datetime_type, timezone

import pytest

from .context import create_core_context, NOT_RESOLVED
from .datetime import datetime as d, unsupported_datetime_options
from .formatter import get_formatter_cache_key, to_babel_locale
from .number import number as n, unsupported_number_options
from .warnings import I18nWarning

MOMENT = datetime_type(2026, 8, 12, 14, 5, 30, tzinfo=timezone.utc)


def _ctx(**kwargs):
    defaults = dict(
        locale="sl",
        fallback_locale="en",
        missing_warn=False,
        fallback_warn=False,
        number_formats={
            "sl": {"currency": {"style": "currency", "currency": "EUR"}},
            "en": {"currency": {"style": "currency", "currency": "GBP"}, "en-only": {"style": "percent"}},
        },
        datetime_formats={
            "sl": {"short": {"year": "numeric", "month": "short", "day": "numeric"}},
            "en": {"short": {"year": "numeric", "month": "short", "day": "numeric"}, "en-only": {"dateStyle": "long"}},
        },
    )
    defaults.update(kwargs)
    return create_core_context(**defaults)


# -- which locale answers ---------------------------------------------------------------------


def test_named_format_resolves_in_the_current_locale() -> None:
    assert "€" in n(_ctx(), 1234.5, "currency")


def test_named_format_falls_back_to_the_next_locale_in_the_chain() -> None:
    """`en-only` exists only in `en`, so a Slovene context has to walk the chain to find it."""
    result = n(_ctx(), 0.25, "en-only")
    assert result != "en-only", "the key came back, so the chain was not walked"
    assert "%" in result


def test_a_per_call_locale_overrides_the_context() -> None:
    assert "£" in n(_ctx(), 1234.5, "currency", "en")
    assert "€" in n(_ctx(), 1234.5, "currency")


def test_datetime_named_format_falls_back_too() -> None:
    assert d(_ctx(), MOMENT, "en-only") != "en-only"


# -- what a missing format does ---------------------------------------------------------------


def test_a_missing_format_returns_the_key() -> None:
    assert n(_ctx(), 1, "nope") == "nope"
    assert d(_ctx(), MOMENT, "nope") == "nope"


def test_a_missing_format_returns_not_resolved_when_unresolving() -> None:
    assert n(_ctx(unresolving=True), 1, "nope") == NOT_RESOLVED
    assert d(_ctx(unresolving=True), MOMENT, "nope") == NOT_RESOLVED


# -- overrides --------------------------------------------------------------------------------


def test_an_override_merges_over_the_named_format() -> None:
    """The named format says EUR; the override says GBP and must win.

    Asserted by difference rather than by symbol. A Slovene locale writes a foreign currency with
    its ISO code, so the obvious `"£" in result` fails here for a reason that has nothing to do with
    whether the override merged - which is exactly the CLDR-data trap this file avoids elsewhere.
    """
    default = n(_ctx(), 1234.5, "currency")
    overridden = n(_ctx(), 1234.5, "currency", {"currency": "GBP"})
    assert overridden != default
    assert "€" not in overridden


def test_options_without_a_named_format_are_used_directly() -> None:
    assert "%" in n(_ctx(), 0.25, {"style": "percent"})


def test_fraction_digits_are_honoured() -> None:
    """One of the few output assertions worth making: digit *counts* are not CLDR data."""
    assert n(_ctx(), 1.5, {"minimumFractionDigits": 3}).count("0") >= 2


def test_grouping_can_be_switched_off() -> None:
    grouped = n(_ctx(), 1234567, {})
    plain = n(_ctx(), 1234567, {"useGrouping": False})
    assert grouped != plain
    assert plain.strip("0123456789") == ""


# -- arguments --------------------------------------------------------------------------------


def test_a_non_number_warns_and_returns_empty_rather_than_raising() -> None:
    ctx = _ctx(missing_warn=True)
    with pytest.warns(I18nWarning, match="Invalid argument for number"):
        assert n(ctx, "not a number") == ""


def test_a_non_date_warns_and_returns_empty_rather_than_raising() -> None:
    with pytest.warns(I18nWarning, match="Invalid argument for datetime"):
        assert d(_ctx(missing_warn=True), object()) == ""


def test_a_date_may_be_a_timestamp_or_an_iso_string() -> None:
    from_datetime = d(_ctx(), MOMENT, "short")
    assert d(_ctx(), MOMENT.timestamp() * 1000, "short") == from_datetime
    assert d(_ctx(), "2026-08-12T14:05:30+00:00", "short") == from_datetime


def test_currency_style_without_a_currency_is_refused() -> None:
    """`Intl` throws a TypeError here; this raises rather than inventing a currency."""
    with pytest.raises(Exception, match="argument"):
        n(_ctx(), 1, {"style": "currency"})


def test_parts_are_refused_rather_than_approximated() -> None:
    with pytest.raises(NotImplementedError, match="formatToParts"):
        n(_ctx(), 1, {"part": True})


# -- the seams --------------------------------------------------------------------------------


def test_cache_key_separates_calls_that_differ_only_in_overrides() -> None:
    a = get_formatter_cache_key("sl", "currency", {"currency": "EUR"})
    b = get_formatter_cache_key("sl", "currency", {"currency": "GBP"})
    assert a != b
    # Two callers spelling the same overrides in a different order must share an entry.
    assert get_formatter_cache_key("sl", "k", {"a": 1, "b": 2}) == get_formatter_cache_key("sl", "k", {"b": 2, "a": 1})


def test_bcp47_tags_are_translated_for_babel() -> None:
    assert to_babel_locale("sl-SI") == "sl_SI"
    assert to_babel_locale("sl!") == "sl"


def test_unsupported_options_are_named_rather_than_silently_dropped() -> None:
    """A caller can ask what will be ignored. Without this the option simply vanishes."""
    assert unsupported_number_options({"style": "decimal", "signDisplay": "always"}) == {"signDisplay"}
    assert unsupported_datetime_options({"year": "numeric", "calendar": "buddhist"}) == {"calendar"}


def test_an_unmatched_skeleton_still_formats() -> None:
    """babel's fuzzy matcher can give up; upstream always produces something, so this must too."""
    assert d(_ctx(), MOMENT, {"era": "long", "second": "2-digit"})
