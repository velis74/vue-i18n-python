"""Message tokenizer.

Port of ``packages/message-compiler/src/tokenizer.ts``.

This is a deliberately literal port. The upstream file carries three ``TODO: We need refactoring of
token parsing ...`` markers and the control flow in ``_read_token_in_placeholder`` and
``_read_token_in_linked`` is genuinely tangled — but it is the definition of the format, quirks and
all, and a tidier tokenizer that disagreed about one edge case would be worse than an untidy one
that agrees about all of them. Restructure only with a conformance fixture proving the behaviour is
unchanged.

Two Python-specific notes:

* ``None`` stands in for JavaScript's ``undefined``. It is falsy and unequal to every character, so
  ported truthiness tests (``if not ch``) and equality tests (``ch == "{"``) both carry over.
* ``_take_char`` collapses upstream's ``undefined`` (end of input) and ``null`` (predicate said no)
  into ``None``. Every caller tests only for truthiness, so the distinction was never read.
"""

from collections.abc import Callable
from dataclasses import dataclass
from enum import IntEnum
from typing import Any

from .errors import CompileErrorCodes, create_compile_error
from .location import create_location, create_position, Position, SourceLocation
from .scanner import CHAR_LF as NEW_LINE, CHAR_SP as SPACE, create_scanner, Scanner


class TokenTypes(IntEnum):
    TEXT = 0
    PIPE = 1
    BRACE_LEFT = 2
    BRACE_RIGHT = 3
    NAMED = 4
    LIST = 5
    LITERAL = 6
    LINKED_ALIAS = 7
    LINKED_DOT = 8
    LINKED_DELIMITER = 9
    LINKED_KEY = 10
    LINKED_MODIFIER = 11
    INVALID_PLACE = 12
    EOF = 13


class TokenChars:
    PIPE = "|"
    BRACE_LEFT = "{"
    BRACE_RIGHT = "}"
    PAREN_LEFT = "("
    PAREN_RIGHT = ")"
    LINKED_ALIAS = "@"
    LINKED_DOT = "."
    LINKED_DELIMITER = ":"


DOT = "."
LITERAL_DELIMITER = "'"
#: U+3000 IDEOGRAPHIC SPACE, which upstream accepts as a placeholder terminator alongside the ASCII
#: space. Without it a CJK message with a full-width space after a name would report an invalid
#: token rather than a name.
IDEOGRAPHIC_SPACE = "　"
ERROR_DOMAIN = "tokenizer"


@dataclass
class Token:
    type: TokenTypes
    value: str | None = None
    loc: SourceLocation | None = None


@dataclass
class TokenizeContext:
    current_type: TokenTypes
    offset: int
    start_loc: Position
    end_loc: Position
    last_type: TokenTypes
    last_offset: int
    last_start_loc: Position
    last_end_loc: Position
    brace_nest: int = 0
    in_linked: bool = False
    text: str = ""


@dataclass
class TokenizeOptions:
    #: When false, tokens carry no ``loc``. Upstream uses this to shrink compiled output; here it
    #: only saves allocations, but the flag stays so this port takes the same options as upstream.
    location: bool = True
    on_error: Callable[[Exception], None] | None = None


def _is_identifier_start(ch: str | None) -> bool:
    if ch is None:
        return False
    cc = ord(ch)
    return (97 <= cc <= 122) or (65 <= cc <= 90) or cc == 95  # a-z, A-Z, _


def _is_number_start(ch: str | None) -> bool:
    if ch is None:
        return False
    return 48 <= ord(ch) <= 57  # 0-9


def _is_identifier(ch: str) -> bool:
    cc = ord(ch)
    return (97 <= cc <= 122) or (65 <= cc <= 90) or (48 <= cc <= 57) or cc == 95 or cc == 36  # … _ $


def _is_named_identifier(ch: str) -> bool:
    cc = ord(ch)
    # Same as an identifier plus '-', because message keys are routinely kebab-case.
    return (97 <= cc <= 122) or (65 <= cc <= 90) or (48 <= cc <= 57) or cc in (95, 36, 45)


def _is_digit(ch: str) -> bool:
    return 48 <= ord(ch) <= 57


def _is_hex_digit(ch: str) -> bool:
    cc = ord(ch)
    return (48 <= cc <= 57) or (65 <= cc <= 70) or (97 <= cc <= 102)


def _is_literal(ch: str) -> bool:
    return ch != LITERAL_DELIMITER and ch != NEW_LINE


def _is_invalid_identifier(ch: str) -> bool:
    return ch != TokenChars.BRACE_LEFT and ch != TokenChars.BRACE_RIGHT and ch != SPACE and ch != NEW_LINE


class Tokenizer:
    """Turns message source into a token stream. One instance per message; not reusable."""

    def __init__(self, source: str, options: TokenizeOptions | None = None) -> None:
        self._options = options or TokenizeOptions()
        self._location = self._options.location is not False
        self._scnr: Scanner = create_scanner(source)

        init_loc = self.current_position()
        init_offset = self.current_offset()
        self._context = TokenizeContext(
            current_type=TokenTypes.EOF,
            offset=init_offset,
            start_loc=init_loc,
            end_loc=init_loc,
            last_type=TokenTypes.EOF,
            last_offset=init_offset,
            last_start_loc=init_loc,
            last_end_loc=init_loc,
        )

    # -- position ---------------------------------------------------------------------------------

    def current_offset(self) -> int:
        return self._scnr.u16_index()

    def current_position(self) -> Position:
        return create_position(self._scnr.line(), self._scnr.column(), self._scnr.u16_index())

    def context(self) -> TokenizeContext:
        return self._context

    # -- errors and token construction ------------------------------------------------------------

    def _emit_error(self, code: int, pos: Position, offset: int, *args: Any) -> None:
        """Report a defect. ``pos`` is advanced in place by ``offset``, as upstream does."""
        ctx = self._context
        pos.column += offset
        pos.offset += offset

        on_error = self._options.on_error
        if on_error:
            loc = create_location(ctx.start_loc, pos) if self._location else None
            on_error(create_compile_error(code, loc, domain=ERROR_DOMAIN, args=list(args)))

    def _get_token(self, ctx: TokenizeContext, token_type: TokenTypes, value: str | None = None) -> Token:
        ctx.end_loc = self.current_position()
        ctx.current_type = token_type

        token = Token(type=token_type)
        if self._location:
            token.loc = create_location(ctx.start_loc, ctx.end_loc)
        if value is not None:
            token.value = value
        return token

    def _get_end_token(self, ctx: TokenizeContext) -> Token:
        return self._get_token(ctx, TokenTypes.EOF)

    # -- primitive readers ------------------------------------------------------------------------

    def _eat(self, scnr: Scanner, ch: str) -> str:
        if scnr.current_char() == ch:
            scnr.next()
            return ch
        self._emit_error(CompileErrorCodes.EXPECTED_TOKEN, self.current_position(), 0, ch)
        return ""

    def _peek_spaces(self, scnr: Scanner) -> str:
        buf = ""
        while scnr.current_peek() == SPACE or scnr.current_peek() == NEW_LINE:
            buf += scnr.current_peek() or ""
            scnr.peek()
        return buf

    def _skip_spaces(self, scnr: Scanner) -> str:
        buf = self._peek_spaces(scnr)
        scnr.skip_to_peek()
        return buf

    def _take_char(self, scnr: Scanner, fn: Callable[[str], bool]) -> str | None:
        ch = scnr.current_char()
        if ch is None:
            return None
        if fn(ch):
            scnr.next()
            return ch
        return None

    def _take_identifier_char(self, scnr: Scanner) -> str | None:
        return self._take_char(scnr, _is_identifier)

    def _take_named_identifier_char(self, scnr: Scanner) -> str | None:
        return self._take_char(scnr, _is_named_identifier)

    def _take_digit(self, scnr: Scanner) -> str | None:
        return self._take_char(scnr, _is_digit)

    def _take_hex_digit(self, scnr: Scanner) -> str | None:
        return self._take_char(scnr, _is_hex_digit)

    def _get_digits(self, scnr: Scanner) -> str:
        num = ""
        while ch := self._take_digit(scnr):
            num += ch
        return num

    # -- lookahead predicates ---------------------------------------------------------------------

    def _is_named_identifier_start(self, scnr: Scanner, ctx: TokenizeContext) -> bool:
        if ctx.current_type != TokenTypes.BRACE_LEFT:
            return False
        self._peek_spaces(scnr)
        ret = _is_identifier_start(scnr.current_peek())
        scnr.reset_peek()
        return ret

    def _is_list_identifier_start(self, scnr: Scanner, ctx: TokenizeContext) -> bool:
        if ctx.current_type != TokenTypes.BRACE_LEFT:
            return False
        self._peek_spaces(scnr)
        ch = scnr.peek() if scnr.current_peek() == "-" else scnr.current_peek()
        ret = _is_number_start(ch)
        scnr.reset_peek()
        return ret

    def _is_literal_start(self, scnr: Scanner, ctx: TokenizeContext) -> bool:
        if ctx.current_type != TokenTypes.BRACE_LEFT:
            return False
        self._peek_spaces(scnr)
        ret = scnr.current_peek() == LITERAL_DELIMITER
        scnr.reset_peek()
        return ret

    def _is_linked_dot_start(self, scnr: Scanner, ctx: TokenizeContext) -> bool:
        if ctx.current_type != TokenTypes.LINKED_ALIAS:
            return False
        self._peek_spaces(scnr)
        ret = scnr.current_peek() == TokenChars.LINKED_DOT
        scnr.reset_peek()
        return ret

    def _is_linked_modifier_start(self, scnr: Scanner, ctx: TokenizeContext) -> bool:
        if ctx.current_type != TokenTypes.LINKED_DOT:
            return False
        self._peek_spaces(scnr)
        ret = _is_identifier_start(scnr.current_peek())
        scnr.reset_peek()
        return ret

    def _is_linked_delimiter_start(self, scnr: Scanner, ctx: TokenizeContext) -> bool:
        if ctx.current_type not in (TokenTypes.LINKED_ALIAS, TokenTypes.LINKED_MODIFIER):
            return False
        self._peek_spaces(scnr)
        ret = scnr.current_peek() == TokenChars.LINKED_DELIMITER
        scnr.reset_peek()
        return ret

    def _is_linked_refer_start(self, scnr: Scanner, ctx: TokenizeContext) -> bool:
        if ctx.current_type != TokenTypes.LINKED_DELIMITER:
            return False

        def fn() -> bool:
            ch = scnr.current_peek()
            if ch == TokenChars.BRACE_LEFT:
                return _is_identifier_start(scnr.peek())
            if ch in (
                TokenChars.LINKED_ALIAS,
                TokenChars.PIPE,
                TokenChars.LINKED_DELIMITER,
                TokenChars.LINKED_DOT,
                SPACE,
            ) or not ch:
                return False
            if ch == NEW_LINE:
                scnr.peek()
                return fn()
            return self._is_text_start(scnr, False)

        ret = fn()
        scnr.reset_peek()
        return ret

    def _is_plural_start(self, scnr: Scanner) -> bool:
        self._peek_spaces(scnr)
        ret = scnr.current_peek() == TokenChars.PIPE
        scnr.reset_peek()
        return ret

    def _is_text_start(self, scnr: Scanner, reset: bool = True) -> bool:
        def fn(has_space: bool = False, prev: str = "") -> bool:
            ch = scnr.current_peek()
            if ch == TokenChars.BRACE_LEFT:
                return has_space
            if ch == TokenChars.LINKED_ALIAS or not ch:
                return has_space
            if ch == TokenChars.PIPE:
                # A pipe preceded by whitespace starts a plural branch; one glued to a word is text.
                return not (prev == SPACE or prev == NEW_LINE)
            if ch == SPACE:
                scnr.peek()
                return fn(True, SPACE)
            if ch == NEW_LINE:
                scnr.peek()
                return fn(True, NEW_LINE)
            return True

        ret = fn()
        if reset:
            scnr.reset_peek()
        return ret

    # -- value readers ----------------------------------------------------------------------------

    def _read_text(self, scnr: Scanner) -> str:
        buf = ""
        while True:
            ch = scnr.current_char()
            if ch == "\\":
                next_ch = scnr.peek()
                if next_ch in (
                    TokenChars.BRACE_LEFT,
                    TokenChars.BRACE_RIGHT,
                    TokenChars.LINKED_ALIAS,
                    TokenChars.PIPE,
                    "\\",
                ):
                    # The backslash is kept; the parser's unescape step removes it later.
                    buf += ch + (next_ch or "")
                    scnr.next()
                    scnr.next()
                else:
                    scnr.reset_peek()
                    buf += ch
                    scnr.next()
            elif (
                ch == TokenChars.BRACE_LEFT
                or ch == TokenChars.BRACE_RIGHT
                or ch == TokenChars.LINKED_ALIAS
                or ch == TokenChars.PIPE
                or not ch
            ):
                break
            elif ch == SPACE or ch == NEW_LINE:
                if self._is_text_start(scnr):
                    buf += ch
                    scnr.next()
                elif self._is_plural_start(scnr):
                    break
                else:
                    buf += ch
                    scnr.next()
            else:
                buf += ch
                scnr.next()
        return buf

    def _read_named_identifier(self, scnr: Scanner) -> str:
        self._skip_spaces(scnr)

        name = ""
        while ch := self._take_named_identifier_char(scnr):
            name += ch

        # Did the loop stop on a character that has no business being in a placeholder, rather than
        # on the closing brace? If so the whole run is reported, so the message names the offender.
        current_char = scnr.current_char()
        if (
            current_char
            and current_char != "}"
            and current_char is not None
            and current_char != SPACE
            and current_char != NEW_LINE
            and current_char != IDEOGRAPHIC_SPACE
        ):
            invalid_part = self._read_invalid_identifier(scnr)
            self._emit_error(
                CompileErrorCodes.INVALID_TOKEN_IN_PLACEHOLDER,
                self.current_position(),
                0,
                name + invalid_part,
            )
            return name + invalid_part

        if scnr.current_char() is None:
            self._emit_error(CompileErrorCodes.UNTERMINATED_CLOSING_BRACE, self.current_position(), 0)

        return name

    def _read_list_identifier(self, scnr: Scanner) -> str:
        self._skip_spaces(scnr)

        value = ""
        if scnr.current_char() == "-":
            scnr.next()
            value += f"-{self._get_digits(scnr)}"
        else:
            value += self._get_digits(scnr)

        if scnr.current_char() is None:
            self._emit_error(CompileErrorCodes.UNTERMINATED_CLOSING_BRACE, self.current_position(), 0)

        return value

    def _read_literal(self, scnr: Scanner) -> str:
        self._skip_spaces(scnr)
        self._eat(scnr, "'")

        literal = ""
        while ch := self._take_char(scnr, _is_literal):
            if ch == "\\":
                literal += self._read_escape_sequence(scnr)
            else:
                literal += ch

        current = scnr.current_char()
        if current == NEW_LINE or current is None:
            self._emit_error(
                CompileErrorCodes.UNTERMINATED_SINGLE_QUOTE_IN_PLACEHOLDER, self.current_position(), 0
            )
            if current == NEW_LINE:
                scnr.next()
                self._eat(scnr, "'")
            return literal

        self._eat(scnr, "'")
        return literal

    def _read_escape_sequence(self, scnr: Scanner) -> str:
        ch = scnr.current_char()
        if ch == "\\" or ch == "'":
            scnr.next()
            return f"\\{ch}"
        if ch == "u":
            return self._read_unicode_escape_sequence(scnr, ch, 4)
        if ch == "U":
            return self._read_unicode_escape_sequence(scnr, ch, 6)
        self._emit_error(CompileErrorCodes.UNKNOWN_ESCAPE_SEQUENCE, self.current_position(), 0, ch)
        return ""

    def _read_unicode_escape_sequence(self, scnr: Scanner, unicode_char: str, digits: int) -> str:
        self._eat(scnr, unicode_char)

        sequence = ""
        for _ in range(digits):
            ch = self._take_hex_digit(scnr)
            if not ch:
                self._emit_error(
                    CompileErrorCodes.INVALID_UNICODE_ESCAPE_SEQUENCE,
                    self.current_position(),
                    0,
                    f"\\{unicode_char}{sequence}{scnr.current_char()}",
                )
                break
            sequence += ch

        return f"\\{unicode_char}{sequence}"

    def _read_invalid_identifier(self, scnr: Scanner) -> str:
        self._skip_spaces(scnr)

        identifiers = ""
        while ch := self._take_char(scnr, _is_invalid_identifier):
            identifiers += ch
        return identifiers

    def _read_linked_modifier(self, scnr: Scanner) -> str:
        name = ""
        while ch := self._take_identifier_char(scnr):
            name += ch
        return name

    def _read_linked_refer(self, scnr: Scanner) -> str:
        buf = ""
        while True:
            ch = scnr.current_char()
            if (
                ch == TokenChars.BRACE_LEFT
                or ch == TokenChars.LINKED_ALIAS
                or ch == TokenChars.PIPE
                or ch == TokenChars.PAREN_LEFT
                or ch == TokenChars.PAREN_RIGHT
                or not ch
                or ch == SPACE
            ):
                return buf
            # Newline and dot are part of the key: dotted paths, and upstream lets a key wrap.
            buf += ch
            scnr.next()

    def _read_plural(self, scnr: Scanner) -> str:
        self._skip_spaces(scnr)
        plural = self._eat(scnr, TokenChars.PIPE)
        self._skip_spaces(scnr)
        return plural

    # -- token readers ----------------------------------------------------------------------------

    def _read_token_in_placeholder(self, scnr: Scanner, ctx: TokenizeContext) -> Token | None:
        ch = scnr.current_char()

        if ch == TokenChars.BRACE_LEFT:
            if ctx.brace_nest >= 1:
                self._emit_error(CompileErrorCodes.NOT_ALLOW_NEST_PLACEHOLDER, self.current_position(), 0)
            scnr.next()
            token = self._get_token(ctx, TokenTypes.BRACE_LEFT, TokenChars.BRACE_LEFT)
            self._skip_spaces(scnr)
            ctx.brace_nest += 1
            return token

        if ch == TokenChars.BRACE_RIGHT:
            if ctx.brace_nest > 0 and ctx.current_type == TokenTypes.BRACE_LEFT:
                self._emit_error(CompileErrorCodes.EMPTY_PLACEHOLDER, self.current_position(), 0)
            scnr.next()
            token = self._get_token(ctx, TokenTypes.BRACE_RIGHT, TokenChars.BRACE_RIGHT)
            ctx.brace_nest -= 1
            if ctx.brace_nest > 0:
                self._skip_spaces(scnr)
            if ctx.in_linked and ctx.brace_nest == 0:
                ctx.in_linked = False
            return token

        if ch == TokenChars.LINKED_ALIAS:
            if ctx.brace_nest > 0:
                self._emit_error(CompileErrorCodes.UNTERMINATED_CLOSING_BRACE, self.current_position(), 0)
            token = self._read_token_in_linked(scnr, ctx) or self._get_end_token(ctx)
            ctx.brace_nest = 0
            return token

        # default branch
        if self._is_plural_start(scnr):
            if ctx.brace_nest > 0:
                self._emit_error(CompileErrorCodes.UNTERMINATED_CLOSING_BRACE, self.current_position(), 0)
            token = self._get_token(ctx, TokenTypes.PIPE, self._read_plural(scnr))
            ctx.brace_nest = 0
            ctx.in_linked = False
            return token

        if ctx.brace_nest > 0 and ctx.current_type in (
            TokenTypes.NAMED,
            TokenTypes.LIST,
            TokenTypes.LITERAL,
        ):
            self._emit_error(CompileErrorCodes.UNTERMINATED_CLOSING_BRACE, self.current_position(), 0)
            ctx.brace_nest = 0
            return self._read_token(scnr, ctx)

        valid_named_identifier = self._is_named_identifier_start(scnr, ctx)
        if valid_named_identifier:
            token = self._get_token(ctx, TokenTypes.NAMED, self._read_named_identifier(scnr))
            self._skip_spaces(scnr)
            return token

        valid_list_identifier = self._is_list_identifier_start(scnr, ctx)
        if valid_list_identifier:
            token = self._get_token(ctx, TokenTypes.LIST, self._read_list_identifier(scnr))
            self._skip_spaces(scnr)
            return token

        valid_literal = self._is_literal_start(scnr, ctx)
        if valid_literal:
            token = self._get_token(ctx, TokenTypes.LITERAL, self._read_literal(scnr))
            self._skip_spaces(scnr)
            return token

        if not valid_named_identifier and not valid_list_identifier and not valid_literal:
            token = self._get_token(ctx, TokenTypes.INVALID_PLACE, self._read_invalid_identifier(scnr))
            self._emit_error(
                CompileErrorCodes.INVALID_TOKEN_IN_PLACEHOLDER, self.current_position(), 0, token.value
            )
            self._skip_spaces(scnr)
            return token

        return None

    def _read_token_in_linked(self, scnr: Scanner, ctx: TokenizeContext) -> Token | None:
        current_type = ctx.current_type
        ch = scnr.current_char()

        if current_type in (
            TokenTypes.LINKED_ALIAS,
            TokenTypes.LINKED_DOT,
            TokenTypes.LINKED_MODIFIER,
            TokenTypes.LINKED_DELIMITER,
        ) and (ch == NEW_LINE or ch == SPACE):
            self._emit_error(CompileErrorCodes.INVALID_LINKED_FORMAT, self.current_position(), 0)

        if ch == TokenChars.LINKED_ALIAS:
            scnr.next()
            token = self._get_token(ctx, TokenTypes.LINKED_ALIAS, TokenChars.LINKED_ALIAS)
            ctx.in_linked = True
            return token

        if ch == TokenChars.LINKED_DOT:
            self._skip_spaces(scnr)
            scnr.next()
            return self._get_token(ctx, TokenTypes.LINKED_DOT, TokenChars.LINKED_DOT)

        if ch == TokenChars.LINKED_DELIMITER:
            self._skip_spaces(scnr)
            scnr.next()
            return self._get_token(ctx, TokenTypes.LINKED_DELIMITER, TokenChars.LINKED_DELIMITER)

        # default branch
        if self._is_plural_start(scnr):
            token = self._get_token(ctx, TokenTypes.PIPE, self._read_plural(scnr))
            ctx.brace_nest = 0
            ctx.in_linked = False
            return token

        if self._is_linked_dot_start(scnr, ctx) or self._is_linked_delimiter_start(scnr, ctx):
            self._skip_spaces(scnr)
            return self._read_token_in_linked(scnr, ctx)

        if self._is_linked_modifier_start(scnr, ctx):
            self._skip_spaces(scnr)
            return self._get_token(ctx, TokenTypes.LINKED_MODIFIER, self._read_linked_modifier(scnr))

        if self._is_linked_refer_start(scnr, ctx):
            self._skip_spaces(scnr)
            if ch == TokenChars.BRACE_LEFT:
                # `@:{'dynamic.key'}` - the key is itself a placeholder.
                return self._read_token_in_placeholder(scnr, ctx) or None
            return self._get_token(ctx, TokenTypes.LINKED_KEY, self._read_linked_refer(scnr))

        if current_type == TokenTypes.LINKED_ALIAS:
            self._emit_error(CompileErrorCodes.INVALID_LINKED_FORMAT, self.current_position(), 0)

        ctx.brace_nest = 0
        ctx.in_linked = False
        return self._read_token(scnr, ctx)

    def _read_token(self, scnr: Scanner, ctx: TokenizeContext) -> Token:
        if ctx.brace_nest > 0:
            return self._read_token_in_placeholder(scnr, ctx) or self._get_end_token(ctx)

        if ctx.in_linked:
            return self._read_token_in_linked(scnr, ctx) or self._get_end_token(ctx)

        ch = scnr.current_char()

        if ch == TokenChars.BRACE_LEFT:
            return self._read_token_in_placeholder(scnr, ctx) or self._get_end_token(ctx)

        if ch == TokenChars.BRACE_RIGHT:
            self._emit_error(CompileErrorCodes.UNBALANCED_CLOSING_BRACE, self.current_position(), 0)
            scnr.next()
            return self._get_token(ctx, TokenTypes.BRACE_RIGHT, TokenChars.BRACE_RIGHT)

        if ch == TokenChars.LINKED_ALIAS:
            return self._read_token_in_linked(scnr, ctx) or self._get_end_token(ctx)

        if self._is_plural_start(scnr):
            token = self._get_token(ctx, TokenTypes.PIPE, self._read_plural(scnr))
            ctx.brace_nest = 0
            ctx.in_linked = False
            return token

        if self._is_text_start(scnr):
            return self._get_token(ctx, TokenTypes.TEXT, self._read_text(scnr))

        # Upstream returns a bare `{ type: EOF }` here - no location, and without touching the
        # context. Ported as-is: `nextToken` relies on the context still describing the last real
        # token when the stream ends in an unexpected place.
        return Token(type=TokenTypes.EOF)

    # -- public API -------------------------------------------------------------------------------

    def next_token(self) -> Token:
        ctx = self._context
        ctx.last_type = ctx.current_type
        ctx.last_offset = ctx.offset
        ctx.last_start_loc = ctx.start_loc
        ctx.last_end_loc = ctx.end_loc
        ctx.offset = self.current_offset()
        ctx.start_loc = self.current_position()

        if self._scnr.current_char() is None:
            return self._get_token(ctx, TokenTypes.EOF)

        return self._read_token(self._scnr, ctx)


def create_tokenizer(source: str, options: TokenizeOptions | None = None) -> Tokenizer:
    return Tokenizer(source, options)


def tokenize(source: str, options: TokenizeOptions | None = None) -> list[Token]:
    """Drain a tokenizer into a list. Upstream calls this ``parse``; renamed to avoid confusion
    with the parser proper, which is a different thing in the same package."""
    tokens: list[Token] = []
    tokenizer = create_tokenizer(source, options)

    while True:
        token = tokenizer.next_token()
        tokens.append(token)
        if token.type == TokenTypes.EOF:
            break

    return tokens
