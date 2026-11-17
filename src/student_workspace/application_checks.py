"""Read-only validation of private application handoffs; no model or network calls."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from html import unescape
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import unquote, urlsplit

from .state import WorkspaceStateError, require_workspace, secure_workspace_path

REQUEST_ID = re.compile(r"req_[0-9]{8}T[0-9]{6}Z_[0-9a-f]{12}")
ARTIFACT_PATH = re.compile(r"(drafts|revisions)/[A-Za-z0-9][A-Za-z0-9._-]*")
RESPONSE_KEYS = {"schema_version", "request_id", "status", "artifacts", "source_refs", "notes", "custom"}


def _document(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise WorkspaceStateError(f"cannot read JSON object {path.name}: {exc}") from exc
    if not isinstance(value, dict):
        raise WorkspaceStateError(f"{path.name} must be a JSON object")
    return value


def _artifact(root: Path, folder: Path, relative: Any) -> Path:
    if not isinstance(relative, str) or not ARTIFACT_PATH.fullmatch(relative):
        raise WorkspaceStateError("artifact path must name a file under drafts/ or revisions/")
    path = secure_workspace_path(root, folder, folder / relative, "application artifact")
    if not path.is_file():
        raise WorkspaceStateError(f"missing application artifact: {relative}")
    return path


def _source(root: Path, reference: str) -> tuple[Path | None, str]:
    """Resolve an evidence reference, allowing external URLs without fetching them."""
    if urlsplit(reference).scheme.lower() in {"https", "http"}:
        if not urlsplit(reference).hostname or re.search(r"\s", reference):
            raise WorkspaceStateError(f"invalid source URL: {reference}")
        return None, ""
    relative, _, anchor = reference.partition("#")
    portable = PurePosixPath(relative)
    if (
        "\\" in relative
        or portable.is_absolute()
        or len(portable.parts) < 2
        or portable.parts[0] not in {"sources", "knowledge"}
        or any(part in {".", ".."} or ":" in part for part in portable.parts)
        or portable.as_posix() != relative
    ):
        raise WorkspaceStateError(f"source reference must point below sources/ or knowledge/: {reference}")
    path = secure_workspace_path(root, root / portable.parts[0], root / relative, "application source")
    if not path.is_file():
        raise WorkspaceStateError(f"missing source reference: {reference}")
    return path, unquote(anchor)


def inspect_application_response(root: Path, folder: Path, *, request_id: str) -> dict[str, Any]:
    """Return a response status without treating file existence as a valid response."""
    response_path = secure_workspace_path(root, folder, folder / "response.json", "application response")
    if not response_path.exists():
        return {"status": "awaiting-response", "errors": [], "artifacts": [], "source_refs": []}
    try:
        value = _document(response_path)
        if set(value) != RESPONSE_KEYS:
            raise WorkspaceStateError("response.json has missing or unknown fields")
        if value["schema_version"] != "1.0":
            raise WorkspaceStateError("unsupported response schema_version")
        if value["request_id"] != request_id or not REQUEST_ID.fullmatch(request_id):
            raise WorkspaceStateError("response request_id does not match its request folder")
        if value["status"] not in ("drafted", "needs-input"):
            raise WorkspaceStateError("response status must be drafted or needs-input")
        if not isinstance(value["notes"], str) or not isinstance(value["custom"], dict):
            raise WorkspaceStateError("response notes/custom have invalid types")
        if not isinstance(value["artifacts"], list) or not isinstance(value["source_refs"], list):
            raise WorkspaceStateError("response artifacts/source_refs must be arrays")
        if value["status"] == "drafted" and not value["artifacts"]:
            raise WorkspaceStateError("a drafted response must have at least one existing artifact")
        artifacts = []
        for raw in value["artifacts"]:
            if not isinstance(raw, dict) or set(raw) != {"path", "kind"}:
                raise WorkspaceStateError("artifact must contain path and kind")
            path = _artifact(root, folder, raw["path"])
            if (
                raw["kind"] not in ("draft", "revision")
                or path.parent.name != {"draft": "drafts", "revision": "revisions"}[raw["kind"]]
            ):
                raise WorkspaceStateError("artifact kind does not match its directory")
            artifacts.append(raw["path"])
        for reference in value["source_refs"]:
            if not isinstance(reference, str):
                raise WorkspaceStateError("source_refs entries must be strings")
            _source(root, reference)
        return {
            "status": value["status"],
            "errors": [],
            "artifacts": artifacts,
            "source_refs": value["source_refs"],
        }
    except (OSError, ValueError, WorkspaceStateError) as exc:
        return {"status": "invalid-response", "errors": [str(exc)], "artifacts": [], "source_refs": []}


def _without_fences(text: str) -> str:
    lines = []
    fence = ""
    for line in text.splitlines():
        match = re.match(r"^\s{0,3}(" + chr(96) + r"{3,}|~{3,})", line)
        if match:
            marker = match[1]
            if not fence:
                fence = marker
            elif marker[0] == fence[0] and len(marker) >= len(fence):
                fence = ""
            continue
        if not fence:
            lines.append(line)
    return "\n".join(lines)


def _anchors(text: str) -> set[str]:
    """Recognize common GitHub-style ATX/setext headings and explicit HTML IDs."""
    text = _without_fences(text)
    headings = []
    lines = text.splitlines()
    for index, line in enumerate(lines):
        match = re.match(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$", line)
        if match:
            headings.append(match[1])
        elif index and re.fullmatch(r"\s{0,3}(?:=+|-+)\s*", line) and lines[index - 1].strip():
            headings.append(lines[index - 1])
    anchors = set()
    for heading in headings:
        heading = re.sub(r"<[^>]*>", "", heading)
        heading = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", heading)
        heading = unescape(heading).lower().strip()
        slug = "".join(
            char
            for char in heading
            if char in "-_" or char.isspace() or unicodedata.category(char)[0] in "LN"
        ).replace(" ", "-")
        candidate = slug
        suffix = 0
        while candidate in anchors:
            suffix += 1
            candidate = f"{slug}-{suffix}"
        anchors.add(candidate)
    anchors.update(re.findall(r"\b(?:id|name)\s*=\s*[\"']([^\"']+)[\"']", text, re.I))
    return anchors


def _check_anchor(path: Path, anchor: str) -> None:
    if (
        anchor
        and path.suffix.lower() in {".md", ".markdown"}
        and anchor not in _anchors(path.read_text(encoding="utf-8"))
    ):
        raise WorkspaceStateError(f"missing Markdown anchor: {path.name}#{anchor}")


def _markdown_targets(text: str) -> list[str]:
    text = _without_fences(text)
    text = re.sub(chr(96) + r"+[^" + chr(96) + r"\n]*" + chr(96) + "+", "", text)
    # Common inline links/images and reference definitions; no renderer or network dependency.
    targets = re.findall(r"!?\[[^\]\n]*\]\(\s*(<[^>\n]+>|[^\s)]+)", text)
    targets.extend(re.findall(r"^\s{0,3}\[[^\]\n]+\]:\s*(<[^>\n]+>|[^\s]+)", text, re.M))
    return [target.removeprefix("<").removesuffix(">") for target in targets]


def check_application_request(root: Path, request_path: str) -> dict[str, Any]:
    """Validate a saved request, response, references, local links and declared limits."""
    root, _metadata = require_workspace(root)
    portable = PurePosixPath(request_path)
    if (
        "\\" in request_path
        or portable.is_absolute()
        or portable.as_posix() != request_path
        or len(portable.parts) < 4
        or portable.parts[0] != "applications"
        or portable.parts[-2] != "requests"
        or not REQUEST_ID.fullmatch(portable.name)
        or any(part in {".", ".."} or ":" in part for part in portable.parts)
    ):
        raise WorkspaceStateError("request_path must name an application requests/req_... folder")
    folder = secure_workspace_path(root, root / "applications", root / request_path, "application request")
    request = _document(secure_workspace_path(root, folder, folder / "request.json", "request manifest"))
    if request.get("request_id") != folder.name:
        raise WorkspaceStateError("request identity does not match its folder")
    result: dict[str, Any] = {
        "schema_version": "1.0",
        "request_path": request_path,
        "errors": [],
        "warnings": [],
        "response_status": None,
        "fields": [],
        "local_links_checked": 0,
    }
    response = inspect_application_response(root, folder, request_id=folder.name)
    result["response_status"] = response["status"]
    result["errors"].extend(response["errors"])
    if response["status"] == "awaiting-response":
        result["warnings"].append("No response recorded; drafting is not established.")
    markdown_paths = set()
    try:
        references = _document(
            secure_workspace_path(root, folder, folder / "references.json", "application references")
        )
        if set(references) != {"schema_version", "references"} or references["schema_version"] != "1.0":
            raise WorkspaceStateError("invalid references.json fields or schema_version")
        if not isinstance(references["references"], list) or len(references["references"]) > 52:
            raise WorkspaceStateError("references must be an array of at most 52 entries")
        for raw in references["references"]:
            if not isinstance(raw, dict) or set(raw) != {"path", "kind", "sha256"}:
                raise WorkspaceStateError("invalid reference entry")
            if not isinstance(raw["path"], str) or "#" in raw["path"]:
                raise WorkspaceStateError("reference snapshot must name a whole source/knowledge file")
            path, _ = _source(root, raw["path"])
            if path is None or raw["kind"] != PurePosixPath(raw["path"]).parts[0]:
                raise WorkspaceStateError("reference kind must match its local directory")
            if not isinstance(raw["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", raw["sha256"]):
                raise WorkspaceStateError("invalid reference SHA-256")
            if hashlib.sha256(path.read_bytes()).hexdigest() != raw["sha256"]:
                result["warnings"].append(f"Reference changed since request: {raw['path']}")
    except (OSError, ValueError, WorkspaceStateError) as exc:
        result["errors"].append(str(exc))
    for reference in response["source_refs"]:
        try:
            path, anchor = _source(root, reference)
            if path is not None:
                _check_anchor(path, anchor)
        except (OSError, ValueError, WorkspaceStateError) as exc:
            result["errors"].append(str(exc))
    for relative in response["artifacts"]:
        path = _artifact(root, folder, relative)
        if path.suffix.lower() in {".md", ".markdown"}:
            markdown_paths.add(path)
    checks_path = secure_workspace_path(root, folder, folder / "checks.json", "application checks")
    if checks_path.exists():
        try:
            checks = _document(checks_path)
            if set(checks) != {"schema_version", "fields", "custom"} or checks["schema_version"] != "1.0":
                raise WorkspaceStateError("invalid checks.json fields or schema_version")
            if not isinstance(checks["fields"], list) or not isinstance(checks["custom"], dict):
                raise WorkspaceStateError("checks fields/custom have invalid types")
            for field in checks["fields"]:
                if (
                    not isinstance(field, dict)
                    or "path" not in field
                    or set(field) - {"path", "max_words", "max_characters"}
                    or not ({"max_words", "max_characters"} & set(field))
                ):
                    raise WorkspaceStateError("each field needs an artifact path and at least one limit")
                path = _artifact(root, folder, field["path"])
                text = path.read_text(encoding="utf-8")
                counts: dict[str, Any] = {
                    "path": field["path"],
                    "words": len(text.split()),
                    "characters": len(text),
                }
                for key, count in (("max_words", counts["words"]), ("max_characters", counts["characters"])):
                    if key in field:
                        limit = field[key]
                        if type(limit) is not int or limit < 0:
                            raise WorkspaceStateError(f"{key} must be a nonnegative integer")
                        if count > limit:
                            result["errors"].append(f"{field['path']}: {count} exceeds {key}={limit}")
                result["fields"].append(counts)
                if path.suffix.lower() in {".md", ".markdown"}:
                    markdown_paths.add(path)
        except (OSError, ValueError, WorkspaceStateError) as exc:
            result["errors"].append(str(exc))
    for path in sorted(markdown_paths):
        try:
            for target in _markdown_targets(path.read_text(encoding="utf-8")):
                if re.match(r"^[A-Za-z]:", target):
                    raise WorkspaceStateError("local Markdown links must stay inside the workspace")
                parsed = urlsplit(target)
                if parsed.scheme or parsed.netloc:
                    continue
                linked = secure_workspace_path(
                    root,
                    root,
                    path.parent / unquote(parsed.path) if parsed.path else path,
                    "Markdown link",
                )
                if not linked.exists():
                    raise WorkspaceStateError(f"missing local Markdown link in {path.name}: {target}")
                if parsed.fragment and linked.is_file():
                    _check_anchor(linked, unquote(parsed.fragment))
                result["local_links_checked"] += 1
        except (OSError, ValueError, WorkspaceStateError) as exc:
            result["errors"].append(str(exc))
    result["valid"] = not result["errors"]
    return result
