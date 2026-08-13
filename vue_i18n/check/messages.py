"""Check a set of message resources against itself.

This is the half of the checker that needs no source code at all, and the half a generic JSON linter
cannot do: every message is run through *the real vue-i18n parser*, so a message that will not
compile is found before it reaches a page, and an ``@:linked`` reference is followed to a key that
either exists or does not - reported at the column the link starts on, because the parser records it.

Nothing here loads a file. Resources arrive as ``{locale: nested dict}``, the same shape
``create_core_context`` takes.
"""

from typing import Any

from ..compiler.errors import CompileError
from ..compiler.nodes import LinkedNode, MessageNode, Node, PluralNode, ResourceNode
from ..compiler.parser import create_parser
from ..runtime.message_context import DEFAULT_MODIFIERS
from ..runtime.resolver import resolve_value
from .report import Problem, Report, Severity

#: Past this many forms the built-in rule cannot reach: `min(choice, 2)` tops out at index 2. A
#: message with more forms needs `plural_rules`, which is the single most common surprise in this
#: library - see the plural rules guide.
REACHABLE_FORMS_WITHOUT_A_RULE = 3


def flatten(resource: Any, prefix: str = "") -> dict[str, Any]:
    """Every leaf of a resource, keyed by the dotted path a caller would write.

    A resource may already hold flat dotted keys (``{"a.b": "..."}``), and vue-i18n accepts both, so
    those are emitted verbatim as well as walked.
    """
    found: dict[str, Any] = {}
    if not isinstance(resource, dict):
        return found
    for key, value in resource.items():
        path = f"{prefix}{key}"
        if isinstance(value, dict):
            found.update(flatten(value, f"{path}."))
        else:
            found[path] = value
    return found


def resolves(resource: Any, key: str) -> bool:
    """Exactly how ``translate`` looks a key up: walk the path, then try the flat dotted key.

    Reproduced rather than approximated - a checker that disagrees with the runtime about what
    "missing" means is worse than no checker.
    """
    if resolve_value(resource, key) is not None:
        return True
    return isinstance(resource, dict) and resource.get(key) is not None


def _linked_keys(node: Node) -> list[tuple[str, int | None, str | None]]:
    """Every ``@:key`` in one parsed message, as (key, column-within-the-message, modifier)."""
    found: list[tuple[str, int | None, str | None]] = []

    def walk(current: Node) -> None:
        if isinstance(current, LinkedNode):
            key_node = current.key
            # A dynamic link - `@:{someVar}` - has a NamedNode or ListNode key, which no static
            # check can follow. Only a literal key is worth reporting on.
            value = getattr(key_node, "value", None)
            if isinstance(value, str):
                loc = getattr(key_node, "loc", None)
                modifier = getattr(current.modifier, "value", None)
                found.append((value, loc.start.column if loc else None, modifier))
        for attribute in ("items", "cases", "body"):
            child = getattr(current, attribute, None)
            if isinstance(child, list):
                for item in child:
                    walk(item)
            elif isinstance(child, Node):
                walk(child)

    walk(node)
    return found


def _form_count(ast: ResourceNode) -> int:
    """How many plural forms a message supplies; 1 when it is not a plural at all."""
    body = ast.body
    if isinstance(body, PluralNode):
        return len(body.cases)
    return 1 if isinstance(body, MessageNode) else 1


def check_messages(
    resources: dict[str, Any],
    base_locale: str | None = None,
    modifiers: set[str] | None = None,
    file_of: dict[str, str] | None = None,
) -> Report:
    """Compile every message, follow every link, and compare each locale against the base one.

    ``base_locale`` defaults to ``en`` when present and otherwise to the first locale given; it is
    the one whose key set the others are measured against. ``file_of`` maps a locale to the file it
    came from, purely so a problem can name it.
    """
    report = Report()
    if not resources:
        return report

    known_modifiers = set(DEFAULT_MODIFIERS) if modifiers is None else modifiers
    files = file_of or {}
    if base_locale is None:
        base_locale = "en" if "en" in resources else next(iter(resources))

    flattened = {locale: flatten(resource) for locale, resource in resources.items()}

    for locale, messages in flattened.items():
        file = files.get(locale)
        for key, value in messages.items():
            if not isinstance(value, str):
                continue

            errors: list[CompileError] = []
            ast = create_parser(on_error=errors.append).parse(value)
            for error in errors:
                loc = error.location
                report.add(
                    Problem(
                        severity=Severity.ERROR,
                        kind="does-not-compile",
                        detail=f"{key}: {error}",
                        file=file,
                        in_message=loc.start.column if loc else None,
                        locale=locale,
                        key=key,
                    )
                )
            if errors:
                continue

            for link, column, modifier in _linked_keys(ast):
                # A link resolves through the fallback chain at runtime, and this checker is not
                # told the chain - so anywhere is good enough to not be an error. Reported only when
                # no locale at all has it, which no chain can rescue.
                if not any(resolves(resource, link) for resource in resources.values()):
                    report.add(
                        Problem(
                            severity=Severity.ERROR,
                            kind="broken-link",
                            detail=f"{key}: @:{link} resolves in no locale",
                            file=file,
                            in_message=column,
                            locale=locale,
                            key=key,
                        )
                    )
                elif not resolves(resources[locale], link):
                    report.add(
                        Problem(
                            severity=Severity.WARNING,
                            kind="link-needs-fallback",
                            detail=f"{key}: @:{link} is not in {locale}, so it needs the fallback chain",
                            file=file,
                            in_message=column,
                            locale=locale,
                            key=key,
                        )
                    )
                if modifier is not None and modifier not in known_modifiers:
                    report.add(
                        Problem(
                            severity=Severity.WARNING,
                            kind="unknown-modifier",
                            detail=(
                                f"{key}: @.{modifier}: is not built in - pass it as a custom "
                                f"modifier, or it renders the message unchanged"
                            ),
                            file=file,
                            in_message=column,
                            locale=locale,
                            key=key,
                        )
                    )

            forms = _form_count(ast)
            if forms > REACHABLE_FORMS_WITHOUT_A_RULE:
                report.add(
                    Problem(
                        severity=Severity.WARNING,
                        kind="unreachable-plural-form",
                        detail=(
                            f"{key}: {forms} plural forms, but the built-in rule stops at "
                            f"{REACHABLE_FORMS_WITHOUT_A_RULE} - pass plural_rules for {locale} or "
                            f"the last {forms - REACHABLE_FORMS_WITHOUT_A_RULE} never render"
                        ),
                        file=file,
                        locale=locale,
                        key=key,
                    )
                )

    base_keys = set(flattened.get(base_locale, {}))
    for locale, messages in flattened.items():
        if locale == base_locale:
            continue
        for key in sorted(base_keys - set(messages)):
            report.add(
                Problem(
                    severity=Severity.WARNING,
                    kind="missing-key",
                    detail=f"{key}: in {base_locale}, not in {locale}",
                    file=files.get(locale),
                    locale=locale,
                    key=key,
                )
            )
        for key in sorted(set(messages) - base_keys):
            report.add(
                Problem(
                    severity=Severity.WARNING,
                    kind="extra-key",
                    detail=f"{key}: in {locale}, not in {base_locale}",
                    file=files.get(locale),
                    locale=locale,
                    key=key,
                )
            )

    return report
