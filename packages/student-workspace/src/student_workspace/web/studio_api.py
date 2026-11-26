"""Application Studio API. Every route calls `studio.store` (the same code as the CLI).

Changes return the whole updated version, so the interface redraws from one
response; the preview route returns the PDF and where each bullet landed.
"""

from __future__ import annotations

import base64
import threading
from collections import OrderedDict
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from ..state import secure_workspace_path
from ..studio import ats, export, handoff, importer
from ..studio.render import Rendered, Renderer
from ..studio.store import ENTRY_KINDS, Studio, StudioError

Kind = Literal["section", "entry", "bullet"]


class TextBody(BaseModel):
    text: str


class OptionalText(BaseModel):
    text: str | None = None


class VariantChoice(BaseModel):
    variant_id: str | None = None


class HiddenBody(BaseModel):
    kind: Kind
    id: str
    hidden: bool


class MoveBody(BaseModel):
    kind: Kind
    id: str
    position: int = Field(ge=0)


class SectionBody(BaseModel):
    title: str
    kind: str


class NewEntryBody(BaseModel):
    entry_id: str | None = None  # an existing library entry, or create one from the fields below
    kind: str | None = None
    title: str | None = None
    subtitle: str = ""
    location: str = ""
    dates: str = ""
    tech: str = ""
    details: str = ""
    note: str = ""
    url: str | None = None


class EntryPatch(BaseModel):
    title: str | None = None
    subtitle: str | None = None
    location: str | None = None
    dates: str | None = None
    tech: str | None = None
    details: str | None = None
    note: str | None = None
    url: str | None = None


class TemplateBody(BaseModel):
    template: str


class SettingsBody(BaseModel):
    font_size: float | None = None
    spacing: float | None = None
    margin: float | None = None


class ContactItem(BaseModel):
    text: str
    url: str | None = None


class HeaderBody(BaseModel):
    name: str
    contact: list[ContactItem] = []


class SkillLine(BaseModel):
    label: str
    value: str


class NewResumeBody(BaseModel):
    application_folder: str
    name: str
    contact: list[ContactItem] = []
    template: str = "jake"
    tex: str | None = None  # import a Jake's-style LaTeX resume instead of starting empty
    copy_from: str | None = None  # or start from an existing version (its sections and bullets)


class ExportBody(BaseModel):
    replace: bool = False


class AskBody(BaseModel):
    section_id: str
    request: str


class RequestPathBody(BaseModel):
    request_path: str


class EvidenceBody(BaseModel):
    title: str
    body: str = ""


class EvidenceLinkBody(BaseModel):
    kind: Literal["entry", "bullet"]
    target_id: str
    linked: bool = True


class EvidenceImportBody(BaseModel):
    path: str  # workspace-relative, e.g. applications/acme/evidence-matrix.md


class _PreviewCache:
    """The last few renders, keyed by version, template and last change, so repeat requests are free."""

    def __init__(self, size: int = 16) -> None:
        self._items: OrderedDict[tuple[str, str, str], Rendered] = OrderedDict()
        self._size = size
        self._lock = threading.Lock()

    def get(self, key: tuple[str, str, str]) -> Rendered | None:
        with self._lock:
            item = self._items.get(key)
            if item is not None:
                self._items.move_to_end(key)
            return item

    def put(self, key: tuple[str, str, str], value: Rendered) -> None:
        with self._lock:
            self._items[key] = value
            self._items.move_to_end(key)
            while len(self._items) > self._size:
                self._items.popitem(last=False)


def studio_router(root: Path) -> APIRouter:
    router = APIRouter(prefix="/api/studio", tags=["studio"])
    renderer = Renderer()
    cache = _PreviewCache()

    @contextmanager
    def opened() -> Iterator[Studio]:
        studio = Studio(root)
        try:
            yield studio
        finally:
            studio.close()

    def full(studio: Studio, version_id: str) -> dict[str, Any]:
        version = studio.version(version_id)
        version["export"] = export.export_state(studio, version_id)
        version["versions"] = [
            {"id": v["id"], "name": v["name"]}
            for r in studio.resumes()
            if r["id"] == version["resume_id"]
            for v in r["versions"]
        ]
        return version

    def render(studio: Studio, version_id: str) -> tuple[dict[str, Any], Rendered]:
        version = studio.version(version_id)
        key = (version_id, version["template"], version["updated_at"])
        data = studio.render_data(version_id)
        rendered = cache.get(key)
        if rendered is None:
            rendered = renderer.render(data, version["template"])
            cache.put(key, rendered)
        return data, rendered

    # ---------- resumes ----------

    @router.get("/resumes")
    def list_resumes() -> list[dict[str, Any]]:
        with opened() as s:
            return s.resumes()

    @router.post("/resumes")
    def create_resume(body: NewResumeBody) -> dict[str, Any]:
        with opened() as s:
            if body.tex is not None:
                result = importer.import_resume(s, body.application_folder, body.tex, template=body.template)
                return full(s, result["version_id"])
            _resume_id, version_id = s.create_resume(
                body.application_folder,
                header={"name": body.name, "contact": [c.model_dump() for c in body.contact]},
                template=body.template,
            )
            if body.copy_from:
                _copy_structure(s, body.copy_from, version_id)
            return full(s, version_id)

    @router.get("/library")
    def library() -> list[dict[str, Any]]:
        with opened() as s:
            return s.library()

    # ---------- one version ----------

    @router.get("/versions/{version_id}")
    def get_version(version_id: str) -> dict[str, Any]:
        with opened() as s:
            return full(s, version_id)

    @router.get("/versions/{version_id}/preview")
    def preview(version_id: str) -> dict[str, Any]:
        with opened() as s:
            _data, rendered = render(s, version_id)
        return {
            "pages": rendered.pages,
            "fill": rendered.fill,
            "page_width": rendered.page_width,
            "page_height": rendered.page_height,
            "boxes": rendered.boxes,
            "warnings": rendered.warnings,
            "pdf_base64": base64.b64encode(rendered.pdf).decode("ascii"),
        }

    @router.get("/versions/{version_id}/checks")
    def checks(version_id: str) -> dict[str, Any]:
        with opened() as s:
            data, rendered = render(s, version_id)
            report = ats.parse_check(rendered.pdf, data, margin_in=data["settings"]["margin"])
            version = s.version(version_id)
            coverage = ats.keyword_coverage(
                version["posting_text"], report.pop("extracted_text"), s.evidence()
            )
        return {"parse": report, "keywords": coverage}

    def change(version_id: str, action: Any) -> dict[str, Any]:
        with opened() as s:
            action(s)
            return full(s, version_id)

    @router.post("/versions/{version_id}/bullets/{bullet_id}/edit")
    def edit_bullet(version_id: str, bullet_id: str, body: TextBody) -> dict[str, Any]:
        return change(version_id, lambda s: s.edit_bullet(version_id, bullet_id, body.text))

    @router.post("/versions/{version_id}/bullets/{bullet_id}/save-to-library")
    def save_to_library(version_id: str, bullet_id: str) -> dict[str, Any]:
        return change(version_id, lambda s: s.save_bullet_to_library(version_id, bullet_id))

    @router.post("/versions/{version_id}/bullets/{bullet_id}/variant")
    def choose_variant(version_id: str, bullet_id: str, body: VariantChoice) -> dict[str, Any]:
        return change(version_id, lambda s: s.choose_variant(version_id, bullet_id, body.variant_id))

    @router.post("/versions/{version_id}/bullets/{bullet_id}/variants")
    def add_variant(version_id: str, bullet_id: str, body: TextBody) -> dict[str, Any]:
        return change(version_id, lambda s: s.add_variant(bullet_id, body.text))

    @router.post("/versions/{version_id}/bullets/{bullet_id}/raw")
    def set_raw(version_id: str, bullet_id: str, body: OptionalText) -> dict[str, Any]:
        return change(version_id, lambda s: s.set_raw(version_id, bullet_id, body.text))

    @router.post("/versions/{version_id}/bullets/{bullet_id}/remove")
    def remove_bullet(version_id: str, bullet_id: str) -> dict[str, Any]:
        return change(version_id, lambda s: s.remove_bullet(version_id, bullet_id))

    @router.post("/versions/{version_id}/entries/{entry_id}/bullets")
    def add_bullet(version_id: str, entry_id: str, body: TextBody) -> dict[str, Any]:
        return change(version_id, lambda s: s.add_bullet(version_id, entry_id, body.text))

    @router.post("/versions/{version_id}/entries/{entry_id}")
    def update_entry(version_id: str, entry_id: str, body: EntryPatch) -> dict[str, Any]:
        fields = body.model_dump(exclude_none=True)
        return change(version_id, lambda s: s.update_entry(entry_id, **fields))

    @router.post("/versions/{version_id}/hide")
    def hide(version_id: str, body: HiddenBody) -> dict[str, Any]:
        return change(version_id, lambda s: s.set_hidden(version_id, body.kind, body.id, body.hidden))

    @router.post("/versions/{version_id}/move")
    def move(version_id: str, body: MoveBody) -> dict[str, Any]:
        return change(version_id, lambda s: s.move(version_id, body.kind, body.id, body.position))

    @router.post("/versions/{version_id}/sections")
    def add_section(version_id: str, body: SectionBody) -> dict[str, Any]:
        return change(version_id, lambda s: s.add_section(version_id, body.title, body.kind))

    @router.post("/versions/{version_id}/sections/{section_id}/entries")
    def add_entry(version_id: str, section_id: str, body: NewEntryBody) -> dict[str, Any]:
        def action(s: Studio) -> None:
            entry_id = body.entry_id
            if entry_id is None:
                if body.kind not in ENTRY_KINDS or not body.title:
                    raise StudioError("a new entry needs a kind and a title")
                fields = body.model_dump(exclude={"entry_id", "kind"}, exclude_none=True)
                entry_id = s.create_entry(body.kind, **fields)
            s.add_entry_to_section(section_id, entry_id)

        return change(version_id, action)

    @router.post("/versions/{version_id}/template")
    def set_template(version_id: str, body: TemplateBody) -> dict[str, Any]:
        return change(version_id, lambda s: s.set_template(version_id, body.template))

    @router.post("/versions/{version_id}/settings")
    def set_settings(version_id: str, body: SettingsBody) -> dict[str, Any]:
        return change(version_id, lambda s: s.set_settings(version_id, body.model_dump(exclude_none=True)))

    @router.post("/versions/{version_id}/header")
    def set_header(version_id: str, body: HeaderBody) -> dict[str, Any]:
        return change(version_id, lambda s: s.set_header(version_id, body.model_dump()))

    @router.post("/versions/{version_id}/skills")
    def set_skills(version_id: str, body: list[SkillLine]) -> dict[str, Any]:
        return change(version_id, lambda s: s.set_skills(version_id, [line.model_dump() for line in body]))

    @router.post("/versions/{version_id}/posting")
    def set_posting(version_id: str, body: TextBody) -> dict[str, Any]:
        return change(version_id, lambda s: s.set_posting(s.version(version_id)["resume_id"], body.text))

    @router.post("/versions/{version_id}/new-version")
    def new_version(version_id: str) -> dict[str, Any]:
        with opened() as s:
            return full(s, s.new_version(version_id))

    @router.post("/versions/{version_id}/delete")
    def delete_version(version_id: str) -> dict[str, Any]:
        with opened() as s:
            resume_id = s.version(version_id)["resume_id"]
            s.delete_version(version_id)
            remaining = next(r for r in s.resumes() if r["id"] == resume_id)["versions"]
            return full(s, remaining[0]["id"])

    @router.post("/versions/{version_id}/export")
    def export_files(version_id: str, body: ExportBody) -> dict[str, Any]:
        with opened() as s:
            result = export.export_version(s, version_id, replace_outside_edits=body.replace)
            return {"result": result, "version": full(s, version_id)}

    @router.get("/versions/{version_id}/requests")
    def requests(version_id: str) -> list[dict[str, Any]]:
        with opened() as s:
            return handoff.requests_for(s, version_id)

    @router.post("/versions/{version_id}/ask-ai")
    def ask_ai(version_id: str, body: AskBody) -> dict[str, Any]:
        with opened() as s:
            return handoff.ask_ai(s, version_id, body.section_id, body.request)

    @router.post("/versions/{version_id}/import-variants")
    def import_variants(version_id: str, body: RequestPathBody) -> dict[str, Any]:
        with opened() as s:
            result = handoff.import_variants(s, body.request_path)
            return {"result": result, "version": full(s, version_id)}

    # ---------- evidence ----------

    @router.get("/evidence")
    def evidence() -> list[dict[str, Any]]:
        with opened() as s:
            return s.evidence()

    @router.post("/evidence")
    def add_evidence(body: EvidenceBody) -> dict[str, str]:
        with opened() as s:
            return {"id": s.add_evidence(body.title, body.body)}

    @router.post("/evidence/import")
    def import_evidence(body: EvidenceImportBody) -> dict[str, Any]:
        with opened() as s:
            path = secure_workspace_path(s.root, s.root, s.root / body.path, "evidence matrix")
            if not path.is_file():
                raise StudioError(f"{body.path} doesn't exist")
            return {"ids": importer.import_evidence_matrix(s, path, source_label=body.path)}

    @router.post("/evidence/{note_id}/links")
    def link_evidence(note_id: str, body: EvidenceLinkBody) -> dict[str, str]:
        with opened() as s:
            s.link_evidence(note_id, body.kind, body.target_id, linked=body.linked)
            return {"status": "ok"}

    return router


def _copy_structure(studio: Studio, source_version: str, target_version: str) -> None:
    """Start a new resume from another version: same sections, entries, visible bullets and wording."""
    source = studio.version(source_version)
    studio.set_header(target_version, source["header"])
    studio.set_skills(target_version, source["skills"])
    studio.set_settings(target_version, source["settings"])
    studio.set_template(target_version, source["template"])
    for section in source["sections"]:
        section_id = studio.add_section(target_version, section["title"], section["kind"])
        for entry in section["entries"]:
            studio.add_entry_to_section(section_id, entry["id"], with_bullets=False)
            if entry["hidden"]:
                studio.set_hidden(target_version, "entry", entry["id"], True)
            for bullet in entry["bullets"]:
                studio.include_bullet(target_version, bullet["id"])
                if bullet["override_text"]:
                    studio.edit_bullet(target_version, bullet["id"], bullet["override_text"])
                elif bullet["variant_id"]:
                    studio.choose_variant(target_version, bullet["id"], bullet["variant_id"])
                if bullet["hidden"]:
                    studio.set_hidden(target_version, "bullet", bullet["id"], True)
        if section["hidden"]:
            studio.set_hidden(target_version, "section", section_id, True)
