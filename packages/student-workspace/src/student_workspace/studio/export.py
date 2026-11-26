"""Write a version's source and PDF into its application folder, and check they still match.

The PDF is always compiled from the exact source file written next to it, and
both files' SHA-256 are recorded, so the studio can tell when either was changed
outside it (for example by editing the .typ by hand).
"""

from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path
from typing import Any, Literal

from ..state import secure_workspace_path
from .render import compile_source, export_source
from .store import Studio, StudioError

# current: the files match what the studio wrote and the resume hasn't changed since.
# outdated: the files match what the studio wrote, but the resume was edited afterwards.
ExportState = Literal["not-exported", "current", "outdated", "changed-outside", "missing"]


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _atomic_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.replace(temp, path)
    except BaseException:
        Path(temp).unlink(missing_ok=True)
        raise


def export_paths(studio: Studio, version: dict[str, Any]) -> tuple[Path, Path]:
    folder = secure_workspace_path(
        studio.root,
        studio.root / "applications",
        studio.root / version["application_folder"],
        "application folder",
    )
    return folder / f"{version['name']}.typ", folder / f"{version['name']}.pdf"


def export_state(studio: Studio, version_id: str) -> dict[str, Any]:
    version = studio.version(version_id)
    source_path, pdf_path = export_paths(studio, version)
    state: ExportState
    if not version["exported_at"]:
        state = "not-exported"
    elif not source_path.is_file() or not pdf_path.is_file():
        state = "missing"
    elif (
        _sha256(source_path.read_bytes()) != version["exported_source_sha256"]
        or _sha256(pdf_path.read_bytes()) != version["exported_pdf_sha256"]
    ):
        state = "changed-outside"
    elif (
        _sha256(export_source(studio.render_data(version_id), version["template"]).encode("utf-8"))
        != version["exported_source_sha256"]
    ):
        state = "outdated"
    else:
        state = "current"
    return {
        "state": state,
        "exported_at": version["exported_at"],
        "source_path": source_path.relative_to(studio.root).as_posix(),
        "pdf_path": pdf_path.relative_to(studio.root).as_posix(),
    }


def export_version(studio: Studio, version_id: str, *, replace_outside_edits: bool = False) -> dict[str, Any]:
    """Write <name>.typ and <name>.pdf; refuse to overwrite files changed outside the studio."""
    version = studio.version(version_id)
    status = export_state(studio, version_id)
    source_path, pdf_path = export_paths(studio, version)
    if status["state"] == "changed-outside" and not replace_outside_edits:
        raise StudioError(
            f"{status['source_path']} or its PDF was changed outside the studio; "
            "export again with replace to overwrite it"
        )
    if (
        status["state"] == "not-exported"
        and (source_path.exists() or pdf_path.exists())
        and not replace_outside_edits
    ):
        raise StudioError(f"{status['source_path']} already exists and wasn't written by the studio")
    source = export_source(studio.render_data(version_id), version["template"]).encode("utf-8")
    pdf = compile_source(source.decode("utf-8"))
    _atomic_bytes(source_path, source)
    _atomic_bytes(pdf_path, pdf)
    studio.record_export(version_id, _sha256(source), _sha256(pdf))
    return {
        **export_state(studio, version_id),
        "source_sha256": _sha256(source),
        "pdf_sha256": _sha256(pdf),
        "pdf_bytes": len(pdf),
    }


def verify_export(studio: Studio, version_id: str) -> bool:
    """Recompile the exported source from disk: True when it reproduces the exported PDF byte for byte."""
    status = export_state(studio, version_id)
    if status["state"] not in ("current", "outdated"):
        return False
    source_path, pdf_path = export_paths(studio, studio.version(version_id))
    return compile_source(source_path.read_text(encoding="utf-8")) == pdf_path.read_bytes()
