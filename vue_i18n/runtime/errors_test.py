"""The runtime error codes are part of the contract, so they are pinned rather than trusted."""

import pytest

from ..compiler.errors import COMPILE_ERROR_CODES_EXTEND_POINT
from .errors import CORE_ERROR_CODES_EXTEND_POINT, CoreErrorCodes, create_core_error


def test_the_numbering_continues_where_the_compiler_stops() -> None:
    """One number identifies one defect across both halves of the library; renumbering breaks that."""
    assert CoreErrorCodes.INVALID_ARGUMENT == COMPILE_ERROR_CODES_EXTEND_POINT == 17
    assert [code.value for code in CoreErrorCodes] == list(range(17, 24))
    assert CORE_ERROR_CODES_EXTEND_POINT == 24


@pytest.mark.parametrize(
    ("code", "message"),
    [
        (CoreErrorCodes.INVALID_ARGUMENT, "Invalid arguments"),
        (CoreErrorCodes.NOT_SUPPORT_NON_STRING_MESSAGE, "Not support non-string message"),
        (CoreErrorCodes.NOT_SUPPORT_LOCALE_PROMISE_VALUE, "cannot support promise value"),
        (CoreErrorCodes.NOT_SUPPORT_LOCALE_ASYNC_FUNCTION, "cannot support async function"),
        (CoreErrorCodes.NOT_SUPPORT_LOCALE_TYPE, "cannot support locale type"),
    ],
)
def test_the_message_is_upstreams_word_for_word(code: int, message: str) -> None:
    error = create_core_error(code)
    assert error.code == code
    assert str(error) == message
    # No location: the defect is in the call, not anywhere in a message's source text.
    assert error.location is None


def test_the_two_run_on_sentences_in_the_date_message_are_upstreams_too() -> None:
    """Upstream concatenates two string literals and loses the space between them. Do not fix it."""
    assert str(create_core_error(CoreErrorCodes.INVALID_DATE_ARGUMENT)) == (
        "The date provided is an invalid Date object.Make sure your Date represents a valid date."
    )
