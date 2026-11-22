"""Generic, validated helpers for a private student workspace.

Tools use these helpers to read and write their own state below an initialized
workspace root. Nothing here knows about any particular tool.
"""

from __future__ import annotations

import json
import os
import re
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

STATE_DIR = ".student-workspace"
WORKSPACE_SCHEMA_VERSION = "1.0"
STATE_SCHEMA_VERSION = "1.0"
SAFE_ID = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}$")


class WorkspaceStateError(ValueError):
    """Private workspace state or input failed validation."""


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def require_object(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise WorkspaceStateError(f"{path} must be an object")
    return value


def require_string(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise WorkspaceStateError(f"{path} must be a non-empty string")
    return value


def require_string_array(value: Any, path: str, *, nonempty: bool = False) -> list[str]:
    if not isinstance(value, list) or (nonempty and not value):
        qualifier = "non-empty " if nonempty else ""
        raise WorkspaceStateError(f"{path} must be a {qualifier}string array")
    if not all(isinstance(item, str) and item.strip() for item in value):
        raise WorkspaceStateError(f"{path} must be a string array")
    return value


def require_timestamp(value: Any, path: str) -> str:
    timestamp = require_string(value, path)
    try:
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError as exc:
        raise WorkspaceStateError(f"{path} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise WorkspaceStateError(f"{path} must include a UTC offset or Z")
    return timestamp


def parse_timestamp(value: Any, path: str) -> datetime:
    timestamp = require_timestamp(value, path)
    return datetime.fromisoformat(timestamp.replace("Z", "+00:00")).astimezone(UTC)


def merge_custom(existing: Any, incoming: Any, path: str) -> dict[str, Any]:
    """Recursively merge extension objects without discarding unknown nested data."""
    before = require_object(existing, f"{path}.existing")
    after = require_object(incoming, f"{path}.incoming")
    merged: dict[str, Any] = dict(before)
    for key, value in after.items():
        if isinstance(merged.get(key), dict) and isinstance(value, dict):
            merged[key] = merge_custom(merged[key], value, f"{path}.{key}")
        else:
            merged[key] = value
    return merged


def secure_workspace_path(root: Path, allowed_root: Path, path: Path, label: str) -> Path:
    """Reject lexical escapes, resolved escapes, and every symlink component."""
    root = root.absolute()
    allowed_root = allowed_root.absolute()
    candidate = path.absolute()
    try:
        allowed_root.relative_to(root)
        candidate.relative_to(allowed_root)
        workspace_relative = candidate.relative_to(root)
    except ValueError as exc:
        raise WorkspaceStateError(f"{label} is outside its allowed workspace directory") from exc

    current = root
    for part in workspace_relative.parts:
        current = current / part
        if current.is_symlink():
            raise WorkspaceStateError(f"{label} contains a symlink component: {current}")

    resolved_allowed = allowed_root.resolve(strict=False)
    resolved_candidate = candidate.resolve(strict=False)
    try:
        resolved_allowed.relative_to(root.resolve(strict=False))
        resolved_candidate.relative_to(resolved_allowed)
    except ValueError as exc:
        raise WorkspaceStateError(f"{label} resolves outside its allowed workspace directory") from exc
    return candidate


def state_path(root: Path, *parts: str) -> Path:
    """A path below the workspace's private state folder, checked for escapes."""
    base = root / STATE_DIR
    return secure_workspace_path(root, base, base.joinpath(*parts), "workspace state")


def atomic_json(path: Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    payload = (json.dumps(document, indent=2, sort_keys=True) + "\n").encode("utf-8")
    try:
        with open(temporary, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        with suppress(FileNotFoundError):
            temporary.unlink()


def atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        with open(temporary, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        with suppress(FileNotFoundError):
            temporary.unlink()


def read_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default
    try:
        return require_object(json.loads(path.read_text(encoding="utf-8")), str(path))
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkspaceStateError(f"could not read {path}: {exc}") from exc


def require_workspace(root: Path) -> tuple[Path, dict[str, Any]]:
    """Resolve an initialized workspace and validate its machine metadata."""
    root = Path(root).expanduser().resolve()
    metadata = read_json(root / STATE_DIR / "workspace.json", {})
    if metadata.get("schema_version") != WORKSPACE_SCHEMA_VERSION:
        raise WorkspaceStateError(f"{root} is not an initialized schema-{WORKSPACE_SCHEMA_VERSION} workspace")
    require_object(metadata.get("custom", {}), f"{STATE_DIR}/workspace.json.custom")
    if not isinstance(metadata.get("private_state_root"), str):
        raise WorkspaceStateError("workspace metadata private_state_root must be a string")
    tools = metadata.get("tools", [])
    if not isinstance(tools, list) or not all(isinstance(item, dict) for item in tools):
        raise WorkspaceStateError("workspace metadata tools must be an object array")
    return root, metadata


def write_checkpoint(
    root: Path,
    *,
    operation: str,
    operation_id: str,
    status: str,
    completed_steps: list[str],
    exact_next_action: str,
    input_sha256: str | None,
    error: str | None = None,
) -> Path:
    """Record the latest operation so an interrupted step can be resumed by hand."""
    path = root / STATE_DIR / "checkpoint.json"
    existing = read_json(path, {})
    custom = existing.get("custom", {})
    require_object(custom, f"{STATE_DIR}/checkpoint.json.custom")
    document: dict[str, Any] = {
        "schema_version": STATE_SCHEMA_VERSION,
        "operation": operation,
        "operation_id": operation_id,
        "status": status,
        "updated_at": utc_now(),
        "completed_steps": completed_steps,
        "exact_next_action": exact_next_action,
        "input_sha256": input_sha256,
        "custom": custom,
    }
    if error:
        document["error"] = error[:1000]
    atomic_json(path, document)
    return path
