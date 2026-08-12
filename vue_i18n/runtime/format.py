"""Render a message AST against a context.

Port of ``packages/core-base/src/format.ts``.

Upstream's counterpart exists because vue-i18n can either compile a message into a JavaScript
function or walk its AST; this is the walking half, and it is the only half this port needs. The
shape is preserved exactly — ``format_parts`` for the resource, ``format_message_parts`` for one
plural branch, ``format_message_part`` for one node — so a reader can hold both files side by side.
"""

from collections.abc import Callable
from typing import Any

from ..compiler.nodes import (
    LinkedNode,
    ListNode,
    MessageNode,
    NamedNode,
    Node,
    NodeTypes,
    PluralNode,
    ResourceNode,
)
from .message_context import MessageContext

#: The four node kinds that are nothing but a string once parsed.
_VALUE_NODES = (
    NodeTypes.TEXT,
    NodeTypes.LITERAL,
    NodeTypes.LINKED_KEY,
    NodeTypes.LINKED_MODIFIER,
)


class UnhandledNodeError(Exception):
    """A node the renderer has no rule for. Upstream raises a bare ``Error`` with the same text."""

    def __init__(self, node_type: Any) -> None:
        super().__init__(f"unhandled node type: {node_type}")
        self.node_type = node_type


def format_message_part(ctx: MessageContext, node: Node) -> Any:
    node_type = node.type

    if node_type in _VALUE_NODES:
        value = getattr(node, "value", None)
        if value is None:
            raise UnhandledNodeError(node_type)
        return value

    if node_type == NodeTypes.NAMED and isinstance(node, NamedNode):
        if not node.key:
            raise UnhandledNodeError(node_type)
        return ctx.interpolate(ctx.named(node.key))

    if node_type == NodeTypes.LIST and isinstance(node, ListNode):
        if not isinstance(node.index, int) or isinstance(node.index, bool):
            raise UnhandledNodeError(node_type)
        return ctx.interpolate(ctx.list(node.index))

    if node_type == NodeTypes.LINKED and isinstance(node, LinkedNode):
        if node.key is None:
            raise UnhandledNodeError(NodeTypes.LINKED)
        key = format_message_part(ctx, node.key)
        modifier = format_message_part(ctx, node.modifier) if node.modifier is not None else None
        return ctx.linked(key, modifier, ctx.type)

    raise UnhandledNodeError(node_type)


def format_message_parts(ctx: MessageContext, node: MessageNode) -> Any:
    # `static` is set by upstream's optimizer pass, which this port does not run - it exists to let
    # a message of pure text skip interpretation, and skipping it changes nothing but speed. The
    # branch is kept so that an AST produced by upstream's own optimizer still renders here.
    if node.static is not None:
        return node.static if ctx.type == "text" else ctx.normalize([node.static])

    return ctx.normalize([format_message_part(ctx, item) for item in node.items])


def format_parts(ctx: MessageContext, ast: ResourceNode) -> Any:
    body = ast.body
    if body is None:
        raise UnhandledNodeError(NodeTypes.RESOURCE)

    if isinstance(body, PluralNode):
        # Every branch is rendered before one is chosen, exactly as upstream does. It costs work
        # that is thrown away, but a branch can have side effects through a custom modifier and the
        # two ports have to agree on whether those run.
        return ctx.plural([format_message_parts(ctx, case) for case in body.cases])

    return format_message_parts(ctx, body)


def compile_message(ast: ResourceNode) -> Callable[[MessageContext], Any]:
    """Turn an AST into a message function, the callable a resolved message key yields.

    Upstream calls this ``format``. Renamed because ``format`` is a Python builtin and this module
    already has three functions whose names begin with it; the shadowing would read as a mistake.
    """

    def message_function(ctx: MessageContext) -> Any:
        return format_parts(ctx, ast)

    return message_function
