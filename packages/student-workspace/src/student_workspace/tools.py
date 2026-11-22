"""Tool registration, generated instructions and skill pointers."""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import shutil
import subprocess
import sysconfig
from importlib import metadata as importlib_metadata
from importlib.resources import files
from pathlib import Path, PurePosixPath
from typing import Any

from .state import (
    STATE_DIR,
    WorkspaceStateError,
    atomic_json,
    atomic_text,
    read_json,
    require_object,
    require_workspace,
)

MANIFEST_NAME = "student-workspace-tool.json"
MANIFEST_SCHEMA_VERSION = "1.0"
CORE_TOOL = "student-workspace"
POINTER_ROOTS = (".agents/skills", ".claude/skills")
GENERATED_STATE = f"{STATE_DIR}/generated.json"
_NAME = re.compile(r"[a-z][a-z0-9-]{0,63}")
_SKILL = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")
_BEGIN = "<!-- student-workspace:begin {name} -->"
_END = "<!-- student-workspace:end {name} -->"
ToolRow = tuple[dict[str, Any], Path, dict[str, Any] | None, str | None]
_BLOCK = re.compile(
    r"<!-- student-workspace:begin (?P<name>[a-z][a-z0-9-]*) -->\n.*?"
    r"<!-- student-workspace:end (?P=name) -->\n?",
    re.S,
)
WORKSPACE_HEADER = """# Student Workspace

Keep personal material in this workspace. Setup rewrites only the generated
blocks below; text you add outside them is preserved.

"""


def _portable(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise WorkspaceStateError(f"{label} must be a forward-slash relative path")
    path = PurePosixPath(value.rstrip("/"))
    if path.is_absolute() or any(part in {"", ".", ".."} or ":" in part for part in path.parts):
        raise WorkspaceStateError(f"{label} must stay inside its base folder: {value}")
    return value


def _command(value: Any, label: str) -> list[str] | None:
    if value is None:
        return None
    if not isinstance(value, list) or not value or not all(isinstance(part, str) and part for part in value):
        raise WorkspaceStateError(f"{label} must be a non-empty string array or null")
    return value


def load_manifest(tool_dir: Path) -> dict[str, Any]:
    """Read and validate a tool's `student-workspace-tool.json`."""
    path = Path(tool_dir) / MANIFEST_NAME
    try:
        manifest = require_object(json.loads(path.read_text(encoding="utf-8")), MANIFEST_NAME)
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkspaceStateError(f"could not read tool manifest {path}: {exc}") from exc
    if manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        raise WorkspaceStateError(f"{path}: schema_version must be {MANIFEST_SCHEMA_VERSION}")
    allowed = {
        "schema_version",
        "name",
        "display_name",
        "package",
        "owned_paths",
        "protected_paths",
        "sqlite_files",
        "check_command",
        "setup_command",
        "setup_options",
        "instructions",
        "skills",
    }
    if set(manifest) - allowed:
        raise WorkspaceStateError(f"{path}: unknown fields {sorted(set(manifest) - allowed)}")
    name = manifest.get("name")
    if not isinstance(name, str) or not _NAME.fullmatch(name):
        raise WorkspaceStateError(f"{path}: name must be lowercase letters, digits and hyphens")
    for key in ("display_name", "package"):
        if not isinstance(manifest.get(key), str) or not manifest[key].strip():
            raise WorkspaceStateError(f"{path}: {key} must be a non-empty string")
    for key in ("owned_paths", "protected_paths", "sqlite_files"):
        values = manifest.setdefault(key, [])
        if not isinstance(values, list):
            raise WorkspaceStateError(f"{path}: {key} must be an array")
        for index, value in enumerate(values):
            _portable(value, f"{key}[{index}]")
    manifest["check_command"] = _command(manifest.get("check_command"), "check_command")
    manifest["setup_command"] = _command(manifest.get("setup_command"), "setup_command")
    options = manifest.setdefault("setup_options", [])
    if not isinstance(options, list):
        raise WorkspaceStateError(f"{path}: setup_options must be an array")
    for index, option in enumerate(options):
        option = require_object(option, f"setup_options[{index}]")
        if (
            set(option) != {"name", "label", "args", "default"}
            or not isinstance(option["name"], str)
            or not _NAME.fullmatch(option["name"])
            or not isinstance(option["label"], str)
            or _command(option["args"], f"setup_options[{index}].args") is None
            or not isinstance(option["default"], bool)
        ):
            raise WorkspaceStateError(f"{path}: setup_options[{index}] needs name, label, args and default")
    instructions = manifest.setdefault("instructions", None)
    if instructions is not None:
        _portable(instructions, "instructions")
    skills = manifest.setdefault("skills", [])
    if not isinstance(skills, list) or not all(isinstance(s, str) and _SKILL.fullmatch(s) for s in skills):
        raise WorkspaceStateError(f"{path}: skills must be an array of skill folder names")
    return manifest


def scripts_dir() -> Path:
    return Path(sysconfig.get_path("scripts"))


def resolve_command(command: list[str], workspace: Path, extra: list[str] | None = None) -> list[str]:
    """Run a tool command from the same environment as student-workspace."""
    executable = command[0]
    suffix = ".exe" if os.name == "nt" else ""
    local = scripts_dir() / f"{executable}{suffix}"
    resolved = str(local) if local.is_file() else shutil.which(executable)
    if resolved is None:
        raise WorkspaceStateError(f"command not found in the tools environment: {executable}")
    arguments = [part.replace("{workspace}", str(workspace)) for part in command[1:]]
    return [resolved, *arguments, *(extra or [])]


def installed_version(package: str) -> str:
    try:
        return importlib_metadata.version(package)
    except importlib_metadata.PackageNotFoundError as exc:
        raise WorkspaceStateError(f"package {package} is not installed in this environment") from exc


def _tool_path(root: Path, record: dict[str, Any]) -> Path:
    path = Path(str(record.get("path", "")))
    return path if path.is_absolute() else root / path


def registered_tools(root: Path) -> list[ToolRow]:
    """Each registered tool as (record, folder, manifest or None, error or None)."""
    root, metadata = require_workspace(root)
    rows: list[ToolRow] = []
    for record in metadata.get("tools", []):
        folder = _tool_path(root, record)
        try:
            rows.append((record, folder, load_manifest(folder), None))
        except WorkspaceStateError as exc:
            rows.append((record, folder, None, str(exc)))
    return rows


def _write_metadata_tools(root: Path, tools: list[dict[str, Any]]) -> None:
    path = root / STATE_DIR / "workspace.json"
    metadata = read_json(path, {})
    metadata["tools"] = tools
    atomic_json(path, metadata)


def register_tool(
    root: Path,
    tool_dir: Path,
    *,
    options: tuple[str, ...] = (),
    run_setup: bool = True,
) -> dict[str, Any]:
    """Record a tool in workspace.json, run its setup hook and refresh instructions."""
    root, metadata = require_workspace(root)
    tool_dir = Path(tool_dir).resolve()
    manifest = load_manifest(tool_dir)
    version = installed_version(manifest["package"])
    known = {option["name"]: option for option in manifest["setup_options"]}
    unknown = set(options) - set(known)
    if unknown:
        raise WorkspaceStateError(f"unknown setup options for {manifest['name']}: {sorted(unknown)}")
    try:
        stored = tool_dir.relative_to(root).as_posix()
    except ValueError:
        stored = str(tool_dir)
    record = {"name": manifest["name"], "version": version, "path": stored, "options": sorted(options)}
    tools = [item for item in metadata.get("tools", []) if item.get("name") != manifest["name"]]
    tools.append(record)
    tools.sort(key=lambda item: (item.get("name") != CORE_TOOL, str(item.get("name"))))
    _write_metadata_tools(root, tools)
    setup: dict[str, Any] | None = None
    if run_setup and manifest["setup_command"]:
        extra = [arg for name in options for arg in known[name]["args"]]
        command = resolve_command(manifest["setup_command"], root, extra)
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        setup = {"exit_code": completed.returncode, "output": (completed.stdout + completed.stderr).strip()}
        if completed.returncode != 0:
            raise WorkspaceStateError(f"{manifest['name']} setup failed: {setup['output'][-2000:]}")
    refresh = refresh_workspace(root)
    return {"tool": record, "setup": setup, **refresh}


def unregister_tool(root: Path, name: str) -> dict[str, Any]:
    root, metadata = require_workspace(root)
    tools = [item for item in metadata.get("tools", []) if item.get("name") != name]
    if len(tools) == len(metadata.get("tools", [])):
        raise WorkspaceStateError(f"tool is not registered: {name}")
    _write_metadata_tools(root, tools)
    return refresh_workspace(root)


def _core_section() -> str:
    return files("student_workspace").joinpath("workspace-section.md").read_text(encoding="utf-8")


def _tools_section(root: Path, rows: list[ToolRow]) -> str:
    lines = ["## Installed tools", ""]
    for record, folder, manifest, error in rows:
        try:
            shown = folder.relative_to(root).as_posix()
        except ValueError:
            shown = str(folder)
        if manifest is None:
            lines.append(f"- `{record.get('name')}` in `{shown}`: manifest unreadable ({error}).")
            continue
        detail = f"- **{manifest['display_name']}** {record.get('version')} in `{shown}/`."
        if manifest["check_command"]:
            detail += f" Check: `{' '.join(manifest['check_command'])}`."
        if manifest["owned_paths"]:
            detail += " Owns " + ", ".join(f"`{p}`" for p in manifest["owned_paths"]) + "."
        if manifest["protected_paths"]:
            detail += (
                " Ask before changing its "
                + ", ".join(f"`{shown}/{p}`" for p in manifest["protected_paths"])
                + "."
            )
        lines.append(detail)
    return "\n".join(lines) + "\n"


def instruction_blocks(root: Path) -> dict[str, str]:
    """Generated WORKSPACE.md blocks in display order."""
    rows = registered_tools(root)
    blocks = {CORE_TOOL: _core_section().rstrip("\n") + "\n\n" + _tools_section(root, rows)}
    for record, folder, manifest, _error in rows:
        if manifest is None or manifest["name"] == CORE_TOOL or not manifest["instructions"]:
            continue
        path = folder / manifest["instructions"]
        try:
            blocks[manifest["name"]] = path.read_text(encoding="utf-8").rstrip("\n") + "\n"
        except OSError as exc:
            raise WorkspaceStateError(f"could not read instructions for {record.get('name')}: {exc}") from exc
    return blocks


def render_workspace_md(existing: str | None, blocks: dict[str, str]) -> str:
    """Replace generated blocks in place, append new ones, drop retired ones."""
    text = existing if existing is not None else WORKSPACE_HEADER
    present: set[str] = set()

    def replace(match: re.Match[str]) -> str:
        name = match["name"]
        present.add(name)
        if name not in blocks:
            return ""
        return f"{_BEGIN.format(name=name)}\n{blocks[name]}{_END.format(name=name)}\n"

    text = _BLOCK.sub(replace, text)
    for name, body in blocks.items():
        if name not in present:
            if text and not text.endswith("\n\n"):
                text = text.rstrip("\n") + "\n\n"
            text += f"{_BEGIN.format(name=name)}\n{body}{_END.format(name=name)}\n"
    return text


def _frontmatter(path: Path) -> tuple[str, str]:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"---\n(.*?)\n---\n", text.replace("\r\n", "\n"), re.S)
    if not match:
        raise WorkspaceStateError(f"skill has no frontmatter: {path}")
    fields = dict(re.findall(r"^([a-z_]+):\s*(.*)$", match[1], re.M))
    name, description = fields.get("name", "").strip(), fields.get("description", "").strip()
    if not name or not description:
        raise WorkspaceStateError(f"skill frontmatter needs name and description: {path}")
    return name, description


def _pointer(root: Path, target: Path, name: str, description: str) -> str:
    try:
        link = "../../../" + target.relative_to(root).as_posix()
    except ValueError:
        link = target.as_posix()
    return (
        f"---\nname: {name}\ndescription: {description}\n---\n\n"
        f"Read and follow [the maintained skill]({link}). Resolve its links relative to that file. "
        "Where it gives separate Codex and Claude Code instructions, use the ones for your agent.\n\n"
        "Setup generates this discovery entry. Change the skill in its tool folder, not here.\n"
    )


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def refresh_workspace(root: Path, *, create_instructions: bool = True) -> dict[str, Any]:
    """Regenerate WORKSPACE.md blocks and skill pointers from registered tools."""
    root, _metadata = require_workspace(root)
    created: list[str] = []
    updated: list[str] = []
    warnings: list[str] = []

    workspace_md = root / "WORKSPACE.md"
    blocks = instruction_blocks(root)
    if workspace_md.exists():
        existing = workspace_md.read_text(encoding="utf-8")
        if _BLOCK.search(existing) is None:
            warnings.append(
                "WORKSPACE.md has no generated blocks and was left unchanged; "
                "`student-workspace instructions` prints the current blocks"
            )
        else:
            rendered = render_workspace_md(existing, blocks)
            if rendered != existing:
                atomic_text(workspace_md, rendered)
                updated.append("WORKSPACE.md")
    elif create_instructions:
        atomic_text(workspace_md, render_workspace_md(None, blocks))
        created.append("WORKSPACE.md")

    state_path = root / GENERATED_STATE
    state = read_json(state_path, {"schema_version": "1.0", "files": {}})
    previous: dict[str, str] = dict(require_object(state.get("files", {}), "generated files"))
    current: dict[str, str] = {}
    for _record, folder, manifest, error in registered_tools(root):
        if manifest is None:
            warnings.append(f"skipped skills for an unreadable tool manifest: {error}")
            continue
        for skill in manifest["skills"]:
            target = folder / "skills" / skill / "SKILL.md"
            if not target.is_file():
                warnings.append(f"{manifest['name']} lists missing skill {skill}")
                continue
            name, description = _frontmatter(target)
            content = _pointer(root, target, name, description)
            for base in POINTER_ROOTS:
                relative = f"{base}/{skill}/SKILL.md"
                path = root / base / skill / "SKILL.md"
                if relative in current:
                    warnings.append(f"two tools provide skill {skill}; kept the first")
                    continue
                if path.exists():
                    existing_text = path.read_text(encoding="utf-8")
                    if previous.get(relative) != _sha(existing_text):
                        if existing_text != content:
                            warnings.append(f"{relative} is not a generated pointer; left unchanged")
                        continue
                    if existing_text == content:
                        current[relative] = _sha(content)
                        continue
                    updated.append(relative)
                else:
                    created.append(relative)
                atomic_text(path, content)
                current[relative] = _sha(content)
    for relative, digest in previous.items():
        if relative in current:
            continue
        path = root / relative
        if path.is_file() and _sha(path.read_text(encoding="utf-8")) == digest:
            path.unlink()
            with contextlib.suppress(OSError):
                path.parent.rmdir()
            updated.append(relative)
    atomic_json(state_path, {"schema_version": "1.0", "files": dict(sorted(current.items()))})
    return {"created": created, "updated": updated, "warnings": warnings}
