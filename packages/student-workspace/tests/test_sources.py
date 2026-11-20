"""The shared source registry."""

import json
import sqlite3
import zipfile

import pytest
from tests.test_workspace import fake_tool

from student_workspace.recovery import audit_workspace, backup_workspace, restore_workspace_backup
from student_workspace.sources import import_source, read_source_manifest, register_source
from student_workspace.state import STATE_DIR, WorkspaceStateError
from student_workspace.tools import register_tool
from student_workspace.workspace import initialize_workspace


def test_import_is_content_addressed_and_registered_once(tmp_path):
    root = tmp_path / "workspace"
    initialize_workspace(root)
    original = tmp_path / "My Resume (final).pdf"
    original.write_bytes(b"%PDF synthetic\r\n")

    first = import_source(root, original, folder="originals", custom={"tool": "test"})
    second = import_source(root, original, folder="originals")

    assert first == {"stored_path": first["stored_path"], "reused": False}
    assert second == {"stored_path": first["stored_path"], "reused": True}
    assert first["stored_path"].startswith("sources/originals/")
    assert first["stored_path"].endswith("-My-Resume--final-.pdf")
    assert (root / first["stored_path"]).read_bytes() == b"%PDF synthetic\r\n"
    manifest = read_source_manifest(root)
    assert [row["stored_path"] for row in manifest["imports"]] == [first["stored_path"]]
    assert manifest["imports"][0]["custom"] == {"tool": "test"}
    assert audit_workspace(root).errors == []


def test_register_existing_file_and_reject_unsafe_paths(tmp_path):
    root = tmp_path / "workspace"
    initialize_workspace(root)
    note = root / "sources" / "markdown" / "note.md"
    note.parent.mkdir(parents=True)
    note.write_text("# Note\n", encoding="utf-8")
    assert register_source(root, "sources/markdown/note.md")["reused"] is False
    assert register_source(root, "sources/markdown/note.md")["reused"] is True
    for bad in ("../outside.md", "sources\note.md", "inbox/note.md", "sources/missing.md"):
        with pytest.raises(WorkspaceStateError):
            register_source(root, bad)
    with pytest.raises(WorkspaceStateError, match="one portable path segment"):
        import_source(root, note, folder="../escape")
    note.write_text("# Changed\n", encoding="utf-8")
    with pytest.raises(WorkspaceStateError, match="different content"):
        register_source(root, "sources/markdown/note.md")


def test_held_lock_blocks_concurrent_registration(tmp_path):
    root = tmp_path / "workspace"
    initialize_workspace(root)
    (root / STATE_DIR / "source-manifest.lock").write_text("123", encoding="utf-8")
    note = tmp_path / "note.txt"
    note.write_text("x", encoding="utf-8")
    with pytest.raises(WorkspaceStateError, match="locked"):
        import_source(root, note, folder="originals")
    manifest = json.loads((root / STATE_DIR / "source-manifest.json").read_text(encoding="utf-8"))
    assert manifest["imports"] == []


def test_sqlite_backup_is_consistent_and_restore_drops_stale_journals(tmp_path):
    root = tmp_path / "workspace"
    initialize_workspace(root)
    tool = fake_tool(tmp_path)
    manifest_path = tool / "student-workspace-tool.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["sqlite_files"] = ["data/app.sqlite"]
    manifest_path.write_text(json.dumps(manifest))
    register_tool(root, tool)
    database = root / "data" / "app.sqlite"
    database.parent.mkdir()
    writer = sqlite3.connect(database)
    writer.execute("PRAGMA journal_mode=WAL")
    writer.execute("CREATE TABLE notes (body TEXT)")
    writer.execute("INSERT INTO notes VALUES ('committed in WAL')")
    writer.commit()  # Left open: the row lives only in the -wal file until a checkpoint.

    archive = tmp_path / "backup.zip"
    backup_workspace(root, archive, kind="full")
    with zipfile.ZipFile(archive) as saved:
        names = saved.namelist()
        assert "data/app.sqlite" in names
        assert not any(name.endswith(("-wal", "-shm")) for name in names)
        (tmp_path / "copy.sqlite").write_bytes(saved.read("data/app.sqlite"))
    with sqlite3.connect(tmp_path / "copy.sqlite") as copy:
        assert copy.execute("SELECT body FROM notes").fetchall() == [("committed in WAL",)]

    writer.execute("INSERT INTO notes VALUES ('after backup')")
    writer.commit()
    writer.close()
    restore_workspace_backup(root, archive)
    assert not (root / "data" / "app.sqlite-wal").exists()
    with sqlite3.connect(database) as restored:
        assert restored.execute("SELECT body FROM notes").fetchall() == [("committed in WAL",)]
    assert audit_workspace(root).errors == []
    database.write_bytes(b"SQLite format 3\x00" + b"\x00" * 200)
    assert any(finding.rule == "sqlite-integrity" for finding in audit_workspace(root).errors)
