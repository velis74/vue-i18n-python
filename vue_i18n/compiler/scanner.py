"""Character scanner with a separate peek cursor.

Port of ``packages/message-compiler/src/scanner.ts``.

The one thing a reader has to hold on to: JavaScript's ``str[i]`` yields ``undefined`` past either
end of the string, and the tokenizer leans on that everywhere — it compares the result to characters
and tests it for truthiness rather than checking bounds first. Python raises instead, so every read
goes through :func:`_at`, which returns ``None`` for any out-of-range index including a negative
one. ``None`` is falsy and compares unequal to every character, which is exactly how ``undefined``
behaves in the expressions this file was ported from.
"""


CHAR_SP = " "
CHAR_CR = "\r"
CHAR_LF = "\n"
# Written as escapes on purpose: as literal characters these are invisible in an editor and in
# a diff, and LS in particular is indistinguishable from a space at a glance.
CHAR_LS = "\u2028"
CHAR_PS = "\u2029"


def _at(buf: str, index: int) -> str | None:
    """``buf[index]`` with JavaScript's out-of-range behaviour: ``None`` rather than an exception.

    The negative guard is load-bearing. Python would wrap a negative index around to the end of the
    string and hand back a real character, which is not what the ported code means by it.
    """
    if index < 0 or index >= len(buf):
        return None
    return buf[index]


class Scanner:
    """A read cursor (``index``) and a lookahead cursor (``index + peek_offset``).

    Line terminators are normalised on the way out: ``charAt`` reports CRLF, LS and PS as a single
    ``\\n``, so the tokenizer never has to know which of the four it is looking at.
    """

    def __init__(self, source: str) -> None:
        self._buf = source
        self._index = 0
        self._line = 1
        self._column = 1
        self._peek_offset = 0
        # Reported offsets are counted in UTF-16 code units, not in code points - see `u16_index`.
        self._index16 = 0

    # -- line-end classification ------------------------------------------------------------------

    def _is_crlf(self, index: int) -> bool:
        return _at(self._buf, index) == CHAR_CR and _at(self._buf, index + 1) == CHAR_LF

    def _is_lf(self, index: int) -> bool:
        return _at(self._buf, index) == CHAR_LF

    def _is_ps(self, index: int) -> bool:
        return _at(self._buf, index) == CHAR_PS

    def _is_ls(self, index: int) -> bool:
        return _at(self._buf, index) == CHAR_LS

    def _is_line_end(self, index: int) -> bool:
        return self._is_crlf(index) or self._is_lf(index) or self._is_ps(index) or self._is_ls(index)

    # -- cursors ----------------------------------------------------------------------------------

    def index(self) -> int:
        """Cursor as an index into the Python string, i.e. in code points. Internal use only."""
        return self._index

    def u16_index(self) -> int:
        """Cursor in UTF-16 code units, which is what a reported source offset means.

        JavaScript strings are UTF-16, so upstream's offsets and columns count an astral character —
        an emoji, most CJK extension characters — as two. Python counts it as one. Reporting code
        points here would make every location past the first emoji in a message disagree with
        upstream by one, which the conformance corpus would then have to paper over per message.
        Counting units instead costs one integer and keeps this port byte-identical with upstream on
        locations, so a location in a fixture means the same thing in both languages.
        """
        return self._index16

    def line(self) -> int:
        return self._line

    def column(self) -> int:
        return self._column

    def peek_offset(self) -> int:
        return self._peek_offset

    def char_at(self, offset: int) -> str | None:
        if self._is_crlf(offset) or self._is_ps(offset) or self._is_ls(offset):
            return CHAR_LF
        return _at(self._buf, offset)

    def current_char(self) -> str | None:
        return self.char_at(self._index)

    def current_peek(self) -> str | None:
        return self.char_at(self._index + self._peek_offset)

    # -- movement ---------------------------------------------------------------------------------

    def next(self) -> str | None:
        """Advance the read cursor one character (two across a CRLF) and drop the peek cursor."""
        self._peek_offset = 0
        ch = _at(self._buf, self._index)
        if self._is_line_end(self._index):
            self._line += 1
            self._column = 0
        if self._is_crlf(self._index):
            self._index += 1
            self._index16 += 1
        self._index += 1
        self._index16 += 1
        self._column += 1
        # An astral character is two UTF-16 units, so upstream - which scans units - passes through
        # here twice for it and bumps offset and column twice. One step here has to do the same.
        # A CRLF is handled above instead: it is two units but upstream still treats it as one step,
        # because the line-end branch has already reset the column.
        if ch is not None and ord(ch) >= 0x10000:
            self._index16 += 1
            self._column += 1
        return _at(self._buf, self._index)

    def peek(self) -> str | None:
        if self._is_crlf(self._index + self._peek_offset):
            self._peek_offset += 1
        self._peek_offset += 1
        return _at(self._buf, self._index + self._peek_offset)

    def reset(self) -> None:
        self._index = 0
        self._index16 = 0
        self._line = 1
        self._column = 1
        self._peek_offset = 0

    def reset_peek(self, offset: int = 0) -> None:
        self._peek_offset = offset

    def skip_to_peek(self) -> None:
        """Move the read cursor up to where the peek cursor got to, keeping line and column right."""
        target = self._index + self._peek_offset
        while target != self._index:
            self.next()
        self._peek_offset = 0


def create_scanner(source: str) -> Scanner:
    return Scanner(source)
