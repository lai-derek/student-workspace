"""student-workspace command-line interface."""

from __future__ import annotations

import argparse
import contextlib
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from . import __version__
from .application_checks import check_application_request
from .applications import ARTIFACT_TYPES, create_application_request, list_application_requests, url_target
from .check import check_workspace
from .recovery import (
    audit_workspace,
    backup_workspace,
    compare_knowledge_snapshot,
    list_knowledge_snapshots,
    restore_knowledge_snapshot,
    restore_workspace_backup,
)
from .sources import import_source, register_source
from .state import WorkspaceStateError
from .tools import instruction_blocks, refresh_workspace, register_tool, unregister_tool
from .workspace import WorkspaceInitError, initialize_workspace


def _emit(args: argparse.Namespace, payload: Any, lines: list[str]) -> None:
    if args.json_output:
        print(json.dumps(payload, indent=2))
    elif not args.quiet:
        for line in lines:
            print(line)


def _warnings(warnings: list[str]) -> None:
    for warning in warnings:
        print(f"WARNING {warning}", file=sys.stderr)


def cmd_init(args: argparse.Namespace) -> int:
    result = initialize_workspace(Path(args.workspace))
    _emit(
        args,
        result.to_dict(),
        [
            f"workspace ready at {result.root}",
            f"created {len(result.created_files)} files; updated {len(result.updated_files)}; "
            f"preserved {len(result.preserved_files)}",
        ],
    )
    _warnings(list(result.warnings))
    return 0


def cmd_register(args: argparse.Namespace) -> int:
    result = register_tool(
        Path(args.workspace), Path(args.tool), options=tuple(args.option), run_setup=not args.no_setup
    )
    tool = result["tool"]
    _emit(args, result, [f"registered {tool['name']} {tool['version']} from {tool['path']}"])
    _warnings(result["warnings"])
    return 0


def cmd_unregister(args: argparse.Namespace) -> int:
    result = unregister_tool(Path(args.workspace), args.name)
    _emit(args, result, [f"unregistered {args.name}; its files and data were left in place"])
    _warnings(result["warnings"])
    return 0


def cmd_refresh(args: argparse.Namespace) -> int:
    result = refresh_workspace(Path(args.workspace))
    _emit(args, result, [f"created {len(result['created'])}; updated {len(result['updated'])}"])
    _warnings(result["warnings"])
    return 0


def cmd_instructions(args: argparse.Namespace) -> int:
    blocks = instruction_blocks(Path(args.workspace))
    if args.json_output:
        print(json.dumps(blocks, indent=2))
    else:
        for name, body in blocks.items():
            print(f"<!-- student-workspace:begin {name} -->\n{body}<!-- student-workspace:end {name} -->\n")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    report = check_workspace(Path(args.workspace))
    lines = [f"workspace check: {report['status']}"]
    for item in report["results"]:
        label = {0: "ok", 1: "error", 2: "stale"}[item["status"]]
        version = f" {item['version']}" if item.get("version") else ""
        lines.append(f"  [{label}] {item['name']}{version}")
        lines.extend(f"      {line}" for line in item["detail"])
    _emit(args, report, lines)
    return int(report["exit_code"])


def cmd_source_import(args: argparse.Namespace) -> int:
    result = import_source(Path(args.workspace), Path(args.file), folder=args.folder)
    _emit(args, result, [("reused " if result["reused"] else "saved ") + result["stored_path"]])
    return 0


def cmd_source_register(args: argparse.Namespace) -> int:
    result = register_source(Path(args.workspace), args.stored_path, original_name=args.original_name)
    _emit(
        args, result, [("already registered " if result["reused"] else "registered ") + result["stored_path"]]
    )
    return 0


def cmd_backup(args: argparse.Namespace) -> int:
    result = backup_workspace(Path(args.workspace), Path(args.output), kind=args.kind)
    _emit(
        args,
        result.to_dict(),
        [f"created {result.kind} backup with {result.file_count} files -> {result.path}"],
    )
    _warnings([result.warning])
    return 0


def cmd_restore(args: argparse.Namespace) -> int:
    result = restore_workspace_backup(
        Path(args.workspace),
        Path(args.archive),
        pre_restore_path=Path(args.pre_restore_output) if args.pre_restore_output else None,
    )
    _emit(
        args,
        result.to_dict(),
        [
            f"restored {result.restored_files} files from {result.archive}",
            f"pre-restore backup: {result.pre_restore_backup}",
        ],
    )
    return 0


def cmd_snapshot(args: argparse.Namespace) -> int:
    root = Path(args.workspace)
    if args.snapshot_command == "list":
        snapshots = list_knowledge_snapshots(root)
        _emit(
            args,
            {"schema_version": "1.0", "snapshots": [item.to_dict() for item in snapshots]},
            [f"{item.snapshot_id}  {item.created_at}  {len(item.files)} files" for item in snapshots]
            or ["No snapshots yet. Tools save one before they change generated knowledge."],
        )
    elif args.snapshot_command == "compare":
        result = compare_knowledge_snapshot(root, args.snapshot_id)
        _emit(
            args,
            result,
            [f"snapshot {args.snapshot_id}: {len(result['changes'])} changed paths"]
            + [f"  {change['change']}: {change['path']}" for change in result["changes"]],
        )
    else:
        result = restore_knowledge_snapshot(root, args.snapshot_id)
        _emit(
            args,
            result,
            [
                f"restored {len(result['restored_files'])} files from {args.snapshot_id}",
                f"pre-restore snapshot: {result['pre_restore_snapshot_id']}",
            ],
        )
    return 0


def cmd_audit(args: argparse.Namespace) -> int:
    report = audit_workspace(Path(args.workspace))
    _emit(
        args,
        report.to_dict(),
        [
            f"workspace audit: {len(report.errors)} errors, "
            f"{len(report.findings) - len(report.errors)} warnings"
        ]
        + [f"  [{f.severity}] {f.rule}: {f.path} {f.detail}" for f in report.findings],
    )
    return 1 if report.errors else 0


def cmd_apply(args: argparse.Namespace) -> int:
    root = Path(args.workspace)
    if args.apply_command == "request-url":
        result = create_application_request(
            root,
            url_target(args.target_url),
            args.artifact_type,
            args.request_text,
            application_folder=args.application_folder,
            references=tuple(args.reference),
        )
        _emit(
            args,
            result,
            [
                f"request created: {result['request_path']}",
                "Open HANDOFF.md in that folder with your chosen agent to prepare the artifact.",
            ],
        )
        return 0
    if args.apply_command == "list":
        rows = list_application_requests(root, args.application_folder)
        _emit(
            args,
            rows,
            [f"{row['request_id']}  {row['artifact_type']}  {row['response_status']}" for row in rows],
        )
        return 0
    result = check_application_request(root, args.request_path)
    lines = [
        f"application check: {len(result['errors'])} errors, "
        f"{len(result['warnings'])} warnings; {result['response_status']}"
    ]
    lines += [f"[{level[:-1]}] {message}" for level in ("errors", "warnings") for message in result[level]]
    lines += [
        f"{field['path']}: {field['words']} words, {field['characters']} characters"
        for field in result["fields"]
    ]
    _emit(args, result, lines)
    return 0 if result["valid"] else 1


def cmd_update(args: argparse.Namespace) -> int:
    from . import installer

    options: dict[str, list[str]] = {}
    for value in args.option:
        tool, separator, option = value.partition(":")
        if not separator or not option:
            raise WorkspaceStateError("--option takes TOOL:OPTION")
        options.setdefault(tool, []).append(option)
    try:
        release = installer.load_release(args.release)
        if not args.reinstall and installer.already_current(Path(args.workspace), release, set(args.add)):
            _emit(
                args,
                {"schema_version": "1.0", "release": release.get("release"), "changed": False},
                [
                    f"Already current with release {release.get('release')}; nothing to install.",
                    "Use --reinstall to reinstall the same versions (for example to repair tools/).",
                ],
            )
            return 0
        result = installer.install(
            Path(args.workspace),
            release,
            set(args.add),
            options=options,
            progress=None
            if args.quiet or args.json_output
            else lambda _f, message: print(message, flush=True),
        )
    except installer.InstallError as exc:
        print(f"ERROR update stopped: {exc}", file=sys.stderr)
        return 1
    _emit(
        args,
        result,
        [f"{row['action']}: {row['name']} {row['version']}" for row in result["tools"]]
        + [f"backup: {result['backup']}", f"check exit code: {result['check_exit_code']}"],
    )
    return 0


def cmd_resume(args: argparse.Namespace) -> int:
    """Application Studio from the command line (for scripts and AI agents)."""
    from .studio import ats, export, handoff, importer
    from .studio.render import Renderer
    from .studio.store import Studio

    root = Path(args.workspace)
    with Studio(root) as studio:
        action = args.resume_command
        if action == "list":
            rows = studio.resumes()
            lines = [
                f"{r['application_folder']}: " + ", ".join(f"{v['name']} ({v['id']})" for v in r["versions"])
                for r in rows
            ] or ["no resumes yet"]
            _emit(args, rows, lines)
        elif action == "import-tex":
            text = Path(args.tex_file).read_text(encoding="utf-8")
            result = importer.import_resume(studio, args.application_folder, text, template=args.template)
            _emit(
                args,
                result,
                [
                    f"imported version {result['version_id']}: {result['sections']} sections, "
                    f"{result['bullets']} bullets, {result['skills']} skill lines"
                ],
            )
        elif action == "import-evidence":
            ids = importer.import_evidence_matrix(studio, Path(args.matrix))
            _emit(args, {"evidence_ids": ids}, [f"imported {len(ids)} evidence notes"])
        elif action == "show":
            version = studio.version(args.version_id)
            lines = [f"{version['name']} ({version['template']}) for {version['application_folder']}"]
            for section in version["sections"]:
                lines.append(
                    f"## {section['title']}{' (hidden)' if section['hidden'] else ''}  [{section['id']}]"
                )
                for entry in section["entries"]:
                    lines.append(
                        f"- {entry['title']}{' (hidden)' if entry['hidden'] else ''}  [{entry['id']}]"
                    )
                    for bullet in entry["bullets"]:
                        mark = " (hidden)" if bullet["hidden"] else ""
                        lines.append(f"    * {bullet['text']}{mark}  [{bullet['id']}]")
            _emit(args, version, lines)
        elif action == "export":
            result = export.export_version(studio, args.version_id, replace_outside_edits=args.replace)
            _emit(args, result, [f"wrote {result['source_path']} and {result['pdf_path']}"])
        elif action == "verify":
            ok = export.verify_export(studio, args.version_id)
            state = export.export_state(studio, args.version_id)
            _emit(
                args,
                {"matches": ok, **state},
                [
                    f"{state['pdf_path']}: "
                    + ("matches its source" if ok else f"does not match ({state['state']})")
                ],
            )
            return 0 if ok else 1
        elif action == "check":
            version = studio.version(args.version_id)
            data = studio.render_data(args.version_id)
            rendered = Renderer().render(data, version["template"])
            report = ats.parse_check(rendered.pdf, data, margin_in=data["settings"]["margin"])
            coverage = ats.keyword_coverage(
                version["posting_text"], report["extracted_text"], studio.evidence()
            )
            report.pop("extracted_text")
            lines = [f"[{f['level']}] {f['message']}" for f in report["findings"]]
            if coverage["terms"]:
                lines.append(f"posting terms covered: {coverage['covered']} of {len(coverage['terms'])}")
            _emit(args, {"parse": report, "keywords": coverage}, lines)
            return 1 if report["result"] == "error" else 0
        elif action == "ask-ai":
            result = handoff.ask_ai(studio, args.version_id, args.section_id, args.request_text)
            _emit(args, result, [f"created {result['request_path']}; give its HANDOFF.md to your AI agent"])
        elif action == "import-variants":
            result = handoff.import_variants(studio, args.request_path)
            _emit(args, result, [f"imported {result['added']} variants; skipped {len(result['skipped'])}"])
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    # Imported here so the other commands don't pay for loading the web stack.
    from .web.serve import serve

    with contextlib.suppress(KeyboardInterrupt):  # Ctrl+C is the normal way to stop it
        serve(
            Path(args.workspace),
            port=args.port,
            open_browser=not args.no_browser,
            dev_origins=tuple(args.dev_origin),
        )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="student-workspace",
        description="Shared setup, state and recovery for a private student workspace.",
    )
    parser.add_argument("--version", action="version", version=f"student-workspace {__version__}")
    parser.add_argument("--quiet", "-q", action="store_true", help="suppress normal output")
    parser.add_argument(
        "--json", dest="json_output", action="store_true", help="machine-readable JSON output"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def add(
        name: str, function: Callable[[argparse.Namespace], int], help_text: str
    ) -> argparse.ArgumentParser:
        command = sub.add_parser(name, help=help_text)
        command.set_defaults(func=function)
        command.add_argument("workspace", help="private workspace root")
        return command

    add("init", cmd_init, "create or repair the workspace folders and starter files")
    p = add("register", cmd_register, "register an installed tool folder and run its setup")
    p.add_argument("tool", help="tool folder containing student-workspace-tool.json")
    p.add_argument("--option", action="append", default=[], help="setup option named by the tool manifest")
    p.add_argument("--no-setup", action="store_true", help="record the tool without running its setup")
    p = add("unregister", cmd_unregister, "remove a tool from the workspace registry")
    p.add_argument("name")
    add("refresh", cmd_refresh, "regenerate WORKSPACE.md blocks and skill pointers")
    add("instructions", cmd_instructions, "print the generated WORKSPACE.md blocks")
    add("check", cmd_check, "check the workspace and every tool (0 current, 2 stale, 1 error)")
    source = sub.add_parser("source", help="preserve and register evidence below sources/")
    source_sub = source.add_subparsers(dest="source_command", required=True)
    p = source_sub.add_parser("import", help="copy a file unchanged into sources/FOLDER and register it")
    p.set_defaults(func=cmd_source_import)
    p.add_argument("workspace")
    p.add_argument("file")
    p.add_argument("--folder", required=True, help="one folder name below sources/")
    p = source_sub.add_parser("register", help="register a file already saved below sources/")
    p.set_defaults(func=cmd_source_register)
    p.add_argument("workspace")
    p.add_argument("stored_path", help="workspace-relative path below sources/")
    p.add_argument("--original-name")
    p = add("backup", cmd_backup, "create an unencrypted workspace ZIP")
    p.add_argument("output", help="backup ZIP destination")
    p.add_argument("--kind", choices=("full", "state"), default="full")
    p = add("restore", cmd_restore, "restore a verified workspace ZIP")
    p.add_argument("archive")
    p.add_argument("--pre-restore-output", help="path for the automatic full pre-restore backup")
    snapshot = sub.add_parser("snapshot", help="knowledge snapshots taken before tool changes")
    snapshot_sub = snapshot.add_subparsers(dest="snapshot_command", required=True)
    for name, help_text in (
        ("list", "list knowledge snapshots"),
        ("compare", "compare current knowledge with a snapshot"),
        ("restore", "restore a snapshot after snapshotting the current state"),
    ):
        p = snapshot_sub.add_parser(name, help=help_text)
        p.set_defaults(func=cmd_snapshot)
        p.add_argument("workspace")
        if name != "list":
            p.add_argument("snapshot_id")
    add("audit", cmd_audit, "audit workspace exposure and references without changes")
    apply = sub.add_parser("apply", help="manual application handoffs")
    apply_sub = apply.add_subparsers(dest="apply_command", required=True)
    p = apply_sub.add_parser("request-url", help="create a handoff for a user-supplied application URL")
    p.set_defaults(func=cmd_apply)
    p.add_argument("workspace")
    p.add_argument("application_folder", help="workspace-relative path below applications/")
    p.add_argument("target_url", help="HTTP(S) application URL; not fetched")
    p.add_argument("artifact_type", choices=ARTIFACT_TYPES)
    p.add_argument("request_text", help="what the chosen agent should prepare")
    p.add_argument(
        "--reference", action="append", default=[], metavar="PATH", help="sources/ or knowledge/ path"
    )
    p = apply_sub.add_parser("list", help="list recent handoffs in an application folder")
    p.set_defaults(func=cmd_apply)
    p.add_argument("workspace")
    p.add_argument("application_folder")
    p = apply_sub.add_parser("check", help="check a handoff without changing it")
    p.set_defaults(func=cmd_apply)
    p.add_argument("workspace")
    p.add_argument("request_path", help="applications/.../requests/req_... folder")
    resume = sub.add_parser("resume", help="Application Studio: resumes as data, typeset with Typst")
    resume_sub = resume.add_subparsers(dest="resume_command", required=True)

    def resume_cmd(name: str, help_text: str, *extra: str) -> argparse.ArgumentParser:
        command = resume_sub.add_parser(name, help=help_text)
        command.set_defaults(func=cmd_resume)
        command.add_argument("workspace")
        for argument in extra:
            command.add_argument(argument)
        return command

    resume_cmd("list", "list resumes and their versions")
    p = resume_cmd(
        "import-tex", "create a resume from a Jake's-style LaTeX file", "application_folder", "tex_file"
    )
    p.add_argument("--template", choices=("jake", "classic", "modern"), default="jake")
    resume_cmd("import-evidence", "add an evidence-matrix.md table's rows as evidence notes", "matrix")
    resume_cmd("show", "print a version with its ids", "version_id")
    p = resume_cmd("export", "write resume-YYYY-MM-DD.typ and .pdf into the application folder", "version_id")
    p.add_argument("--replace", action="store_true", help="overwrite files changed outside the studio")
    resume_cmd("verify", "recompile the exported source and compare it with the exported PDF", "version_id")
    resume_cmd("check", "resume screening checks (parse check and posting keywords)", "version_id")
    resume_cmd(
        "ask-ai",
        "create a handoff asking your AI for variants of one section",
        "version_id",
        "section_id",
        "request_text",
    )
    resume_cmd("import-variants", "store the variants from an answered studio handoff", "request_path")
    p = add("serve", cmd_serve, "open the Student Workspace app in the browser (runs until stopped)")
    p.add_argument("--port", type=int, default=0, help="port on 127.0.0.1 (default: any free port)")
    p.add_argument("--no-browser", action="store_true", help="print the link instead of opening it")
    p.add_argument(
        "--dev-origin",
        action="append",
        default=[],
        metavar="URL",
        help="also accept this origin, e.g. http://localhost:5173 for the Vite dev server",
    )
    p = add("update", cmd_update, "install the latest tested release into tools/ (backs up first)")
    p.add_argument("--release", default=None, help="release.json path or URL (default: latest release)")
    p.add_argument("--add", action="append", default=[], metavar="TOOL", help="also install this tool")
    p.add_argument("--option", action="append", default=[], metavar="TOOL:OPTION")
    p.add_argument(
        "--reinstall", action="store_true", help="reinstall even when everything is already current"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if getattr(args, "release", "") is None:
        from .installer import RELEASE_URL

        args.release = RELEASE_URL
    try:
        return int(args.func(args))
    except (OSError, WorkspaceStateError, WorkspaceInitError) as exc:
        print(f"ERROR {args.command}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
