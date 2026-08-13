"""What a check found, and how loudly it says so.

Deliberately not exceptions: a checker that stops at the first problem is useless for the job people
actually have, which is "tell me everything wrong with this translation set in one pass".
"""

from dataclasses import dataclass, field
from enum import Enum


class Severity(Enum):
    """Three levels, because two would force a real problem and a maybe into the same bucket."""

    #: The message set is wrong and something will render incorrectly. Exit code 1.
    ERROR = "error"
    #: Probably wrong, but a legitimate setup can produce it - an untranslated key that the fallback
    #: chain covers, a modifier supplied at runtime.
    WARNING = "warning"
    #: Nothing is wrong; the checker simply could not look. A key built at runtime is the case.
    NOTE = "note"


@dataclass(frozen=True)
class Problem:
    """One finding, addressed as precisely as the source allows.

    ``line`` and ``column`` come from the message compiler where a message was parsed, so a broken
    link points at the link rather than at the message holding it.
    """

    severity: Severity
    #: Kebab-case slug naming the check, stable enough to grep or filter on.
    kind: str
    detail: str
    file: str | None = None
    #: Coordinates **in the file**, which only source scanning can supply. A message problem leaves
    #: these unset: the compiler reports positions inside the message string, and a JSON file gives
    #: no way to map those back to a line without a position-aware parser. Printing them as if they
    #: were file coordinates would send a reader to the wrong place, so they go in ``in_message``.
    line: int | None = None
    column: int | None = None
    #: Column within the message text, 1-based, when the finding came from parsing a message.
    in_message: int | None = None
    locale: str | None = None
    key: str | None = None

    def location(self) -> str:
        """``file:line:column``, trimmed to whatever is actually known.

        Never includes ``in_message`` - see the note on ``line``.
        """
        parts = [self.file or ""]
        if self.line is not None:
            parts.append(str(self.line))
            if self.column is not None:
                parts.append(str(self.column))
        return ":".join(part for part in parts if part != "")

    def __str__(self) -> str:
        where = self.location() or (self.locale or "")
        return f"{where}  {self.detail}" if where else self.detail


@dataclass
class Report:
    """Every problem from one run, in the order they were found."""

    problems: list[Problem] = field(default_factory=list)

    def add(self, problem: Problem) -> None:
        self.problems.append(problem)

    def extend(self, problems: "list[Problem] | Report") -> None:
        self.problems.extend(problems.problems if isinstance(problems, Report) else problems)

    def of(self, severity: Severity) -> list[Problem]:
        return [problem for problem in self.problems if problem.severity is severity]

    @property
    def errors(self) -> list[Problem]:
        return self.of(Severity.ERROR)

    @property
    def warnings(self) -> list[Problem]:
        return self.of(Severity.WARNING)

    @property
    def notes(self) -> list[Problem]:
        return self.of(Severity.NOTE)

    def __bool__(self) -> bool:
        """True when there is anything to say at all - not only errors."""
        return bool(self.problems)

    def summary(self) -> str:
        # Written out rather than suffixed, because "1 unchecked" and "2 unchecked" do not differ
        # and a library about plural forms should not print "2 uncheckeds".
        counts = [
            (len(self.errors), "1 error", "{n} errors"),
            (len(self.warnings), "1 warning", "{n} warnings"),
            (len(self.notes), "1 unchecked", "{n} unchecked"),
        ]
        said = [(one if count == 1 else many.format(n=count)) for count, one, many in counts if count]
        return ", ".join(said) if said else "nothing to report"
