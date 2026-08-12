"""JavaScript's ``String(value)`` and ``toDisplayString``, for interpolated values.

Port of the two helpers in ``packages/shared/src/utils.ts`` that decide what a non-string value looks
like once it lands in a message.

This file exists because Python's ``str()`` and JavaScript's ``String()`` disagree on exactly the
values a ``{placeholder}`` most often carries. ``str(1.0)`` is ``"1.0"`` where ``String(1.0)`` is
``"1"``; ``str(True)`` is ``"True"`` where ``String(true)`` is ``"true"``. A message reading
``"{count} items"`` would therefore render differently in Python than in JavaScript for a count that
arrived as a float — which is a difference in the rendered translation, not in some diagnostic.
"""

import json
import math

from decimal import Decimal
from typing import Any

#: Above this magnitude JavaScript switches a whole number to exponential notation.
_EXPONENTIAL_THRESHOLD = 1e21


def js_number_to_string(value: float | int) -> str:
    """Render a number the way JavaScript's ``String()`` does.

    JavaScript has one numeric type, so an integral value never shows a fraction: ``String(1.0)`` is
    ``"1"``. Python keeps ``int`` and ``float`` apart and ``str`` shows the difference, so integral
    floats are collapsed here. Exponent formatting also differs — Python writes ``1e-07`` where
    JavaScript writes ``1e-7`` — so the exponent is rebuilt without the zero padding.
    """
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)

    if math.isnan(value):
        return "NaN"
    if math.isinf(value):
        return "Infinity" if value > 0 else "-Infinity"

    # `-0.0` prints as "0" in JavaScript: String(-0) === "0". Only `Object.is` and division tell the
    # two zeros apart there, and neither is reachable from a message.
    if value == 0:
        return "0"

    # `repr` picks the shortest digits that round-trip, which is the same choice JavaScript's
    # Number::toString makes. Only the layout of those digits differs, so everything below reformats
    # `repr`'s output and never recomputes it. In particular an integral float is NOT rendered
    # through `int(value)`: above 2**53 that yields the exact binary value, where JavaScript prints
    # the shortest one — `String(-8.585543688319877e16)` is "-85855436883198770" and the exact value
    # is -85855436883198768.
    text = repr(value)
    decimal = Decimal(text)

    # The two languages put the fixed/exponential boundary in different places. Python's `repr` goes
    # exponential from 1e-5 down, JavaScript only from 1e-7 down, so `1e-6` is "1e-06" here and
    # "0.000001" there. Upward the boundary is 1e21 in both.
    if -7 < decimal.adjusted() < 21:
        fixed = format(decimal, "f")
        # JavaScript has no integral/fractional distinction to preserve: String(1.0) is "1".
        return fixed[:-2] if fixed.endswith(".0") else fixed

    mantissa, _, exponent = text.partition("e")
    sign = "-" if exponent.startswith("-") else "+"
    digits = exponent.lstrip("+-").lstrip("0") or "0"
    # JavaScript drops a `.0` from the mantissa in exponential form: 1e+21, not 1.0e+21.
    if mantissa.endswith(".0"):
        mantissa = mantissa[:-2]
    return f"{mantissa}e{sign}{digits}"


def js_string(value: Any) -> str:
    """JavaScript's ``String(value)`` for the value kinds a message can carry."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return js_number_to_string(value)
    if isinstance(value, str):
        return value
    if isinstance(value, (list, dict)):
        # `String([1,2])` is "1,2" and `String({})` is "[object Object]". Neither is reached from
        # `to_display_string`, which routes containers to JSON first; this branch is here so that
        # `js_string` is honest on its own.
        if isinstance(value, list):
            return ",".join("" if item is None else js_string(item) for item in value)
        return "[object Object]"
    return str(value)


def to_display_string(value: Any) -> str:
    """Render an interpolated value, as ``toDisplayString`` does.

    ``None`` becomes the empty string rather than ``"null"`` — upstream's ``val == null`` is true for
    both ``null`` and ``undefined``, and a missing placeholder value must not print the word "null"
    into a translation.
    """
    if value is None:
        return ""
    if isinstance(value, (list, dict)):
        # `ensure_ascii=False` because `JSON.stringify` does not escape non-ASCII, and a translation
        # is the last place that should turn "č" into "č".
        return json.dumps(value, indent=2, ensure_ascii=False)
    return js_string(value)
