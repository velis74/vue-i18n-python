"""Source positions and ranges.

Port of ``packages/message-compiler/src/location.ts``. The one deviation from a literal port is that
``Position`` is mutable and carries ``__eq__``: ``Tokenizer._emit_error`` advances a position in
place, exactly as the TypeScript does, and the conformance corpus compares locations by value.
"""

from dataclasses import dataclass


@dataclass
class Position:
    """A point in the source. ``offset`` counts from the start of the message, not of the line."""

    line: int
    column: int
    offset: int

    def copy(self) -> "Position":
        return Position(self.line, self.column, self.offset)


@dataclass
class SourceLocation:
    """A half-open range ``[start, end)`` over the source."""

    start: Position
    end: Position
    source: str | None = None


def create_position(line: int, column: int, offset: int) -> Position:
    return Position(line=line, column=column, offset=offset)


def create_location(start: Position, end: Position, source: str | None = None) -> SourceLocation:
    loc = SourceLocation(start=start, end=end)
    if source is not None:
        loc.source = source
    return loc


LOCATION_STUB = SourceLocation(
    start=Position(line=1, column=1, offset=0),
    end=Position(line=1, column=1, offset=0),
)
