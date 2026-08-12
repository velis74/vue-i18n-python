"""Message AST.

Port of ``packages/message-compiler/src/nodes.ts``.

Upstream carries a short alias next to every field (``t`` for ``type``, ``b`` for ``body``, ``i`` for
``items`` …) because the AST is serialised into generated JavaScript and every byte shows up in a
bundle. Nothing here is serialised into code, so the aliases are dropped; :func:`to_dict` is the one
place that has to speak upstream's shape, and it emits the long names, which is what upstream's own
``JSON.stringify`` of a parsed node produces.
"""

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any

from .location import SourceLocation


class NodeTypes(IntEnum):
    RESOURCE = 0
    PLURAL = 1
    MESSAGE = 2
    TEXT = 3
    NAMED = 4
    LIST = 5
    LINKED = 6
    LINKED_KEY = 7
    LINKED_MODIFIER = 8
    LITERAL = 9


@dataclass
class Node:
    type: NodeTypes
    start: int | None = None
    end: int | None = None
    loc: SourceLocation | None = None


@dataclass
class TextNode(Node):
    value: str | None = None


@dataclass
class NamedNode(Node):
    key: str = ""


@dataclass
class ListNode(Node):
    index: int = 0


@dataclass
class LiteralNode(Node):
    value: str | None = None


@dataclass
class LinkedKeyNode(Node):
    value: str = ""


@dataclass
class LinkedModifierNode(Node):
    value: str = ""


@dataclass
class LinkedNode(Node):
    key: "LinkedKeyNode | NamedNode | ListNode | LiteralNode | None" = None
    modifier: LinkedModifierNode | None = None


MessageElementNode = TextNode | NamedNode | ListNode | LiteralNode | LinkedNode


@dataclass
class MessageNode(Node):
    items: list[MessageElementNode] = field(default_factory=list)
    #: Set by the optimizer when every item is text, so the runtime can skip interpretation. This
    #: port computes it in `compile`, not in a separate pass.
    static: str | None = None


@dataclass
class PluralNode(Node):
    cases: list[MessageNode] = field(default_factory=list)


@dataclass
class ResourceNode(Node):
    body: MessageNode | PluralNode | None = None
    cache_key: str | None = None


def _loc_to_dict(loc: SourceLocation | None) -> dict[str, Any] | None:
    if loc is None:
        return None
    out: dict[str, Any] = {
        "start": {"line": loc.start.line, "column": loc.start.column, "offset": loc.start.offset},
        "end": {"line": loc.end.line, "column": loc.end.column, "offset": loc.end.offset},
    }
    if loc.source is not None:
        out["source"] = loc.source
    return out


def to_dict(node: Node) -> dict[str, Any]:
    """Serialise a node into the object shape upstream's parser produces.

    Fields upstream never assigns are omitted rather than emitted as null, because the conformance
    corpus compares this against ``JSON.stringify`` of the TypeScript AST and a key that is absent
    on one side and null on the other is a difference the corpus would have to explain away.
    """
    out: dict[str, Any] = {"type": int(node.type)}

    if isinstance(node, ResourceNode):
        if node.body is not None:
            out["body"] = to_dict(node.body)
        if node.cache_key is not None:
            out["cacheKey"] = node.cache_key
    elif isinstance(node, PluralNode):
        out["cases"] = [to_dict(c) for c in node.cases]
    elif isinstance(node, MessageNode):
        out["items"] = [to_dict(i) for i in node.items]
        if node.static is not None:
            out["static"] = node.static
    elif isinstance(node, LinkedNode):
        if node.modifier is not None:
            out["modifier"] = to_dict(node.modifier)
        if node.key is not None:
            out["key"] = to_dict(node.key)
    elif isinstance(node, NamedNode):
        out["key"] = node.key
    elif isinstance(node, ListNode):
        out["index"] = node.index
    elif isinstance(node, (TextNode, LiteralNode, LinkedKeyNode, LinkedModifierNode)):
        if node.value is not None:
            out["value"] = node.value

    if node.start is not None:
        out["start"] = node.start
    if node.end is not None:
        out["end"] = node.end
    if node.loc is not None:
        out["loc"] = _loc_to_dict(node.loc)

    return out
