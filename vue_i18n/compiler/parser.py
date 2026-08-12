"""Message parser: token stream in, AST out.

Port of ``packages/message-compiler/src/parser.ts``.

The parser is error-tolerant by design. Every defect is reported through ``on_error`` and parsing
then continues with a best guess, because a translation file with one broken message should render
the other nine hundred rather than fail to load. Callers that want strictness pass an ``on_error``
that raises - :func:`vue_i18n.compiler.errors.default_on_error` does exactly that.
"""

import re

from collections.abc import Callable
from typing import Any

from .errors import CompileErrorCodes, create_compile_error
from .location import create_location, Position, SourceLocation
from .nodes import (
    LinkedKeyNode,
    LinkedModifierNode,
    LinkedNode,
    ListNode,
    LiteralNode,
    MessageNode,
    NamedNode,
    Node,
    NodeTypes,
    PluralNode,
    ResourceNode,
    TextNode,
)
from .tokenizer import create_tokenizer, Token, TokenizeOptions, Tokenizer, TokenTypes

ERROR_DOMAIN = "parser"

#: Backslash backslash, backslash quote, uHHHH, UHHHHHH - the escapes a *literal* understands.
KNOWN_ESCAPES = re.compile(r"\\\\|\\'|\\u([0-9a-fA-F]{4})|\\U([0-9a-fA-F]{6})")

#: The escapes *text* understands: a backslash before one of the five characters that would
#: otherwise start something.
TEXT_ESCAPES = re.compile(r"\\([\\@{}|])")

REPLACEMENT_CHARACTER = "�"


def _from_text_escape_sequence(match: re.Match) -> str:
    return match.group(1)


def _from_escape_sequence(match: re.Match) -> str:
    whole = match.group(0)
    if whole == "\\\\":
        return "\\"
    if whole == "\\'":
        return "'"

    code_point = int(match.group(1) or match.group(2), 16)
    if code_point <= 0xD7FF or 0xE000 <= code_point <= 0x10FFFF:
        return chr(code_point)
    # A lone surrogate, or a `\U` sequence past the last code point. Upstream's
    # `String.fromCodePoint` throws a RangeError for the latter; this port folds it into the
    # replacement character the former already produces, because a malformed escape in one message
    # should not take down the load of a whole file.
    return REPLACEMENT_CHARACTER


def _u16_char_at(source: str, offset: int) -> str:
    """``source[offset]`` where ``offset`` counts UTF-16 code units, as tokenizer offsets do.

    Only an error caption depends on this, but indexing a Python string with a UTF-16 offset would
    silently pick the wrong character in any message containing an emoji - and the character named
    in a syntax error is the one thing the reader uses to find the problem.
    """
    units = source.encode("utf-16-le", errors="surrogatepass")
    if offset < 0 or (offset + 1) * 2 > len(units):
        return ""
    return units[offset * 2 : (offset + 1) * 2].decode("utf-16-le", errors="surrogatepass")


def _get_token_caption(token: Token) -> str:
    """Short, single-line rendering of a token, for the text of an error message."""
    if token.type == TokenTypes.EOF:
        return "EOF"
    name = re.sub(r"\r?\n", "\\\\n", token.value or "")
    return name[:9] + "…" if len(name) > 10 else name


class Parser:
    def __init__(
        self,
        location: bool = True,
        on_error: Callable[[Exception], None] | None = None,
        on_cache_key: Callable[[str], str] | None = None,
    ) -> None:
        self._location = location is not False
        self._on_error = on_error
        self._on_cache_key = on_cache_key

    # -- helpers ----------------------------------------------------------------------------------

    def _emit_error(
        self, tokenizer: Tokenizer, code: int, start: Position, offset: int, *args: Any
    ) -> None:
        end = tokenizer.current_position()
        end.offset += offset
        end.column += offset
        if self._on_error:
            loc = create_location(start, end) if self._location else None
            self._on_error(create_compile_error(code, loc, domain=ERROR_DOMAIN, args=list(args)))

    def _start_node(self, node: Node, offset: int, loc: Position) -> Node:
        if self._location:
            node.start = offset
            node.end = offset
            node.loc = SourceLocation(start=loc, end=loc)
        return node

    def _end_node(self, node: Node, offset: int, pos: Position) -> None:
        if self._location:
            node.end = offset
            if node.loc:
                node.loc.end = pos

    # -- leaf parsers -----------------------------------------------------------------------------

    def _parse_text(self, tokenizer: Tokenizer, value: str) -> TextNode:
        ctx = tokenizer.context()
        node: TextNode = self._start_node(TextNode(type=NodeTypes.TEXT), ctx.offset, ctx.start_loc)
        node.value = TEXT_ESCAPES.sub(_from_text_escape_sequence, value)
        self._end_node(node, tokenizer.current_offset(), tokenizer.current_position())
        return node

    def _parse_list(self, tokenizer: Tokenizer, index: str) -> ListNode:
        ctx = tokenizer.context()
        # The list node starts at the brace, which is the *previous* token.
        node: ListNode = self._start_node(
            ListNode(type=NodeTypes.LIST), ctx.last_offset, ctx.last_start_loc
        )
        node.index = int(index)
        tokenizer.next_token()  # skip brace right
        self._end_node(node, tokenizer.current_offset(), tokenizer.current_position())
        return node

    def _parse_named(self, tokenizer: Tokenizer, key: str) -> NamedNode:
        ctx = tokenizer.context()
        node: NamedNode = self._start_node(
            NamedNode(type=NodeTypes.NAMED), ctx.last_offset, ctx.last_start_loc
        )
        node.key = key
        tokenizer.next_token()  # skip brace right
        self._end_node(node, tokenizer.current_offset(), tokenizer.current_position())
        return node

    def _parse_literal(self, tokenizer: Tokenizer, value: str) -> LiteralNode:
        ctx = tokenizer.context()
        node: LiteralNode = self._start_node(
            LiteralNode(type=NodeTypes.LITERAL), ctx.last_offset, ctx.last_start_loc
        )
        node.value = KNOWN_ESCAPES.sub(_from_escape_sequence, value)
        tokenizer.next_token()  # skip brace right
        self._end_node(node, tokenizer.current_offset(), tokenizer.current_position())
        return node

    def _parse_linked_key(self, tokenizer: Tokenizer, value: str) -> LinkedKeyNode:
        ctx = tokenizer.context()
        node: LinkedKeyNode = self._start_node(
            LinkedKeyNode(type=NodeTypes.LINKED_KEY), ctx.offset, ctx.start_loc
        )
        node.value = value
        self._end_node(node, tokenizer.current_offset(), tokenizer.current_position())
        return node

    # -- linked -----------------------------------------------------------------------------------

    def _parse_linked_modifier(self, tokenizer: Tokenizer) -> tuple[Token | None, LinkedModifierNode]:
        token = tokenizer.next_token()
        ctx = tokenizer.context()
        node: LinkedModifierNode = self._start_node(
            LinkedModifierNode(type=NodeTypes.LINKED_MODIFIER), ctx.last_offset, ctx.last_start_loc
        )

        if token.type != TokenTypes.LINKED_MODIFIER:
            # `@.:key` - the dot promised a modifier and none arrived. The token is handed back so
            # the caller can reconsider it rather than lose it.
            self._emit_error(
                tokenizer, CompileErrorCodes.UNEXPECTED_EMPTY_LINKED_MODIFIER, ctx.last_start_loc, 0
            )
            node.value = ""
            self._end_node(node, ctx.last_offset, ctx.last_start_loc)
            return token, node

        if token.value is None:
            self._emit_error(
                tokenizer,
                CompileErrorCodes.UNEXPECTED_LEXICAL_ANALYSIS,
                ctx.last_start_loc,
                0,
                _get_token_caption(token),
            )

        node.value = token.value or ""
        self._end_node(node, tokenizer.current_offset(), tokenizer.current_position())
        return None, node

    def _parse_linked(self, tokenizer: Tokenizer) -> tuple[Token | None, LinkedNode]:
        ctx = tokenizer.context()
        linked_node: LinkedNode = self._start_node(
            LinkedNode(type=NodeTypes.LINKED), ctx.offset, ctx.start_loc
        )

        token = tokenizer.next_token()
        if token.type == TokenTypes.LINKED_DOT:
            next_consume, modifier = self._parse_linked_modifier(tokenizer)
            linked_node.modifier = modifier
            token = next_consume or tokenizer.next_token()

        if token.type != TokenTypes.LINKED_DELIMITER:
            self._emit_error(
                tokenizer,
                CompileErrorCodes.UNEXPECTED_LEXICAL_ANALYSIS,
                ctx.last_start_loc,
                0,
                _get_token_caption(token),
            )
        token = tokenizer.next_token()

        # `@:{'key'}` and `@:{name}` wrap the key in a placeholder; skip its opening brace.
        if token.type == TokenTypes.BRACE_LEFT:
            token = tokenizer.next_token()

        def check_value() -> None:
            if token.value is None:
                self._emit_error(
                    tokenizer,
                    CompileErrorCodes.UNEXPECTED_LEXICAL_ANALYSIS,
                    ctx.last_start_loc,
                    0,
                    _get_token_caption(token),
                )

        if token.type == TokenTypes.LINKED_KEY:
            check_value()
            linked_node.key = self._parse_linked_key(tokenizer, token.value or "")
        elif token.type == TokenTypes.NAMED:
            check_value()
            linked_node.key = self._parse_named(tokenizer, token.value or "")
        elif token.type == TokenTypes.LIST:
            check_value()
            linked_node.key = self._parse_list(tokenizer, token.value or "")
        elif token.type == TokenTypes.LITERAL:
            check_value()
            linked_node.key = self._parse_literal(tokenizer, token.value or "")
        else:
            # `@:` with nothing after it. An empty key node keeps the AST well-formed.
            self._emit_error(
                tokenizer, CompileErrorCodes.UNEXPECTED_EMPTY_LINKED_KEY, ctx.last_start_loc, 0
            )
            next_ctx = tokenizer.context()
            empty_key: LinkedKeyNode = self._start_node(
                LinkedKeyNode(type=NodeTypes.LINKED_KEY), next_ctx.offset, next_ctx.start_loc
            )
            empty_key.value = ""
            self._end_node(empty_key, next_ctx.offset, next_ctx.start_loc)
            linked_node.key = empty_key
            self._end_node(linked_node, next_ctx.offset, next_ctx.start_loc)
            return token, linked_node

        self._end_node(linked_node, tokenizer.current_offset(), tokenizer.current_position())
        return None, linked_node

    # -- message and plural -----------------------------------------------------------------------

    def _parse_message(self, tokenizer: Tokenizer) -> MessageNode:
        ctx = tokenizer.context()
        # After a pipe the message starts where the pipe ended, not where the previous one began.
        start_offset = tokenizer.current_offset() if ctx.current_type == TokenTypes.PIPE else ctx.offset
        start_loc = ctx.end_loc if ctx.current_type == TokenTypes.PIPE else ctx.start_loc

        node: MessageNode = self._start_node(MessageNode(type=NodeTypes.MESSAGE), start_offset, start_loc)
        node.items = []

        next_token: Token | None = None
        while True:
            token = next_token or tokenizer.next_token()
            next_token = None

            if token.type == TokenTypes.TEXT:
                if token.value is None:
                    self._emit_error(
                        tokenizer,
                        CompileErrorCodes.UNEXPECTED_LEXICAL_ANALYSIS,
                        ctx.last_start_loc,
                        0,
                        _get_token_caption(token),
                    )
                node.items.append(self._parse_text(tokenizer, token.value or ""))
            elif token.type == TokenTypes.LIST:
                if token.value is None:
                    self._emit_error(
                        tokenizer,
                        CompileErrorCodes.UNEXPECTED_LEXICAL_ANALYSIS,
                        ctx.last_start_loc,
                        0,
                        _get_token_caption(token),
                    )
                node.items.append(self._parse_list(tokenizer, token.value or ""))
            elif token.type == TokenTypes.NAMED:
                if token.value is None:
                    self._emit_error(
                        tokenizer,
                        CompileErrorCodes.UNEXPECTED_LEXICAL_ANALYSIS,
                        ctx.last_start_loc,
                        0,
                        _get_token_caption(token),
                    )
                node.items.append(self._parse_named(tokenizer, token.value or ""))
            elif token.type == TokenTypes.LITERAL:
                if token.value is None:
                    self._emit_error(
                        tokenizer,
                        CompileErrorCodes.UNEXPECTED_LEXICAL_ANALYSIS,
                        ctx.last_start_loc,
                        0,
                        _get_token_caption(token),
                    )
                node.items.append(self._parse_literal(tokenizer, token.value or ""))
            elif token.type == TokenTypes.LINKED_ALIAS:
                next_consume, linked = self._parse_linked(tokenizer)
                node.items.append(linked)
                next_token = next_consume

            if ctx.current_type == TokenTypes.EOF or ctx.current_type == TokenTypes.PIPE:
                break

        # A message that ended at a pipe stops before it, not after it.
        end_offset = ctx.last_offset if ctx.current_type == TokenTypes.PIPE else tokenizer.current_offset()
        end_loc = ctx.last_end_loc if ctx.current_type == TokenTypes.PIPE else tokenizer.current_position()

        self._end_node(node, end_offset, end_loc)
        return node

    def _parse_plural(
        self, tokenizer: Tokenizer, offset: int, loc: Position, msg_node: MessageNode
    ) -> PluralNode:
        ctx = tokenizer.context()
        has_empty_message = len(msg_node.items) == 0

        node: PluralNode = self._start_node(PluralNode(type=NodeTypes.PLURAL), offset, loc)
        node.cases = [msg_node]

        while True:
            msg = self._parse_message(tokenizer)
            if not has_empty_message:
                has_empty_message = len(msg.items) == 0
            node.cases.append(msg)
            if ctx.current_type == TokenTypes.EOF:
                break

        if has_empty_message:
            self._emit_error(tokenizer, CompileErrorCodes.MUST_HAVE_MESSAGES_IN_PLURAL, loc, 0)

        self._end_node(node, tokenizer.current_offset(), tokenizer.current_position())
        return node

    def _parse_resource(self, tokenizer: Tokenizer) -> MessageNode | PluralNode:
        ctx = tokenizer.context()
        offset, start_loc = ctx.offset, ctx.start_loc

        msg_node = self._parse_message(tokenizer)
        if ctx.current_type == TokenTypes.EOF:
            return msg_node
        return self._parse_plural(tokenizer, offset, start_loc, msg_node)

    # -- public API -------------------------------------------------------------------------------

    def parse(self, source: str) -> ResourceNode:
        tokenizer = create_tokenizer(
            source, TokenizeOptions(location=self._location, on_error=self._on_error)
        )
        ctx = tokenizer.context()

        node: ResourceNode = self._start_node(
            ResourceNode(type=NodeTypes.RESOURCE), ctx.offset, ctx.start_loc
        )
        if self._location and node.loc:
            node.loc.source = source

        node.body = self._parse_resource(tokenizer)

        if self._on_cache_key:
            node.cache_key = self._on_cache_key(source)

        # Did anything survive past the point the parser thought was the end?
        if ctx.current_type != TokenTypes.EOF:
            self._emit_error(
                tokenizer,
                CompileErrorCodes.UNEXPECTED_LEXICAL_ANALYSIS,
                ctx.last_start_loc,
                0,
                _u16_char_at(source, ctx.offset),
            )

        self._end_node(node, tokenizer.current_offset(), tokenizer.current_position())
        return node


def create_parser(
    location: bool = True,
    on_error: Callable[[Exception], None] | None = None,
    on_cache_key: Callable[[str], str] | None = None,
) -> Parser:
    return Parser(location=location, on_error=on_error, on_cache_key=on_cache_key)
