"""Runtime error codes and the error they are raised as.

Port of ``packages/core-base/src/errors.ts``. The codes continue the compiler's numbering: upstream
starts them at ``COMPILE_ERROR_CODES_EXTEND_POINT`` so that one number identifies one defect across
both halves of the library, and a third implementation reading SPEC.md must report the same number
for the same defect. They are never renumbered.

Upstream's ``CoreError`` is structurally identical to a compile error and ``createCoreError`` builds
one with ``createCompileError``, so this port raises :class:`~i18n_united.compiler.errors.CompileError`
too rather than inventing a parallel class.
"""

from enum import IntEnum

from ..compiler.errors import COMPILE_ERROR_CODES_EXTEND_POINT, CompileError, create_compile_error


class CoreErrorCodes(IntEnum):
    INVALID_ARGUMENT = COMPILE_ERROR_CODES_EXTEND_POINT  # 17
    INVALID_DATE_ARGUMENT = 18
    INVALID_ISO_DATE_ARGUMENT = 19
    NOT_SUPPORT_NON_STRING_MESSAGE = 20
    NOT_SUPPORT_LOCALE_PROMISE_VALUE = 21
    NOT_SUPPORT_LOCALE_ASYNC_FUNCTION = 22
    NOT_SUPPORT_LOCALE_TYPE = 23


#: Where a higher-order runtime may start allocating its own codes without colliding with upstream.
CORE_ERROR_CODES_EXTEND_POINT = 24

ERROR_MESSAGES: dict[int, str] = {
    CoreErrorCodes.INVALID_ARGUMENT: "Invalid arguments",
    CoreErrorCodes.INVALID_DATE_ARGUMENT: (
        "The date provided is an invalid Date object.Make sure your Date represents a valid date."
    ),
    CoreErrorCodes.INVALID_ISO_DATE_ARGUMENT: "The argument provided is not a valid ISO date string",
    CoreErrorCodes.NOT_SUPPORT_NON_STRING_MESSAGE: "Not support non-string message",
    CoreErrorCodes.NOT_SUPPORT_LOCALE_PROMISE_VALUE: "cannot support promise value",
    CoreErrorCodes.NOT_SUPPORT_LOCALE_ASYNC_FUNCTION: "cannot support async function",
    CoreErrorCodes.NOT_SUPPORT_LOCALE_TYPE: "cannot support locale type",
}


def create_core_error(code: CoreErrorCodes) -> CompileError:
    """Upstream's ``createCoreError``, which carries no location: the defect is in the call, not in a
    message's source text.

    Upstream drops the messages in a production build (``__DEV__ ? { messages } : undefined``), which
    leaves the raised error with an empty string. Python has no such build split, so the message is
    always there; the code is the contract either way.
    """
    return create_compile_error(code, None, messages=ERROR_MESSAGES)
