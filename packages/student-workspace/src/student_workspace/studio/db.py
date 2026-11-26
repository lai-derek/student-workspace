"""The studio's SQLite database, inside the workspace, and its numbered migrations."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from ..state import STATE_DIR, require_workspace

DB_RELATIVE = f"{STATE_DIR}/student-workspace/studio.sqlite3"
MIGRATIONS = Path(__file__).parent / "migrations"


def connect(root: Path) -> sqlite3.Connection:
    """Open the workspace's studio database, creating or upgrading it as needed."""
    root, _metadata = require_workspace(root)
    path = root / DB_RELATIVE
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    migrate(conn)
    return conn


def migrate(conn: sqlite3.Connection) -> list[int]:
    """Apply every migration file not yet applied, each in its own transaction."""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
    )
    done = {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}
    applied = []
    for path in sorted(MIGRATIONS.glob("[0-9][0-9][0-9][0-9]_*.sql")):
        version = int(path.name[:4])
        if version in done:
            continue
        script = path.read_text(encoding="utf-8")
        conn.executescript(
            f"BEGIN;\n{script}\n"
            f"INSERT INTO schema_migrations VALUES ({version}, strftime('%Y-%m-%dT%H:%M:%SZ', 'now'));\n"
            "COMMIT;"
        )
        applied.append(version)
    return applied
