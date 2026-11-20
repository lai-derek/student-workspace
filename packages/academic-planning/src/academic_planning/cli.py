"""academic-planning command-line interface."""

import argparse
import json
from pathlib import Path
import sys

import yaml

from . import __version__
from .core import PlanningError, Workspace, import_source
from .records import demo, initialize


def check_summary(result):
    """One line for `student-workspace check`; the JSON form stays the agent interface."""
    records = f"{result.get('requirements', 0)} requirements, {result.get('assignments', 0)} planned courses"
    if result.get("outputs_stale"):
        return f"{records}; outputs are out of date, run `academic-planning build`"
    if not result.get("outputs_built"):
        return f"{records}; outputs not built yet"
    return f"{records}; outputs current"


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="academic-planning",
        description="Academic records, course plans and schedules in a student workspace",
    )
    parser.add_argument("--version", action="version", version=f"academic-planning {__version__}")
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path.cwd(),
        help="Private workspace root (default: current directory)",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check")
    check.add_argument(
        "--summary",
        action="store_true",
        help="Print one readable line instead of JSON (used by student-workspace check)",
    )
    for name in ("build", "demo"):
        commands.add_parser(name)
    init = commands.add_parser("init")
    init.add_argument(
        "--with-abroad",
        action="store_true",
        help="Add missing optional study-abroad records",
    )
    context = commands.add_parser("context")
    context.add_argument(
        "--focus",
        choices=["overview", "record", "term", "winter", "abroad"],
        default="overview",
    )
    ingest = commands.add_parser("import-source")
    ingest.add_argument("file", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            result = initialize(args.workspace, with_abroad=args.with_abroad)
        elif args.command == "demo":
            result = demo(args.workspace)
        elif args.command == "import-source":
            result = import_source(args.workspace, args.file)
        else:
            workspace = Workspace(args.workspace)
            result = (
                workspace.context(args.focus)
                if args.command == "context"
                else getattr(workspace, args.command)()
            )
        if getattr(args, "summary", False):
            print(check_summary(result))
        else:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        return 2 if result.get("outputs_stale") else 0
    except (
        PlanningError,
        OSError,
        KeyError,
        TypeError,
        ValueError,
        yaml.YAMLError,
    ) as exc:
        print(f"Academic planning: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
