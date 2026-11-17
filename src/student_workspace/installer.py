"""Install and update core shared by the setup wizard and `student-workspace update`.

Standard library only: the wizard loads this file directly, before any package
is installed. It downloads the tested versions listed in release.json into
`tools/<name>/`, installs them into `tools/.venv`, registers them, and puts the
previous `tools/` back if anything fails.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import urllib.request
import zipfile
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

RELEASE_URL = "https://github.com/lai-derek/student-workspace/releases/latest/download/release.json"
CORE = "student-workspace"
STATE_DIR = ".student-workspace"
MANIFEST_NAME = "student-workspace-tool.json"
USER_AGENT = "student-workspace-installer"
Progress = Callable[[float, str], None]


class InstallError(RuntimeError):
    """Installation stopped; the message says what to do next."""


def _now_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _read_bytes(source: str | Path) -> bytes:
    text = str(source)
    if "://" in text or text.startswith("file:"):
        request = urllib.request.Request(text, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=60) as response:
            return bytes(response.read())
    return Path(text).read_bytes()


def load_release(source: str | Path) -> dict[str, Any]:
    """Read and validate release.json from a path or URL."""
    try:
        release = json.loads(_read_bytes(source).decode("utf-8"))
    except (OSError, ValueError) as exc:
        raise InstallError(f"could not read release information from {source}: {exc}") from exc
    if not isinstance(release, dict) or release.get("schema_version") != "1.0":
        raise InstallError("release.json must be a schema 1.0 object")
    tools = release.get("tools")
    if not isinstance(tools, list) or not tools:
        raise InstallError("release.json lists no tools")
    names = []
    for entry in tools:
        if not isinstance(entry, dict) or not all(
            isinstance(entry.get(key), str) and entry[key]
            for key in ("name", "display_name", "version", "archive", "sha256")
        ):
            raise InstallError("each release tool needs name, display_name, version, archive and sha256")
        if not re.fullmatch(r"[0-9a-f]{64}", entry["sha256"]):
            raise InstallError(f"{entry['name']} has an invalid sha256 in release.json")
        names.append(entry["name"])
    if CORE not in names or len(set(names)) != len(names):
        raise InstallError("release.json must list student-workspace once and each tool once")
    return release


def release_tool(release: dict[str, Any], name: str) -> dict[str, Any]:
    for entry in release["tools"]:
        if entry["name"] == name:
            return dict(entry)
    raise InstallError(f"this release does not include {name}")


def installed_tools(workspace: Path) -> dict[str, dict[str, Any]]:
    """Registered tools by name, from workspace.json; empty for a new folder."""
    path = Path(workspace) / STATE_DIR / "workspace.json"
    if not path.is_file():
        return {}
    try:
        metadata = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise InstallError(f"could not read {path}: {exc}") from exc
    tools = metadata.get("tools", []) if isinstance(metadata, dict) else []
    return {str(item["name"]): item for item in tools if isinstance(item, dict) and "name" in item}


def inside_git_checkout(path: Path) -> Path | None:
    path = Path(path).expanduser().resolve()
    for candidate in (path, *path.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def plan(workspace: Path, release: dict[str, Any], chosen: set[str]) -> list[dict[str, Any]]:
    """What an install of `chosen` tools does: core and installed tools are always kept current."""
    current = installed_tools(workspace)
    wanted = {CORE, *current, *chosen}
    rows = []
    for entry in release["tools"]:
        if entry["name"] not in wanted:
            continue
        before = current.get(entry["name"], {}).get("version")
        action = "install" if before is None else ("keep" if before == entry["version"] else "update")
        rows.append({**entry, "installed_version": before, "action": action})
    missing = wanted - {row["name"] for row in rows}
    if missing:
        raise InstallError(f"this release does not include installed tools: {sorted(missing)}")
    return rows


def _venv_bin(venv: Path, command: str) -> Path:
    if os.name == "nt":
        return venv / "Scripts" / f"{command}.exe"
    return venv / "bin" / command


def _remove_tree(path: Path) -> None:
    def retry(function: Callable[..., Any], target: str, _excinfo: Any) -> None:
        os.chmod(target, stat.S_IWRITE)
        function(target)

    if path.exists():
        shutil.rmtree(path, onexc=retry)


def _extract(archive: Path, destination: Path) -> None:
    """Extract a tagged source ZIP, dropping its single top-level folder."""
    with zipfile.ZipFile(archive) as bundle:
        names = [info.filename for info in bundle.infolist()]
        tops = {PurePosixPath(name).parts[0] for name in names if name.strip("/")}
        if len(tops) != 1:
            raise InstallError(f"{archive.name} should contain exactly one top-level folder")
        for info in bundle.infolist():
            parts = PurePosixPath(info.filename).parts
            if "\\" in info.filename or PurePosixPath(info.filename).is_absolute() or ".." in parts:
                raise InstallError(f"{archive.name} contains an unsafe path: {info.filename}")
            relative = parts[1:]
            if not relative:
                continue
            target = destination.joinpath(*relative)
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with bundle.open(info) as source, open(target, "wb") as handle:
                shutil.copyfileobj(source, handle)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _download(entry: dict[str, Any], staging: Path) -> Path:
    archive = staging / f"{entry['name']}-{entry['version']}.zip"
    try:
        archive.write_bytes(_read_bytes(entry["archive"]))
    except OSError as exc:
        raise InstallError(f"could not download {entry['display_name']} {entry['version']}: {exc}") from exc
    if _sha256(archive) != entry["sha256"]:
        raise InstallError(f"{entry['display_name']} download does not match the release checksum")
    folder = staging / entry["name"]
    _extract(archive, folder)
    manifest_path = folder / MANIFEST_NAME
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise InstallError(f"{entry['display_name']} download has no readable {MANIFEST_NAME}") from exc
    if manifest.get("name") != entry["name"]:
        raise InstallError(f"{entry['archive']} is not {entry['name']}")
    return folder


class _Log:
    def __init__(self, path: Path, progress: Progress | None) -> None:
        self.path = path
        self.progress = progress
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"student-workspace install {_now_stamp()}\n", encoding="utf-8")

    def write(self, text: str) -> None:
        with open(self.path, "a", encoding="utf-8") as handle:
            handle.write(text.rstrip("\n") + "\n")

    def step(self, fraction: float, message: str) -> None:
        self.write(f"== {message}")
        if self.progress:
            self.progress(fraction, message)

    def run(self, command: list[str], *, cwd: Path | None = None, allowed: tuple[int, ...] = (0,)) -> int:
        self.write("$ " + " ".join(command))
        completed = subprocess.run(
            command, cwd=cwd, capture_output=True, text=True, check=False, encoding="utf-8", errors="replace"
        )
        self.write(completed.stdout + completed.stderr)
        if completed.returncode not in allowed:
            tail = (completed.stdout + completed.stderr).strip().splitlines()[-15:]
            raise InstallError(
                f"{Path(command[0]).name} {' '.join(command[1:3])} failed (exit {completed.returncode}):\n"
                + "\n".join(tail)
                + f"\nFull log: {self.path}"
            )
        return completed.returncode


def _clean_leftovers(tools: Path) -> None:
    # A process from a previous environment may still hold files; the next run retries.
    for leftover in [*tools.glob(".previous-*"), *tools.glob(".staging-*")]:
        with contextlib.suppress(OSError):
            _remove_tree(leftover)


def install(
    workspace: Path,
    release: dict[str, Any],
    chosen: set[str],
    *,
    options: dict[str, list[str]] | None = None,
    python: str | None = None,
    progress: Progress | None = None,
) -> dict[str, Any]:
    """Install or update the tested set; restore the previous tools/ on failure."""
    workspace = Path(workspace).expanduser().resolve()
    if workspace.exists() and not workspace.is_dir():
        raise InstallError(f"{workspace} is a file, not a folder")
    rows = plan(workspace, release, chosen)
    current = installed_tools(workspace)
    tools = workspace / "tools"
    for row in rows:
        if row["action"] != "keep" and (tools / row["name"] / ".git").exists():
            raise InstallError(
                f"tools/{row['name']} is a Git checkout; update it with Git and pip instead of the installer"
            )
    tools.mkdir(parents=True, exist_ok=True)
    (workspace / STATE_DIR).mkdir(parents=True, exist_ok=True)
    log = _Log(workspace / STATE_DIR / "install.log", progress)
    _clean_leftovers(tools)
    venv = tools / ".venv"
    stamp = _now_stamp()
    staging = tools / f".staging-{stamp}"
    previous = tools / f".previous-{stamp}"
    interpreter = python or str(getattr(sys, "_base_executable", sys.executable))

    backup: Path | None = None
    if current:
        log.step(0.05, "Backing up the workspace")
        backup_cli = _venv_bin(venv, CORE)
        if not backup_cli.is_file():
            raise InstallError(
                f"{backup_cli} is missing, so the workspace cannot be backed up; nothing was changed"
            )
        backup = workspace / STATE_DIR / "backups" / f"pre-update-{stamp}.zip"
        log.run([str(backup_cli), "backup", str(workspace), str(backup), "--kind", "full"])

    staging.mkdir()
    fetched: dict[str, Path] = {}
    try:
        for index, row in enumerate(rows):
            log.step(0.1 + 0.3 * index / len(rows), f"Downloading {row['display_name']} {row['version']}")
            fetched[row["name"]] = _download(row, staging)
    except Exception:
        _remove_tree(staging)
        raise

    moved: list[tuple[Path, Path]] = []
    placed: list[Path] = []
    saved_files = _snapshot_generated(workspace)
    venv_replaced = False
    try:
        log.step(0.42, "Setting the previous tools aside")
        previous.mkdir()
        for name, folder in fetched.items():
            target = tools / name
            if target.exists():
                os.replace(target, previous / name)
                moved.append((previous / name, target))
            os.replace(folder, target)
            placed.append(target)
        if venv.exists():
            os.replace(venv, previous / ".venv")
            moved.append((previous / ".venv", venv))
        venv_replaced = True

        log.step(0.5, "Creating the tools environment")
        log.run([interpreter, "-m", "venv", str(venv)])
        venv_python = _venv_bin(venv, "python")
        log.step(0.6, "Installing packages")
        ordered = [tools / row["name"] for row in rows]
        log.run([str(venv_python), "-m", "pip", "install", "--disable-pip-version-check", *map(str, ordered)])

        log.step(0.8, "Registering tools")
        cli = str(_venv_bin(venv, CORE))
        log.run([cli, "init", str(workspace)])
        for row in rows:
            recorded = current.get(row["name"], {}).get("options")
            chosen_options = (options or {}).get(row["name"], recorded if isinstance(recorded, list) else [])
            command = [cli, "register", str(workspace), str(tools / row["name"])]
            for option in chosen_options:
                command += ["--option", option]
            log.run(command)
    except BaseException as exc:
        log.write(f"!! {exc}; restoring the previous tools")
        _rollback(workspace, venv if venv_replaced else None, placed, moved, saved_files)
        _remove_tree(staging)
        if isinstance(exc, InstallError):
            raise
        raise InstallError(f"installation failed and the previous tools were restored: {exc}") from exc

    log.step(0.92, "Checking the workspace")
    check_code = log.run([cli, "check", str(workspace)], allowed=(0, 1, 2))
    for leftover in (staging, previous):
        try:
            _remove_tree(leftover)
        except OSError:
            log.write(f"left {leftover} for the next run to remove")
    log.step(1.0, "Done")
    return {
        "workspace": str(workspace),
        "tools": [{"name": row["name"], "version": row["version"], "action": row["action"]} for row in rows],
        "backup": str(backup) if backup else None,
        "check_exit_code": check_code,
        "log": str(log.path),
    }


GENERATED_FILES = (
    f"{STATE_DIR}/workspace.json",
    f"{STATE_DIR}/generated.json",
    "WORKSPACE.md",
    "AGENTS.md",
    "CLAUDE.md",
    "Open Dashboard.cmd",
)
GENERATED_FOLDERS = (".agents/skills", ".claude/skills")


def _snapshot_generated(workspace: Path) -> dict[Path, bytes | None]:
    """Bytes of every file registration may rewrite, so a failed install can put them back."""
    saved: dict[Path, bytes | None] = {}
    for relative in GENERATED_FILES:
        path = workspace / relative
        saved[path] = path.read_bytes() if path.is_file() else None
    for relative in GENERATED_FOLDERS:
        folder = workspace / relative
        if folder.is_dir():
            for path in folder.rglob("*"):
                if path.is_file():
                    saved[path] = path.read_bytes()
    return saved


def _rollback(
    workspace: Path,
    venv: Path | None,
    placed: list[Path],
    moved: list[tuple[Path, Path]],
    saved_files: dict[Path, bytes | None],
) -> None:
    for target in placed:
        _remove_tree(target)
    if venv is not None and venv.exists():
        _remove_tree(venv)
    for saved, original in moved:
        if saved.exists():
            os.replace(saved, original)
    for relative in GENERATED_FOLDERS:
        folder = workspace / relative
        if folder.is_dir():
            for path in sorted(folder.rglob("*"), reverse=True):
                if path.is_file() and path not in saved_files:
                    path.unlink()
                elif path.is_dir() and not any(path.iterdir()):
                    path.rmdir()
    for path, content in saved_files.items():
        if content is None:
            path.unlink(missing_ok=True)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)


def main(argv: list[str] | None = None) -> int:
    """`python installer.py WORKSPACE [--release SOURCE] [--add NAME] [--option NAME:OPTION]`."""
    import argparse

    parser = argparse.ArgumentParser(description="Install or update a student workspace without the wizard.")
    parser.add_argument("workspace", type=Path)
    parser.add_argument("--release", default=RELEASE_URL, help="release.json path or URL")
    parser.add_argument("--add", action="append", default=[], metavar="TOOL", help="add a tool")
    parser.add_argument("--option", action="append", default=[], metavar="TOOL:OPTION")
    args = parser.parse_args(argv)
    options: dict[str, list[str]] = {}
    for value in args.option:
        tool, _, option = value.partition(":")
        options.setdefault(tool, []).append(option)
    try:
        result = install(
            args.workspace,
            load_release(args.release),
            set(args.add),
            options=options,
            progress=lambda _fraction, message: print(message, flush=True),
        )
    except InstallError as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
