"""Warning codes and their messages.

Port of ``packages/core-base/src/warnings.ts``, plus the ``format`` helper it uses from
``packages/shared/src/utils.ts``.

These are warnings, not errors: vue-i18n reports a missing key or a fallback by warning and carrying
on, because a translation that is merely absent should not take an application down. This port does
the same, through :mod:`warnings`, so a caller can silence or escalate them with the standard
machinery rather than with an option only this library understands.
"""

import re
import warnings

from enum import IntEnum
from typing import Any

#: ``{name}``, where the name is alphanumeric. Upstream's `RE_ARGS`.
_RE_ARGS = re.compile(r"\{([0-9a-zA-Z]+)\}")


class CoreWarnCodes(IntEnum):
    NOT_FOUND_KEY = 1
    FALLBACK_TO_TRANSLATE = 2
    CANNOT_FORMAT_NUMBER = 3
    FALLBACK_TO_NUMBER_FORMAT = 4
    CANNOT_FORMAT_DATE = 5
    FALLBACK_TO_DATE_FORMAT = 6
    EXPERIMENTAL_CUSTOM_MESSAGE_COMPILER = 7
    INVALID_NUMBER_ARGUMENT = 8
    INVALID_DATE_ARGUMENT = 9


#: Where a higher-order layer may start allocating its own codes without colliding with upstream.
CORE_WARN_CODES_EXTEND_POINT = 10

WARN_MESSAGES: dict[int, str] = {
    CoreWarnCodes.NOT_FOUND_KEY: "Not found '{key}' key in '{locale}' locale messages.",
    CoreWarnCodes.FALLBACK_TO_TRANSLATE: "Fall back to translate '{key}' key with '{target}' locale.",
    CoreWarnCodes.CANNOT_FORMAT_NUMBER: "Cannot format a number value due to not supported Intl.NumberFormat.",
    CoreWarnCodes.FALLBACK_TO_NUMBER_FORMAT: "Fall back to number format '{key}' key with '{target}' locale.",
    CoreWarnCodes.CANNOT_FORMAT_DATE: "Cannot format a date value due to not supported Intl.DateTimeFormat.",
    CoreWarnCodes.FALLBACK_TO_DATE_FORMAT: "Fall back to datetime format '{key}' key with '{target}' locale.",
    CoreWarnCodes.EXPERIMENTAL_CUSTOM_MESSAGE_COMPILER: (
        "This project is using Custom Message Compiler, which is an experimental feature. "
        "It may receive breaking changes or be removed in the future."
    ),
    CoreWarnCodes.INVALID_NUMBER_ARGUMENT: (
        "Invalid argument for number formatting: expected a number but received '{value}'."
    ),
    CoreWarnCodes.INVALID_DATE_ARGUMENT: (
        "Invalid argument for datetime formatting: expected a Date, number, or ISO string but received '{value}'."
    ),
}


class I18nWarning(UserWarning):
    """Category for every warning this library raises, so a caller can filter on it alone."""


def format_message(message: str, args: dict[str, Any] | None = None) -> str:
    """Substitute ``{name}`` placeholders. An unknown name becomes the empty string, as upstream."""
    values = args or {}
    return _RE_ARGS.sub(lambda m: str(values.get(m.group(1), "")), message)


def get_warn_message(code: int, args: dict[str, Any] | None = None) -> str:
    return format_message(WARN_MESSAGES.get(code, ""), args)


def default_warn(message: str) -> None:
    """The default ``on_warn``.

    ``stacklevel=3`` so the warning points at the caller's ``t()`` rather than into this package -
    two frames up is where a reader can act on it.
    """
    warnings.warn(message, I18nWarning, stacklevel=3)
