"""Every read and change of studio data. The CLI and the app's API both call these methods.

Vocabulary:
- The **library** holds entries (a job, project, school...) and their bullets,
  shared by every resume. Bullets can have **variants** (alternative wordings)
  and **evidence** notes.
- A **resume** belongs to one application folder and has **versions**
  (`resume-YYYY-MM-DD`). A version has sections; each section lists library
  entries; each entry shows some of its bullets. The version decides order and
  visibility, and per bullet can override the text, pick a variant, or use raw
  Typst. Editing a bullet in a version doesn't change other resumes until it is
  saved to the library.
"""

from __future__ import annotations

import json
import re
import secrets
import sqlite3
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import Any, Literal

from ..applications import APPLICATION_FOLDER
from ..state import WorkspaceStateError, require_workspace, utc_now
from .db import connect

TEMPLATES = ("jake", "classic", "modern")
ENTRY_KINDS = ("education", "experience", "project", "leadership", "other")
ENTRY_FIELDS = ("title", "url", "tech", "details", "subtitle", "location", "dates", "note")
SETTINGS = {
    # name: (minimum, maximum, default)
    "font_size": (9.0, 12.0, 10.5),
    "spacing": (0.5, 1.6, 1.0),
    "margin": (0.4, 1.0, 0.5),
}
MAX_TEXT = 2000
_URL = re.compile(r"(https?://|mailto:)\S+")

Kind = Literal["section", "entry", "bullet"]


class StudioError(WorkspaceStateError):
    """A studio request that can't be carried out; the message says why."""


def _id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(6)}"


def _text(
    value: Any, field: str, *, allow_empty: bool = False, limit: int = MAX_TEXT, multiline: bool = False
) -> str:
    if not isinstance(value, str):
        raise StudioError(f"{field} must be text")
    value = value.strip()
    if not value and not allow_empty:
        raise StudioError(f"{field} can't be empty")
    if len(value) > limit:
        raise StudioError(f"{field} is longer than {limit} characters")
    allowed = "\t\n\r" if multiline else "\t"
    if any(ord(ch) < 32 and ch not in allowed for ch in value):
        raise StudioError(f"{field} contains control characters")
    return value


def _url(value: Any, field: str) -> str | None:
    if value in (None, ""):
        return None
    value = _text(value, field, limit=500)
    if not _URL.fullmatch(value):
        raise StudioError(f"{field} must start with http://, https:// or mailto:")
    return value


def settings_with_defaults(raw: dict[str, Any] | None = None) -> dict[str, float]:
    raw = raw or {}
    result = {}
    for name, (low, high, default) in SETTINGS.items():
        value = raw.get(name, default)
        if not isinstance(value, int | float) or isinstance(value, bool) or not low <= value <= high:
            raise StudioError(f"setting {name} must be a number from {low} to {high}")
        result[name] = float(value)
    unknown = set(raw) - set(SETTINGS)
    if unknown:
        raise StudioError(f"unknown settings: {', '.join(sorted(unknown))}")
    return result


def _header(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise StudioError("header must be an object with name and contact")
    contact = value.get("contact", [])
    if not isinstance(contact, list) or len(contact) > 8:
        raise StudioError("header contact must be a list of at most 8 items")
    return {
        "name": _text(value.get("name"), "name", limit=120),
        "contact": [
            {
                "text": _text(item.get("text"), "contact text", limit=200),
                "url": _url(item.get("url"), "contact url"),
            }
            for item in contact
            if isinstance(item, dict)
        ],
    }


def _skills(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list) or len(value) > 12:
        raise StudioError("skills must be a list of at most 12 lines")
    return [
        {
            "label": _text(item.get("label"), "skill label", limit=80),
            "value": _text(item.get("value"), "skills"),
        }
        for item in value
        if isinstance(item, dict)
    ]


def version_name(day: date | None = None, taken: Iterable[str] = ()) -> str:
    base = f"resume-{(day or date.today()).isoformat()}"
    taken = set(taken)
    if base not in taken:
        return base
    n = 2
    while f"{base}-{n}" in taken:
        n += 1
    return f"{base}-{n}"


class Studio:
    """An open studio database for one workspace. Use as a context manager."""

    def __init__(self, root: Path) -> None:
        self.root, _metadata = require_workspace(root)
        self.conn = connect(self.root)

    def __enter__(self) -> Studio:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        self.conn.close()

    @contextmanager
    def _write(self) -> Iterator[sqlite3.Connection]:
        """One transaction: everything inside commits together or not at all."""
        with self.conn:
            yield self.conn

    def _one(self, sql: str, params: Iterable[Any], what: str) -> sqlite3.Row:
        row = self.conn.execute(sql, tuple(params)).fetchone()
        if row is None:
            raise StudioError(f"{what} not found")
        return row

    def _touch(self, version_id: str) -> None:
        self.conn.execute("UPDATE versions SET updated_at = ? WHERE id = ?", (utc_now(), version_id))

    # ---------- library ----------

    def create_entry(self, kind: str, title: str, **fields: Any) -> str:
        if kind not in ENTRY_KINDS:
            raise StudioError(f"entry kind must be one of {', '.join(ENTRY_KINDS)}")
        values = self._entry_values({"title": title, **fields})
        entry_id = _id("ent")
        now = utc_now()
        with self._write() as c:
            c.execute(
                "INSERT INTO entries (id, kind, title, url, tech, details, subtitle, location, dates, note,"
                " created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    entry_id,
                    kind,
                    *(values.get(f, None if f == "url" else "") for f in ENTRY_FIELDS),
                    now,
                    now,
                ),
            )
        return entry_id

    def _entry_values(self, fields: dict[str, Any]) -> dict[str, Any]:
        unknown = set(fields) - set(ENTRY_FIELDS)
        if unknown:
            raise StudioError(f"unknown entry fields: {', '.join(sorted(unknown))}")
        values: dict[str, Any] = {}
        for name, value in fields.items():
            if name == "url":
                values[name] = _url(value, "url")
            else:
                values[name] = _text(value, name, allow_empty=name != "title", limit=300)
        return values

    def update_entry(self, entry_id: str, **fields: Any) -> None:
        values = self._entry_values(fields)
        self._one("SELECT id FROM entries WHERE id = ?", [entry_id], "entry")
        if not values:
            return
        # Column names come from ENTRY_FIELDS (checked above), never from the caller.
        assignments = ", ".join(f"{name} = ?" for name in values)
        with self._write() as c:
            c.execute(
                f"UPDATE entries SET {assignments}, updated_at = ? WHERE id = ?",
                (*values.values(), utc_now(), entry_id),
            )

    def create_bullet(self, entry_id: str, text: str) -> str:
        text = _text(text, "bullet")
        self._one("SELECT id FROM entries WHERE id = ?", [entry_id], "entry")
        bullet_id = _id("bul")
        now = utc_now()
        with self._write() as c:
            c.execute("INSERT INTO bullets VALUES (?,?,?,?,?)", (bullet_id, entry_id, text, now, now))
        return bullet_id

    def add_variant(
        self, bullet_id: str, text: str, *, source: str = "manual", request_id: str | None = None
    ) -> str:
        text = _text(text, "variant")
        if source not in ("manual", "ai"):
            raise StudioError("variant source must be manual or ai")
        self._one("SELECT id FROM bullets WHERE id = ?", [bullet_id], "bullet")
        existing = self.conn.execute(
            "SELECT id FROM bullet_variants WHERE bullet_id = ? AND text = ?", (bullet_id, text)
        ).fetchone()
        if existing:
            return str(existing["id"])
        variant_id = _id("var")
        with self._write() as c:
            c.execute(
                "INSERT INTO bullet_variants VALUES (?,?,?,?,?,?)",
                (variant_id, bullet_id, text, source, request_id, utc_now()),
            )
        return variant_id

    def delete_variant(self, variant_id: str) -> None:
        with self._write() as c:
            c.execute("DELETE FROM bullet_variants WHERE id = ?", (variant_id,))

    def library(self) -> list[dict[str, Any]]:
        """Every library entry with its bullets, for adding to a version."""
        entries = [dict(row) for row in self.conn.execute("SELECT * FROM entries ORDER BY kind, title")]
        for entry in entries:
            entry["bullets"] = [
                dict(row)
                for row in self.conn.execute(
                    "SELECT id, text FROM bullets WHERE entry_id = ? ORDER BY created_at, id", (entry["id"],)
                )
            ]
        return entries

    # ---------- evidence ----------

    def add_evidence(self, title: str, body: str = "", source_path: str | None = None) -> str:
        title = _text(title, "evidence title", limit=500)
        body = _text(body, "evidence", allow_empty=True, limit=5000, multiline=True)
        existing = self.conn.execute(
            "SELECT id FROM evidence_notes WHERE source_path IS ? AND title = ?", (source_path, title)
        ).fetchone()
        with self._write() as c:
            if existing:
                c.execute("UPDATE evidence_notes SET body = ? WHERE id = ?", (body, existing["id"]))
                return str(existing["id"])
            note_id = _id("ev")
            c.execute(
                "INSERT INTO evidence_notes VALUES (?,?,?,?,?)",
                (note_id, title, body, source_path, utc_now()),
            )
        return note_id

    def link_evidence(self, note_id: str, target_kind: str, target_id: str, *, linked: bool = True) -> None:
        if target_kind not in ("entry", "bullet"):
            raise StudioError("evidence links to an entry or a bullet")
        self._one("SELECT id FROM evidence_notes WHERE id = ?", [note_id], "evidence note")
        table = "entries" if target_kind == "entry" else "bullets"
        self._one(f"SELECT id FROM {table} WHERE id = ?", [target_id], target_kind)
        with self._write() as c:
            if linked:
                c.execute(
                    "INSERT OR IGNORE INTO evidence_links VALUES (?,?,?)", (note_id, target_kind, target_id)
                )
            else:
                c.execute(
                    "DELETE FROM evidence_links WHERE note_id = ? AND target_kind = ? AND target_id = ?",
                    (note_id, target_kind, target_id),
                )

    def evidence(self) -> list[dict[str, Any]]:
        return [
            dict(row) for row in self.conn.execute("SELECT * FROM evidence_notes ORDER BY source_path, title")
        ]

    def _linked_evidence(self, target_kind: str, target_id: str) -> list[dict[str, Any]]:
        return [
            dict(row)
            for row in self.conn.execute(
                "SELECT n.id, n.title, n.body, n.source_path FROM evidence_notes n"
                " JOIN evidence_links l ON l.note_id = n.id WHERE l.target_kind = ? AND l.target_id = ?"
                " ORDER BY n.title",
                (target_kind, target_id),
            )
        ]

    # ---------- resumes and versions ----------

    def create_resume(
        self,
        application_folder: str,
        *,
        header: dict[str, Any],
        skills: list[dict[str, str]] | None = None,
        template: str = "jake",
        day: date | None = None,
    ) -> tuple[str, str]:
        if not APPLICATION_FOLDER.fullmatch(application_folder):
            raise StudioError("application folder must be a path below applications/, like applications/acme")
        if template not in TEMPLATES:
            raise StudioError(f"template must be one of {', '.join(TEMPLATES)}")
        header = _header(header)
        skill_rows = _skills(skills or [])
        if self.conn.execute(
            "SELECT 1 FROM resumes WHERE application_folder = ?", (application_folder,)
        ).fetchone():
            raise StudioError(f"{application_folder} already has a resume")
        resume_id, version_id = _id("res"), _id("ver")
        now = utc_now()
        with self._write() as c:
            c.execute("INSERT INTO resumes VALUES (?,?,?,?,?)", (resume_id, application_folder, "", now, now))
            c.execute(
                "INSERT INTO versions (id, resume_id, name, template, settings, header, skills, created_at,"
                " updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    version_id,
                    resume_id,
                    version_name(day),
                    template,
                    json.dumps(settings_with_defaults()),
                    json.dumps(header),
                    json.dumps(skill_rows),
                    now,
                    now,
                ),
            )
        return resume_id, version_id

    def resumes(self) -> list[dict[str, Any]]:
        result = []
        for row in self.conn.execute("SELECT * FROM resumes ORDER BY updated_at DESC"):
            resume = dict(row)
            resume["versions"] = [
                dict(v)
                for v in self.conn.execute(
                    "SELECT id, name, template, updated_at, exported_at FROM versions WHERE resume_id = ?"
                    " ORDER BY created_at DESC, name DESC",
                    (resume["id"],),
                )
            ]
            result.append(resume)
        return result

    def new_version(self, version_id: str, *, day: date | None = None) -> str:
        """Copy a version (order, visibility, overrides, settings) under today's name."""
        source = self._one("SELECT * FROM versions WHERE id = ?", [version_id], "version")
        taken = [
            r[0]
            for r in self.conn.execute(
                "SELECT name FROM versions WHERE resume_id = ?", (source["resume_id"],)
            )
        ]
        new_id = _id("ver")
        now = utc_now()
        with self._write() as c:
            c.execute(
                "INSERT INTO versions (id, resume_id, name, template, settings, header, skills, created_at,"
                " updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    new_id,
                    source["resume_id"],
                    version_name(day, taken),
                    source["template"],
                    source["settings"],
                    source["header"],
                    source["skills"],
                    now,
                    now,
                ),
            )
            for section in c.execute(
                "SELECT * FROM version_sections WHERE version_id = ? ORDER BY position", (version_id,)
            ).fetchall():
                section_id = _id("sec")
                c.execute(
                    "INSERT INTO version_sections VALUES (?,?,?,?,?,?)",
                    (
                        section_id,
                        new_id,
                        section["title"],
                        section["kind"],
                        section["position"],
                        section["hidden"],
                    ),
                )
                c.execute(
                    "INSERT INTO version_entries SELECT ?, entry_id, position, hidden FROM version_entries"
                    " WHERE section_id = ?",
                    (section_id, section["id"]),
                )
            c.execute(
                "INSERT INTO version_bullets SELECT ?, bullet_id, position, hidden, variant_id,"
                " override_text, raw_typst FROM version_bullets WHERE version_id = ?",
                (new_id, version_id),
            )
        return new_id

    def delete_version(self, version_id: str) -> None:
        row = self._one("SELECT resume_id FROM versions WHERE id = ?", [version_id], "version")
        count = self.conn.execute("SELECT COUNT(*) FROM versions WHERE resume_id = ?", (row[0],)).fetchone()[
            0
        ]
        if count <= 1:
            raise StudioError("a resume keeps at least one version")
        with self._write() as c:
            c.execute("DELETE FROM versions WHERE id = ?", (version_id,))

    def add_section(self, version_id: str, title: str, kind: str) -> str:
        self._one("SELECT id FROM versions WHERE id = ?", [version_id], "version")
        if kind not in ENTRY_KINDS:
            raise StudioError(f"section kind must be one of {', '.join(ENTRY_KINDS)}")
        title = _text(title, "section title", limit=80)
        position = self.conn.execute(
            "SELECT COUNT(*) FROM version_sections WHERE version_id = ?", (version_id,)
        ).fetchone()[0]
        section_id = _id("sec")
        with self._write() as c:
            c.execute(
                "INSERT INTO version_sections VALUES (?,?,?,?,?,?)",
                (section_id, version_id, title, kind, position, 0),
            )
            self._touch(version_id)
        return section_id

    def add_entry_to_section(self, section_id: str, entry_id: str, *, with_bullets: bool = True) -> None:
        section = self._one("SELECT * FROM version_sections WHERE id = ?", [section_id], "section")
        self._one("SELECT id FROM entries WHERE id = ?", [entry_id], "entry")
        version_id = section["version_id"]
        if self.conn.execute(
            "SELECT 1 FROM version_entries e JOIN version_sections s ON s.id = e.section_id"
            " WHERE s.version_id = ? AND e.entry_id = ?",
            (version_id, entry_id),
        ).fetchone():
            raise StudioError("that entry is already in this version")
        position = self.conn.execute(
            "SELECT COUNT(*) FROM version_entries WHERE section_id = ?", (section_id,)
        ).fetchone()[0]
        with self._write() as c:
            c.execute("INSERT INTO version_entries VALUES (?,?,?,0)", (section_id, entry_id, position))
            if with_bullets:
                for i, bullet in enumerate(
                    c.execute(
                        "SELECT id FROM bullets WHERE entry_id = ? ORDER BY created_at, id", (entry_id,)
                    ).fetchall()
                ):
                    c.execute(
                        "INSERT OR IGNORE INTO version_bullets (version_id, bullet_id, position)"
                        " VALUES (?,?,?)",
                        (version_id, bullet["id"], i),
                    )
            self._touch(version_id)

    def add_bullet(self, version_id: str, entry_id: str, text: str) -> str:
        """A new library bullet under the entry, shown at the end of the entry in this version."""
        self._require_entry_in_version(version_id, entry_id)
        bullet_id = self.create_bullet(entry_id, text)
        position = len(self._bullet_ids(version_id, entry_id))
        with self._write() as c:
            c.execute(
                "INSERT INTO version_bullets (version_id, bullet_id, position) VALUES (?,?,?)",
                (version_id, bullet_id, position),
            )
            self._touch(version_id)
        return bullet_id

    def include_bullet(self, version_id: str, bullet_id: str) -> None:
        """Show an existing library bullet (of an entry already in the version) at the end of its entry."""
        bullet = self._one("SELECT entry_id FROM bullets WHERE id = ?", [bullet_id], "bullet")
        self._require_entry_in_version(version_id, bullet["entry_id"])
        position = len(self._bullet_ids(version_id, bullet["entry_id"]))
        with self._write() as c:
            c.execute(
                "INSERT OR IGNORE INTO version_bullets (version_id, bullet_id, position) VALUES (?,?,?)",
                (version_id, bullet_id, position),
            )
            self._touch(version_id)

    def remove_bullet(self, version_id: str, bullet_id: str) -> None:
        """Take a bullet out of this version; it stays in the library."""
        entry_id = self._version_bullet(version_id, bullet_id)["entry_id"]
        with self._write() as c:
            c.execute(
                "DELETE FROM version_bullets WHERE version_id = ? AND bullet_id = ?", (version_id, bullet_id)
            )
            self._renumber_bullets(version_id, entry_id)
            self._touch(version_id)

    def edit_bullet(self, version_id: str, bullet_id: str, text: str) -> None:
        """Change the bullet's wording in this version only."""
        text = _text(text, "bullet")
        row = self._version_bullet(version_id, bullet_id)
        override = None if text == row["library_text"] else text
        with self._write() as c:
            c.execute(
                "UPDATE version_bullets SET override_text = ?, variant_id = NULL, raw_typst = NULL"
                " WHERE version_id = ? AND bullet_id = ?",
                (override, version_id, bullet_id),
            )
            self._touch(version_id)

    def save_bullet_to_library(self, version_id: str, bullet_id: str) -> None:
        """Make this version's wording the library wording, for every resume that uses it."""
        row = self._version_bullet(version_id, bullet_id)
        text = self._effective_text(row)
        with self._write() as c:
            c.execute(
                "UPDATE bullets SET text = ?, updated_at = ? WHERE id = ?", (text, utc_now(), bullet_id)
            )
            c.execute(
                "UPDATE version_bullets SET override_text = NULL, variant_id = NULL"
                " WHERE version_id = ? AND bullet_id = ?",
                (version_id, bullet_id),
            )
            self._touch(version_id)

    def choose_variant(self, version_id: str, bullet_id: str, variant_id: str | None) -> None:
        self._version_bullet(version_id, bullet_id)
        if variant_id is not None:
            self._one(
                "SELECT id FROM bullet_variants WHERE id = ? AND bullet_id = ?",
                [variant_id, bullet_id],
                "variant",
            )
        with self._write() as c:
            c.execute(
                "UPDATE version_bullets SET variant_id = ?, override_text = NULL, raw_typst = NULL"
                " WHERE version_id = ? AND bullet_id = ?",
                (variant_id, version_id, bullet_id),
            )
            self._touch(version_id)

    def set_raw(self, version_id: str, bullet_id: str, raw: str | None) -> None:
        """Advanced: replace this bullet with Typst markup, inserted as written."""
        self._version_bullet(version_id, bullet_id)
        value = None if raw in (None, "") else _text(raw, "raw Typst")
        with self._write() as c:
            c.execute(
                "UPDATE version_bullets SET raw_typst = ? WHERE version_id = ? AND bullet_id = ?",
                (value, version_id, bullet_id),
            )
            self._touch(version_id)

    def set_hidden(self, version_id: str, kind: Kind, target_id: str, hidden: bool) -> None:
        flag = 1 if hidden else 0
        with self._write() as c:
            if kind == "section":
                cur = c.execute(
                    "UPDATE version_sections SET hidden = ? WHERE id = ? AND version_id = ?",
                    (flag, target_id, version_id),
                )
            elif kind == "entry":
                cur = c.execute(
                    "UPDATE version_entries SET hidden = ? WHERE entry_id = ? AND section_id IN"
                    " (SELECT id FROM version_sections WHERE version_id = ?)",
                    (flag, target_id, version_id),
                )
            elif kind == "bullet":
                cur = c.execute(
                    "UPDATE version_bullets SET hidden = ? WHERE version_id = ? AND bullet_id = ?",
                    (flag, version_id, target_id),
                )
            else:
                raise StudioError("kind must be section, entry or bullet")
            if cur.rowcount == 0:
                raise StudioError(f"{kind} not found in this version")
            self._touch(version_id)

    def move(self, version_id: str, kind: Kind, target_id: str, position: int) -> None:
        """Move an item to `position` (0 = first) among its siblings."""
        if kind == "section":
            siblings = [
                r[0]
                for r in self.conn.execute(
                    "SELECT id FROM version_sections WHERE version_id = ? ORDER BY position", (version_id,)
                )
            ]
        elif kind == "entry":
            section = self.conn.execute(
                "SELECT e.section_id FROM version_entries e JOIN version_sections s ON s.id = e.section_id"
                " WHERE s.version_id = ? AND e.entry_id = ?",
                (version_id, target_id),
            ).fetchone()
            if section is None:
                raise StudioError("entry not found in this version")
            siblings = [
                r[0]
                for r in self.conn.execute(
                    "SELECT entry_id FROM version_entries WHERE section_id = ? ORDER BY position",
                    (section[0],),
                )
            ]
        elif kind == "bullet":
            entry_id = self._version_bullet(version_id, target_id)["entry_id"]
            siblings = self._bullet_ids(version_id, entry_id)
        else:
            raise StudioError("kind must be section, entry or bullet")
        if target_id not in siblings:
            raise StudioError(f"{kind} not found in this version")
        siblings.remove(target_id)
        siblings.insert(max(0, min(position, len(siblings))), target_id)
        with self._write() as c:
            for i, item in enumerate(siblings):
                if kind == "section":
                    c.execute("UPDATE version_sections SET position = ? WHERE id = ?", (i, item))
                elif kind == "entry":
                    c.execute(
                        "UPDATE version_entries SET position = ? WHERE entry_id = ? AND section_id = ?",
                        (i, item, section[0]),
                    )
                else:
                    c.execute(
                        "UPDATE version_bullets SET position = ? WHERE version_id = ? AND bullet_id = ?",
                        (i, version_id, item),
                    )
            self._touch(version_id)

    def set_template(self, version_id: str, template: str) -> None:
        if template not in TEMPLATES:
            raise StudioError(f"template must be one of {', '.join(TEMPLATES)}")
        self._update_version(version_id, template=template)

    def set_settings(self, version_id: str, settings: dict[str, Any]) -> None:
        current = json.loads(
            self._one("SELECT settings FROM versions WHERE id = ?", [version_id], "version")[0]
        )
        self._update_version(version_id, settings=json.dumps(settings_with_defaults({**current, **settings})))

    def set_header(self, version_id: str, header: dict[str, Any]) -> None:
        self._update_version(version_id, header=json.dumps(_header(header)))

    def set_skills(self, version_id: str, skills: list[dict[str, str]]) -> None:
        self._update_version(version_id, skills=json.dumps(_skills(skills)))

    def set_posting(self, resume_id: str, text: str) -> None:
        text = _text(text, "posting", allow_empty=True, limit=50_000, multiline=True)
        self._one("SELECT id FROM resumes WHERE id = ?", [resume_id], "resume")
        with self._write() as c:
            c.execute(
                "UPDATE resumes SET posting_text = ?, updated_at = ? WHERE id = ?",
                (text, utc_now(), resume_id),
            )

    def record_export(self, version_id: str, source_sha256: str, pdf_sha256: str) -> None:
        with self._write() as c:
            c.execute(
                "UPDATE versions SET exported_source_sha256 = ?, exported_pdf_sha256 = ?, exported_at = ?"
                " WHERE id = ?",
                (source_sha256, pdf_sha256, utc_now(), version_id),
            )

    def _update_version(self, version_id: str, **columns: str) -> None:
        self._one("SELECT id FROM versions WHERE id = ?", [version_id], "version")
        assignments = ", ".join(f"{name} = ?" for name in columns)  # names are fixed by the callers above
        with self._write() as c:
            c.execute(
                f"UPDATE versions SET {assignments}, updated_at = ? WHERE id = ?",
                (*columns.values(), utc_now(), version_id),
            )

    # ---------- reading a version ----------

    def _version_bullet(self, version_id: str, bullet_id: str) -> sqlite3.Row:
        return self._one(
            "SELECT vb.*, b.entry_id, b.text AS library_text, v.text AS variant_text"
            " FROM version_bullets vb JOIN bullets b ON b.id = vb.bullet_id"
            " LEFT JOIN bullet_variants v ON v.id = vb.variant_id"
            " WHERE vb.version_id = ? AND vb.bullet_id = ?",
            [version_id, bullet_id],
            "bullet in this version",
        )

    @staticmethod
    def _effective_text(row: sqlite3.Row) -> str:
        return str(row["override_text"] or row["variant_text"] or row["library_text"])

    def _bullet_ids(self, version_id: str, entry_id: str) -> list[str]:
        return [
            r[0]
            for r in self.conn.execute(
                "SELECT vb.bullet_id FROM version_bullets vb JOIN bullets b ON b.id = vb.bullet_id"
                " WHERE vb.version_id = ? AND b.entry_id = ? ORDER BY vb.position, vb.bullet_id",
                (version_id, entry_id),
            )
        ]

    def _renumber_bullets(self, version_id: str, entry_id: str) -> None:
        for i, bullet_id in enumerate(self._bullet_ids(version_id, entry_id)):
            self.conn.execute(
                "UPDATE version_bullets SET position = ? WHERE version_id = ? AND bullet_id = ?",
                (i, version_id, bullet_id),
            )

    def _require_entry_in_version(self, version_id: str, entry_id: str) -> None:
        self._one(
            "SELECT 1 FROM version_entries e JOIN version_sections s ON s.id = e.section_id"
            " WHERE s.version_id = ? AND e.entry_id = ?",
            [version_id, entry_id],
            "entry in this version",
        )

    def version(self, version_id: str) -> dict[str, Any]:
        """Everything the editor shows for one version, including hidden items."""
        row = self._one(
            "SELECT v.*, r.application_folder, r.posting_text FROM versions v"
            " JOIN resumes r ON r.id = v.resume_id WHERE v.id = ?",
            [version_id],
            "version",
        )
        result: dict[str, Any] = {
            "id": row["id"],
            "resume_id": row["resume_id"],
            "application_folder": row["application_folder"],
            "posting_text": row["posting_text"],
            "name": row["name"],
            "template": row["template"],
            "settings": json.loads(row["settings"]),
            "header": json.loads(row["header"]),
            "skills": json.loads(row["skills"]),
            "exported_at": row["exported_at"],
            "exported_source_sha256": row["exported_source_sha256"],
            "exported_pdf_sha256": row["exported_pdf_sha256"],
            "updated_at": row["updated_at"],
            "sections": [],
        }
        for section in self.conn.execute(
            "SELECT * FROM version_sections WHERE version_id = ? ORDER BY position", (version_id,)
        ).fetchall():
            entries = []
            for entry in self.conn.execute(
                "SELECT e.*, ve.hidden FROM version_entries ve JOIN entries e ON e.id = ve.entry_id"
                " WHERE ve.section_id = ? ORDER BY ve.position",
                (section["id"],),
            ).fetchall():
                bullets = []
                for bullet in self.conn.execute(
                    "SELECT vb.*, b.entry_id, b.text AS library_text, v.text AS variant_text"
                    " FROM version_bullets vb JOIN bullets b ON b.id = vb.bullet_id"
                    " LEFT JOIN bullet_variants v ON v.id = vb.variant_id"
                    " WHERE vb.version_id = ? AND b.entry_id = ? ORDER BY vb.position, vb.bullet_id",
                    (version_id, entry["id"]),
                ).fetchall():
                    bullets.append(
                        {
                            "id": bullet["bullet_id"],
                            "text": self._effective_text(bullet),
                            "library_text": bullet["library_text"],
                            "override_text": bullet["override_text"],
                            "variant_id": bullet["variant_id"],
                            "raw_typst": bullet["raw_typst"],
                            "hidden": bool(bullet["hidden"]),
                            "variants": [
                                dict(v)
                                for v in self.conn.execute(
                                    "SELECT id, text, source, request_id FROM bullet_variants"
                                    " WHERE bullet_id = ? ORDER BY created_at, id",
                                    (bullet["bullet_id"],),
                                )
                            ],
                            "evidence": self._linked_evidence("bullet", bullet["bullet_id"]),
                        }
                    )
                entries.append(
                    {
                        "id": entry["id"],
                        "kind": entry["kind"],
                        **{field: entry[field] for field in ENTRY_FIELDS},
                        "hidden": bool(entry["hidden"]),
                        "evidence": self._linked_evidence("entry", entry["id"]),
                        "bullets": bullets,
                    }
                )
            result["sections"].append(
                {
                    "id": section["id"],
                    "title": section["title"],
                    "kind": section["kind"],
                    "hidden": bool(section["hidden"]),
                    "entries": entries,
                }
            )
        return result

    def render_data(self, version_id: str) -> dict[str, Any]:
        """What the template typesets: visible items only, in order."""
        version = self.version(version_id)
        sections = []
        for section in version["sections"]:
            if section["hidden"]:
                continue
            entries = []
            for entry in section["entries"]:
                if entry["hidden"]:
                    continue
                entries.append(
                    {
                        "id": entry["id"],
                        "kind": entry["kind"],
                        **{field: entry[field] or "" for field in ENTRY_FIELDS if field != "url"},
                        "url": entry["url"],
                        "bullets": [
                            {"id": b["id"], "text": b["text"], "raw": b["raw_typst"]}
                            for b in entry["bullets"]
                            if not b["hidden"]
                        ],
                    }
                )
            if entries:
                sections.append(
                    {
                        "id": section["id"],
                        "title": section["title"],
                        "kind": section["kind"],
                        "entries": entries,
                    }
                )
        return {
            "name": version["header"].get("name", ""),
            "contact": version["header"].get("contact", []),
            "date": version["name"][len("resume-") : len("resume-") + 10],
            "settings": version["settings"],
            "sections": sections,
            "skills": version["skills"],
        }
