"""Static checks for a vue-i18n message set and the code that uses it.

**Not part of the port.** vue-i18n has no such thing, and nothing here changes what a message
renders to — this only reads. It lives in this package for one reason: checking an ``@:linked``
reference means parsing the message, and the parser that agrees with vue-i18n about what a link *is*
is the one in this package. A generic JSON linter cannot follow a link, and a linter that guessed at
the syntax would disagree with the browser about which messages are broken.

Two halves, usable apart:

- :func:`check_messages` reads only the message resources. Every message is compiled, every link is
  followed, every locale is compared against the base one. No source code, no false positives.
- :func:`check_sources` matches the keys a codebase asks for against the keys that exist. Python is
  parsed; ``.vue``, ``.ts`` and ``.js`` are pattern-matched, which is approximate and says so.

::

    from vue_i18n.check import check_messages

    report = check_messages({"en": en, "sl": sl}, base_locale="en")
    for problem in report.problems:
        print(problem.location(), problem.detail)

Or as a command, which does the file loading too::

    python -m vue_i18n.check locales/ --source backend/ --source frontend/src
"""

from .messages import check_messages, flatten, resolves
from .report import Problem, Report, Severity
from .sources import check_sources, extract_from_path, extract_from_python, extract_from_text, KeyUse

__all__ = [
    "KeyUse",
    "Problem",
    "Report",
    "Severity",
    "check_messages",
    "check_sources",
    "extract_from_path",
    "extract_from_python",
    "extract_from_text",
    "flatten",
    "resolves",
]
