"""The shared source registry: preserved evidence files below `sources/`."""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from typing import Any

from .state import (
    STATE_DIR,
    WorkspaceStateError,
    atomic_json,
    parse_timestamp,
    read_json,
    require_object,
    require_workspace,
    secure_workspace_path,
    utc_now,
)

SOURCE_MANIFEST = f"{STATE_DIR}/source-manifest.json"
SCHEMA_VERSION = "1.0"
_FOLDER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")


def empty_manifest() -> dict[str, Any]:
    return {"schema_version": SCHEMA_VERSION, "imports": [], "external_references": [], "custom": {}}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stored_path(root: Path, value: Any, label: str) -> Path:
    if not isinstance(value, str) or "\\" in value:
        raise WorkspaceStateError(f"{label} must be a forward-slash path below sources/")
    portable = PurePosixPath(value)
    if (
        portable.is_absolute()
        or len(portable.parts) < 2
        or portable.parts[0] != "sources"
        or any(part in {".", ".."} or ":" in part for part in portable.parts)
        or portable.as_posix() != value
    ):
        raise WorkspaceStateError(f"{label} must be a forward-slash path below sources/")
    return secure_workspace_path(root, root / "sources", root.joinpath(*portable.parts), label)


def read_source_manifest(root: Path) -> dict[str, Any]:
    """Read and validate the registry; a missing registry is an error."""
    root, _metadata = require_workspace(root)
    path = root / SOURCE_MANIFEST
    if not path.is_file():
        raise WorkspaceStateError(f"source registry is missing: {SOURCE_MANIFEST}")
    manifest = read_json(path, {})
    if manifest.get("schema_version") != SCHEMA_VERSION or not isinstance(manifest.get("imports"), list):
        raise WorkspaceStateError("unsupported source registry; expected schema 1.0 with an imports array")
    require_object(manifest.get("custom", {}), "source registry custom")
    seen: set[str] = set()
    for index, raw in enumerate(manifest["imports"]):
        row = require_object(raw, f"imports[{index}]")
        if not all(key in row for key in ("stored_path", "sha256", "original_name", "imported_at")):
            raise WorkspaceStateError(f"imports[{index}] is incomplete")
        _stored_path(root, row["stored_path"], f"imports[{index}].stored_path")
        if row["stored_path"] in seen or not re.fullmatch(r"[0-9a-f]{64}", str(row["sha256"])):
            raise WorkspaceStateError(f"imports[{index}] repeats a path or has an invalid SHA-256")
        parse_timestamp(row["imported_at"], f"imports[{index}].imported_at")
        seen.add(row["stored_path"])
    return manifest


@contextmanager
def _registry_lock(root: Path) -> Iterator[None]:
    path = root / STATE_DIR / "source-manifest.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    except FileExistsError as exc:
        raise WorkspaceStateError(
            "source registry is locked by another operation; remove "
            f"{STATE_DIR}/source-manifest.lock only if no operation is running"
        ) from exc
    try:
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        yield
    finally:
        path.unlink(missing_ok=True)


def _append(root: Path, entry: dict[str, Any]) -> dict[str, Any]:
    manifest = read_source_manifest(root)
    for existing in manifest["imports"]:
        if existing["stored_path"] == entry["stored_path"]:
            if existing["sha256"] != entry["sha256"]:
                raise WorkspaceStateError(f"{entry['stored_path']} is registered with different content")
            return {"stored_path": entry["stored_path"], "reused": True}
    manifest["imports"].append(entry)
    atomic_json(root / SOURCE_MANIFEST, manifest)
    return {"stored_path": entry["stored_path"], "reused": False}


def import_source(
    root: Path, filename: Path, *, folder: str, custom: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Copy a file unchanged into `sources/<folder>/` and register it.

    Content-addressed: importing the same bytes again reuses the registered copy.
    """
    root, _metadata = require_workspace(root)
    filename = Path(filename).resolve()
    if not filename.is_file():
        raise WorkspaceStateError(f"source must be a file: {filename}")
    if not _FOLDER.fullmatch(folder):
        raise WorkspaceStateError("folder must be one portable path segment")
    content = filename.read_bytes()
    hashed = hashlib.sha256(content).hexdigest()
    clean_name = re.sub(r"[^A-Za-z0-9._-]", "-", filename.name)[:100] or "source"
    relative = f"sources/{folder}/{hashed[:16]}-{clean_name}"
    with _registry_lock(root):
        manifest = read_source_manifest(root)
        for entry in manifest["imports"]:
            stored = _stored_path(root, entry["stored_path"], "registered source")
            if entry["sha256"] == hashed and stored.is_file() and _sha256(stored) == hashed:
                return {"stored_path": entry["stored_path"], "reused": True}
        target = _stored_path(root, relative, "import destination")
        if target.exists() and _sha256(target) != hashed:
            raise WorkspaceStateError(f"import destination already holds different content: {relative}")
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(target.suffix + ".tmp")
        try:
            temporary.write_bytes(content)
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
        return _append(
            root,
            {
                "sha256": hashed,
                "original_name": filename.name,
                "stored_path": relative,
                "imported_at": utc_now(),
                "custom": custom or {},
            },
        )


def register_source(
    root: Path,
    stored_path: str,
    *,
    original_name: str | None = None,
    custom: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Register a file that is already saved below `sources/`."""
    root, _metadata = require_workspace(root)
    path = _stored_path(root, stored_path, "stored_path")
    if not path.is_file():
        raise WorkspaceStateError(f"source file does not exist: {stored_path}")
    with _registry_lock(root):
        return _append(
            root,
            {
                "sha256": _sha256(path),
                "original_name": original_name or path.name,
                "stored_path": stored_path,
                "imported_at": utc_now(),
                "custom": custom or {},
            },
        )


def manifest_text() -> str:
    return json.dumps(empty_manifest(), indent=2, sort_keys=True) + "\n"
