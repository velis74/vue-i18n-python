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


def load_resource(path: Path) -> Any:
    """One message file. YAML only when PyYAML is present, and it says so when it is not."""
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        return json.loads(text)
    try:
        import yaml
    except ImportError:
        raise SystemExit(
            f"{path}: reading YAML needs PyYAML, which this package does not depend on.\n"
            f"Install it (`pip install pyyaml`), or load the messages yourself and call "
            f"`vue_i18n.check.check_messages` directly."
        ) from None
    return yaml.safe_load(text)


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


def render(report: Report, out: Any) -> None:
    width = max((len(problem.location() or problem.locale or "") for problem in report.problems), default=0)
    for problem in report.problems:
        where = problem.location() or problem.locale or ""
        # `in_message` is a column inside the message text, not inside the file, so it is spelled
        # out rather than appended to the location where it would read as a file coordinate.
        at = f" (at character {problem.in_message} of the message)" if problem.in_message else ""
        print(f"{MARKERS[problem.severity]}  {where:<{width}}  {problem.detail}{at}", file=out)
    if report.problems:
        print(file=out)
    print(report.summary(), file=out)


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
    parser.add_argument("--base-locale", metavar="LOCALE", help="the locale others are compared against (default: en)")
    parser.add_argument("--no-unused", action="store_true", help="do not report messages nothing asks for")
    parser.add_argument("--quiet", action="store_true", help="errors only")
    args = parser.parse_args(argv)

    resources, files = collect_resources(args.messages)
    if not resources:
        print("no message files found", file=sys.stderr)
        return 2

    report = check_messages(resources, base_locale=args.base_locale, file_of=files)

    if args.source:
        uses = [use for path in args.source for use in extract_from_path(path)]
        report.extend(check_sources(uses, resources, report_unused=not args.no_unused))

    if args.quiet:
        report = Report(report.errors)

    render(report, sys.stdout)
    return 1 if report.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
