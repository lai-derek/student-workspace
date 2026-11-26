""" "Ask the AI" for one section: an application handoff, and importing the variants it returns.

The studio doesn't call any AI. It writes a normal application request (the
same mechanism as `student-workspace apply`) whose target snapshot holds the
section's bullets and their ids. The student's own agent writes
`drafts/variants.json` and `response.json`; importing checks the response with
the existing `apply check` and stores each variant for the student to pick.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..application_checks import check_application_request
from ..applications import create_application_request, list_application_requests
from ..state import secure_workspace_path
from .store import Studio, StudioError, _text

TARGET_KIND = "studio-section"
VARIANTS_FILE = "drafts/variants.json"
MAX_VARIANTS = 200


def ask_ai(
    studio: Studio, version_id: str, section_id: str, instruction: str, *, references: tuple[str, ...] = ()
) -> dict[str, Any]:
    version = studio.version(version_id)
    section = next((s for s in version["sections"] if s["id"] == section_id), None)
    if section is None:
        raise StudioError("section not found in this version")
    instruction = _text(instruction, "request", limit=1500)
    target = {
        "kind": TARGET_KIND,
        "id": section_id,
        "url": None,
        "version_id": version_id,
        "version": version["name"],
        "section": section["title"],
        "entries": [
            {
                "entry_id": entry["id"],
                "title": entry["title"],
                "subtitle": entry["subtitle"],
                "bullets": [
                    {"bullet_id": b["id"], "text": b["text"]} for b in entry["bullets"] if not b["hidden"]
                ],
                "evidence": [{"title": n["title"], "body": n["body"]} for n in entry["evidence"]],
            }
            for entry in section["entries"]
            if not entry["hidden"]
        ],
        "posting_excerpt": version["posting_text"][:3000],
    }
    request_text = (
        "Application Studio: suggest alternative wordings for the bullets in the "
        f'"{section["title"]}" section of {version["name"]}.\n\n'
        f"What the student asked: {instruction}\n\n"
        "The section's bullets and their ids are in target.json. Write drafts/variants.json as\n"
        '{"schema_version": "1.0", "variants": '
        '[{"bullet_id": "<id from target.json>", "text": "<wording>"}]}\n'
        "with up to three variants per bullet. Keep each claim within what the evidence supports. "
        "Text may use **bold**, *italic* and [text](url). Then write response.json with status "
        '"drafted" and artifacts [{"path": "drafts/variants.json", "kind": "draft"}], and run the apply '
        "check. The student picks variants in the studio; don't edit any resume files."
    )
    return create_application_request(
        studio.root,
        target,
        "resume",
        request_text,
        application_folder=version["application_folder"],
        references=references,
    )


def requests_for(studio: Studio, version_id: str) -> list[dict[str, Any]]:
    """This application's studio requests (newest first) and whether each has an answer."""
    version = studio.version(version_id)
    rows = []
    for item in list_application_requests(studio.root, version["application_folder"]):
        folder = studio.root / item["path"]
        try:
            target = json.loads((folder / "target.json").read_text(encoding="utf-8"))
        except OSError, ValueError:
            continue
        if target.get("kind") != TARGET_KIND or target.get("version_id") != version_id:
            continue
        imported = studio.conn.execute(
            "SELECT COUNT(*) FROM bullet_variants WHERE request_id = ?", (item["request_id"],)
        ).fetchone()[0]
        rows.append(
            {
                "request_path": item["path"],
                "request_id": item["request_id"],
                "section": target.get("section"),
                "status": item["response_status"],
                "created_at": item.get("created_at"),
                "imported_variants": imported,
            }
        )
    return rows


def import_variants(studio: Studio, request_path: str) -> dict[str, Any]:
    check = check_application_request(studio.root, request_path)
    if not check["valid"]:
        raise StudioError(
            "the request's response doesn't pass apply check: " + "; ".join(check["errors"][:3])
        )
    if check["response_status"] != "drafted":
        raise StudioError(f"the request isn't answered yet ({check['response_status']})")
    folder = secure_workspace_path(
        studio.root, studio.root / "applications", studio.root / request_path, "application request"
    )
    target = json.loads((folder / "target.json").read_text(encoding="utf-8"))
    request = json.loads((folder / "request.json").read_text(encoding="utf-8"))
    if target.get("kind") != TARGET_KIND:
        raise StudioError("this request wasn't made by the studio")
    allowed = {b["bullet_id"] for e in target.get("entries", []) for b in e.get("bullets", [])}
    path = Path(folder / VARIANTS_FILE)
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise StudioError(f"{VARIANTS_FILE} is missing or isn't valid JSON") from exc
    if not isinstance(document, dict) or document.get("schema_version") != "1.0":
        raise StudioError(f'{VARIANTS_FILE} needs "schema_version": "1.0"')
    variants = document.get("variants")
    if not isinstance(variants, list):
        raise StudioError(f"{VARIANTS_FILE} needs a variants list")
    added, skipped = 0, []
    for item in variants[:MAX_VARIANTS]:
        bullet_id = item.get("bullet_id") if isinstance(item, dict) else None
        if not isinstance(bullet_id, str) or bullet_id not in allowed:
            skipped.append(f"unknown bullet {bullet_id!r}")
            continue
        text = item.get("text")
        if not isinstance(text, str):
            skipped.append(f"variant for {bullet_id} has no text")
            continue
        try:
            studio.add_variant(bullet_id, text, source="ai", request_id=request["request_id"])
            added += 1
        except StudioError as exc:
            skipped.append(str(exc))
    return {"request_id": request["request_id"], "added": added, "skipped": skipped}
