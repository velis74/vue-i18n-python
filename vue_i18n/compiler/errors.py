"""Compile error codes and the error type they are raised as.

Port of ``packages/message-compiler/src/errors.ts``. The codes are upstream's and are part of the
contract: a third implementation reading SPEC.md must report the same number for the same defect, so
they are never renumbered. ``COMPILE_ERROR_CODES_EXTEND_POINT`` is where a higher-order compiler
starts its own codes, and it moves only when upstream moves it.
"""

from enum import IntEnum
from typing import Any

from .location import SourceLocation


class CompileErrorCodes(IntEnum):
    # tokenizer
    EXPECTED_TOKEN = 1
    INVALID_TOKEN_IN_PLACEHOLDER = 2
    UNTERMINATED_SINGLE_QUOTE_IN_PLACEHOLDER = 3
    UNKNOWN_ESCAPE_SEQUENCE = 4
    INVALID_UNICODE_ESCAPE_SEQUENCE = 5
    UNBALANCED_CLOSING_BRACE = 6
    UNTERMINATED_CLOSING_BRACE = 7
    EMPTY_PLACEHOLDER = 8
    NOT_ALLOW_NEST_PLACEHOLDER = 9
    INVALID_LINKED_FORMAT = 10
    # parser
    MUST_HAVE_MESSAGES_IN_PLURAL = 11
    UNEXPECTED_EMPTY_LINKED_MODIFIER = 12
    UNEXPECTED_EMPTY_LINKED_KEY = 13
    UNEXPECTED_LEXICAL_ANALYSIS = 14
    # generator (not raised by this port - it generates no code - but kept so the numbering matches)
    UNHANDLED_CODEGEN_NODE_TYPE = 15
    # minifier
    UNHANDLED_MINIFIER_NODE_TYPE = 16


#: Where a higher-order compiler may start allocating its own codes without colliding with upstream.
COMPILE_ERROR_CODES_EXTEND_POINT = 17

ERROR_MESSAGES: dict[int, str] = {
    CompileErrorCodes.EXPECTED_TOKEN: "Expected token: '{0}'",
    CompileErrorCodes.INVALID_TOKEN_IN_PLACEHOLDER: "Invalid token in placeholder: '{0}'",
    CompileErrorCodes.UNTERMINATED_SINGLE_QUOTE_IN_PLACEHOLDER: "Unterminated single quote in placeholder",
    CompileErrorCodes.UNKNOWN_ESCAPE_SEQUENCE: "Unknown escape sequence: \\{0}",
    CompileErrorCodes.INVALID_UNICODE_ESCAPE_SEQUENCE: "Invalid unicode escape sequence: {0}",
    CompileErrorCodes.UNBALANCED_CLOSING_BRACE: "Unbalanced closing brace",
    CompileErrorCodes.UNTERMINATED_CLOSING_BRACE: "Unterminated closing brace",
    CompileErrorCodes.EMPTY_PLACEHOLDER: "Empty placeholder",
    CompileErrorCodes.NOT_ALLOW_NEST_PLACEHOLDER: "Not allowed nest placeholder",
    CompileErrorCodes.INVALID_LINKED_FORMAT: "Invalid linked format",
    CompileErrorCodes.MUST_HAVE_MESSAGES_IN_PLURAL: "Plural must have messages",
    CompileErrorCodes.UNEXPECTED_EMPTY_LINKED_MODIFIER: "Unexpected empty linked modifier",
    CompileErrorCodes.UNEXPECTED_EMPTY_LINKED_KEY: "Unexpected empty linked key",
    CompileErrorCodes.UNEXPECTED_LEXICAL_ANALYSIS: "Unexpected lexical analysis in token: '{0}'",
    CompileErrorCodes.UNHANDLED_CODEGEN_NODE_TYPE: "unhandled codegen node type: '{0}'",
    CompileErrorCodes.UNHANDLED_MINIFIER_NODE_TYPE: "unhandled mimifier node type: '{0}'",
}


class CompileError(SyntaxError):
    """Raised for a defect in a message's source.

    Subclasses ``SyntaxError`` for the same reason upstream does: the message is source text, and a
    malformed one is a syntax problem rather than a value problem.
    """

    def __init__(
        self,
        code: int,
        message: str,
        location: SourceLocation | None = None,
        domain: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.location = location
        self.domain = domain


def _format_message(template: str, *args: Any) -> str:
    """Upstream's ``format()`` from ``@intlify/shared``: ``{0}``, ``{1}`` … by position only."""
    out = template
    for index, arg in enumerate(args):
        out = out.replace("{" + str(index) + "}", str(arg))
    return out


def create_compile_error(
    code: int,
    loc: SourceLocation | None,
    domain: str | None = None,
    messages: dict[int, str] | None = None,
    args: list[Any] | None = None,
) -> CompileError:
    msg = _format_message((messages or ERROR_MESSAGES).get(code, ""), *(args or []))
    return CompileError(code=code, message=msg, location=loc, domain=domain)


def default_on_error(error: CompileError) -> None:
    raise error
