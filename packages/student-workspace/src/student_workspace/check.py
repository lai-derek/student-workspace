"""Workspace-wide check: exit 0 current, 2 stale, 1 error."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from .recovery import audit_workspace
from .state import WorkspaceStateError, require_workspace
from .tools import installed_version, registered_tools, resolve_command

OK, ERROR, STALE = 0, 1, 2
_RANK = {OK: 0, STALE: 1, ERROR: 2}


def _worst(codes: list[int]) -> int:
    return max(codes, key=lambda code: _RANK[code], default=OK)


def check_workspace(root: Path) -> dict[str, Any]:
    """Run the workspace audit and every registered tool's own check."""
    root, _metadata = require_workspace(root)
    results: list[dict[str, Any]] = []

    audit = audit_workspace(root)
    results.append(
        {
            "name": "workspace",
            "status": ERROR if audit.errors else OK,
            "detail": [f"[{f.severity}] {f.rule}: {f.path} {f.detail}" for f in audit.findings],
        }
    )

    for record, folder, manifest, error in registered_tools(root):
        name = str(record.get("name"))
        if manifest is None:
            results.append({"name": name, "status": ERROR, "detail": [str(error)]})
            continue
        detail: list[str] = []
        status = OK
        if not folder.is_dir():
            results.append({"name": name, "status": ERROR, "detail": [f"tool folder is missing: {folder}"]})
            continue
        try:
            version = installed_version(manifest["package"])
        except WorkspaceStateError as exc:
            results.append({"name": name, "status": ERROR, "detail": [str(exc)]})
            continue
        if version != record.get("version"):
            status = STALE
            detail.append(
                f"installed {version} but registered {record.get('version')}; "
                f"run student-workspace register WORKSPACE {folder}"
            )
        if manifest["check_command"]:
            try:
                command = resolve_command(manifest["check_command"], root)
                completed = subprocess.run(command, capture_output=True, text=True, check=False)
            except (OSError, WorkspaceStateError) as exc:
                status = ERROR
                detail.append(str(exc))
            else:
                output = (completed.stdout + completed.stderr).strip()
                if output:
                    detail.extend(output.splitlines()[-20:])
                if completed.returncode == STALE:
                    status = _worst([status, STALE])
                elif completed.returncode != OK:
                    status = ERROR
                    detail.append(f"check exited with {completed.returncode}")
        results.append({"name": name, "version": version, "status": status, "detail": detail})

    code = _worst([item["status"] for item in results])
    return {
        "schema_version": "1.0",
        "workspace": str(root),
        "status": {OK: "current", STALE: "stale", ERROR: "error"}[code],
        "exit_code": code,
        "results": results,
    }
