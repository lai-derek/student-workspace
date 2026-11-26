-- Application Studio schema, version 1.
-- The library (entries, bullets, variants, evidence) is shared by every resume.
-- A version selects library items, orders and hides them, and can override a
-- bullet's text, pick one of its variants, or replace it with raw Typst.

CREATE TABLE entries (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL CHECK (kind IN ('education', 'experience', 'project', 'leadership', 'other')),
    title TEXT NOT NULL,
    url TEXT,
    tech TEXT NOT NULL DEFAULT '',
    details TEXT NOT NULL DEFAULT '',
    subtitle TEXT NOT NULL DEFAULT '',
    location TEXT NOT NULL DEFAULT '',
    dates TEXT NOT NULL DEFAULT '',
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE bullets (
    id TEXT PRIMARY KEY,
    entry_id TEXT NOT NULL REFERENCES entries (id) ON DELETE CASCADE,
    text TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX bullets_entry ON bullets (entry_id);

CREATE TABLE bullet_variants (
    id TEXT PRIMARY KEY,
    bullet_id TEXT NOT NULL REFERENCES bullets (id) ON DELETE CASCADE,
    text TEXT NOT NULL,
    source TEXT NOT NULL CHECK (source IN ('manual', 'ai')),
    request_id TEXT,
    created_at TEXT NOT NULL,
    UNIQUE (bullet_id, text)
);

CREATE TABLE evidence_notes (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    body TEXT NOT NULL DEFAULT '',
    source_path TEXT,
    created_at TEXT NOT NULL,
    UNIQUE (source_path, title)
);

CREATE TABLE evidence_links (
    note_id TEXT NOT NULL REFERENCES evidence_notes (id) ON DELETE CASCADE,
    target_kind TEXT NOT NULL CHECK (target_kind IN ('entry', 'bullet')),
    target_id TEXT NOT NULL,
    PRIMARY KEY (note_id, target_kind, target_id)
);

CREATE TABLE resumes (
    id TEXT PRIMARY KEY,
    application_folder TEXT NOT NULL UNIQUE,
    posting_text TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE versions (
    id TEXT PRIMARY KEY,
    resume_id TEXT NOT NULL REFERENCES resumes (id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    template TEXT NOT NULL DEFAULT 'jake',
    settings TEXT NOT NULL DEFAULT '{}',
    header TEXT NOT NULL DEFAULT '{}',
    skills TEXT NOT NULL DEFAULT '[]',
    exported_source_sha256 TEXT,
    exported_pdf_sha256 TEXT,
    exported_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (resume_id, name)
);

CREATE TABLE version_sections (
    id TEXT PRIMARY KEY,
    version_id TEXT NOT NULL REFERENCES versions (id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    kind TEXT NOT NULL,
    position INTEGER NOT NULL,
    hidden INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX version_sections_version ON version_sections (version_id);

CREATE TABLE version_entries (
    section_id TEXT NOT NULL REFERENCES version_sections (id) ON DELETE CASCADE,
    entry_id TEXT NOT NULL REFERENCES entries (id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    hidden INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (section_id, entry_id)
);

CREATE TABLE version_bullets (
    version_id TEXT NOT NULL REFERENCES versions (id) ON DELETE CASCADE,
    bullet_id TEXT NOT NULL REFERENCES bullets (id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    hidden INTEGER NOT NULL DEFAULT 0,
    variant_id TEXT REFERENCES bullet_variants (id) ON DELETE SET NULL,
    override_text TEXT,
    raw_typst TEXT,
    PRIMARY KEY (version_id, bullet_id)
);
