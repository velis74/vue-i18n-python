"""``python -m vue_i18n.check`` - the checker as a command.

The library never reads a file; this is a tool, and a tool that made you write the loading code
would not get used. JSON always, YAML when PyYAML happens to be installed - not a dependency, and
not an extra, because the library itself still takes messages as an object.
"""

import argparse
import json
import sys

from pathlib import Path
from typing import Any

from .messages import check_messages
from .report import Report, Severity
from .sources import check_sources, extract_from_path

MESSAGE_SUFFIXES = {".json", ".yaml", ".yml"}

MARKERS = {Severity.ERROR: "error", Severity.WARNING: "warn ", Severity.NOTE: "note "}


class UnreadableError(Exception):
    """A message file that could not be read at all - reported, never allowed to reach a traceback.

    A build that prints a stack trace when a translator commits a stray comma has told the person
    who has to fix it nothing useful.
    """


def load_resource(path: Path) -> Any:
    """One message file. YAML only when PyYAML is present, and it says so when it is not."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise UnreadableError(f"{path}: {error.strerror or error}") from None

    if path.suffix.lower() == ".json":
        try:
            return json.loads(text)
        except json.JSONDecodeError as error:
            raise UnreadableError(f"{path}:{error.lineno}:{error.colno}: {error.msg}") from None

    try:
        import yaml
    except ImportError:
        raise UnreadableError(
            f"{path}: reading YAML needs PyYAML, which this package does not depend on. "
            f"Install it (`pip install pyyaml`), or load the messages yourself and call "
            f"`vue_i18n.check.check_messages` directly."
        ) from None
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError as error:
        raise UnreadableError(f"{path}: {error}") from None


def collect_resources(paths: list[Path]) -> tuple[dict[str, Any], dict[str, str]]:
    """Read every message file under the given paths, keyed by filename stem as the locale."""
    resources: dict[str, Any] = {}
    files: dict[str, str] = {}
    for path in paths:
        candidates = sorted(path.rglob("*")) if path.is_dir() else [path]
        for candidate in candidates:
            if candidate.is_file() and candidate.suffix.lower() in MESSAGE_SUFFIXES:
                locale = candidate.stem
                resources[locale] = load_resource(candidate)
                files[locale] = str(candidate)
    return resources, files


def _detail(problem: Any) -> str:
    # `in_message` is a column inside the message text, not inside the file, so it is spelled out
    # rather than appended to the location where it would read as a file coordinate.
    at = f" (at character {problem.in_message} of the message)" if problem.in_message else ""
    return f"{problem.detail}{at}"


def render_text(report: Report, out: Any) -> None:
    width = max((len(problem.location() or problem.locale or "") for problem in report.problems), default=0)
    for problem in report.problems:
        where = problem.location() or problem.locale or ""
        print(f"{MARKERS[problem.severity]}  {where:<{width}}  {_detail(problem)}", file=out)
    if report.problems:
        print(file=out)
    print(report.summary(), file=out)


def render_json(report: Report, out: Any) -> None:
    """One object, so a build step can count or filter without parsing prose."""
    payload = {
        "problems": [
            {
                "severity": problem.severity.value,
                "kind": problem.kind,
                "detail": problem.detail,
                "file": problem.file,
                "line": problem.line,
                "column": problem.column,
                "in_message": problem.in_message,
                "locale": problem.locale,
                "key": problem.key,
            }
            for problem in report.problems
        ],
        "counts": {
            "error": len(report.errors),
            "warning": len(report.warnings),
            "unchecked": len(report.notes),
        },
    }
    json.dump(payload, out, indent=2, ensure_ascii=False)
    print(file=out)


def render_github(report: Report, out: Any) -> None:
    """GitHub Actions workflow commands, so findings land as annotations on the diff."""
    levels = {Severity.ERROR: "error", Severity.WARNING: "warning", Severity.NOTE: "notice"}
    for problem in report.problems:
        fields = []
        if problem.file:
            fields.append(f"file={problem.file}")
            if problem.line is not None:
                fields.append(f"line={problem.line}")
                if problem.column is not None:
                    fields.append(f"col={problem.column}")
        where = ",".join(fields)
        # Annotations are one line each; a newline would end the command early.
        message = _detail(problem).replace("\n", " ")
        print(f"::{levels[problem.severity]} {where}::{message}", file=out)


RENDERERS = {"text": render_text, "json": render_json, "github": render_github}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m vue_i18n.check",
        description="Check vue-i18n message files, and the keys your code asks them for.",
    )
    parser.add_argument("messages", nargs="+", type=Path, help="message file or directory of them; stem is the locale")
    parser.add_argument(
        "--source",
        action="append",
        type=Path,
        default=[],
        metavar="PATH",
        help="code to scan for translation calls; repeatable. .py is parsed, .vue/.ts/.js pattern-matched",
    )
    parser.add_argument(
        "--base-locale",
        metavar="LOCALE",
        help="the source language: keys missing from it fail, keys missing from the others do not (default: en)",
    )
    parser.add_argument("--no-unused", action="store_true", help="do not report messages nothing asks for")
    parser.add_argument("--quiet", action="store_true", help="errors only")
    parser.add_argument("--strict", action="store_true", help="exit non-zero on warnings too, not just errors")
    parser.add_argument("--format", choices=sorted(RENDERERS), default="text", help="output format (default: text)")
    args = parser.parse_args(argv)

    try:
        resources, files = collect_resources(args.messages)
    except UnreadableError as error:
        print(error, file=sys.stderr)
        return 2

    if not resources:
        print("no message files found", file=sys.stderr)
        return 2

    base_locale = args.base_locale
    if base_locale is not None and base_locale not in resources:
        print(f"base locale {base_locale!r} is not among {', '.join(sorted(resources))}", file=sys.stderr)
        return 2

    report = check_messages(resources, base_locale=base_locale, file_of=files)

    if args.source:
        uses = [use for path in args.source for use in extract_from_path(path)]
        report.extend(check_sources(uses, resources, base_locale=base_locale, report_unused=not args.no_unused))

    if args.quiet:
        report = Report(report.errors)

    RENDERERS[args.format](report, sys.stdout)
    return 1 if report.errors or (args.strict and report.warnings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
