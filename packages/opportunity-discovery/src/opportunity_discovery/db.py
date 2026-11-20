"""SQLite storage: connections, versioned idempotent migrations."""

from __future__ import annotations

import hashlib
import importlib.resources
import json
import sqlite3
import zlib
from pathlib import Path

_MIGRATIONS_PACKAGE = "opportunity_discovery.migrations"


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def _available_migrations() -> list[tuple[int, str, str]]:
    """Return sorted (version, filename, sql) from the packaged migrations dir."""
    files: list[tuple[int, str]] = []
    pkg_files = importlib.resources.files(_MIGRATIONS_PACKAGE)
    for entry in pkg_files.iterdir():
        name = getattr(entry, "name", "")
        if name.endswith(".sql"):
            try:
                version = int(name.split("_", 1)[0])
            except ValueError as exc:
                raise RuntimeError(f"bad migration filename: {name}") from exc
            files.append((version, name))
    out: list[tuple[int, str, str]] = []
    for version, name in sorted(files):
        sql = (pkg_files / name).read_text(encoding="utf-8")
        out.append((version, name, sql))
    return out


def migrate(conn: sqlite3.Connection) -> list[int]:
    """Apply pending migrations. Idempotent. Returns applied versions."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
        )
        """
    )
    conn.commit()
    applied = {row["version"] for row in conn.execute("SELECT version FROM schema_migrations")}
    newly_applied: list[int] = []
    for version, name, sql in _available_migrations():
        if version in applied:
            continue
        with conn:
            conn.executescript(sql)
            conn.execute("INSERT INTO schema_migrations (version, name) VALUES (?, ?)", (version, name))
        newly_applied.append(version)
    _backfill_career_profiles(conn)
    _backfill_observation_payloads(conn)
    _compress_legacy_cache_rows(conn)
    return newly_applied


def payload_hash(record_json: str) -> str:
    return hashlib.sha256(record_json.encode("utf-8")).hexdigest()


def store_observation_payload(conn: sqlite3.Connection, record_json: str) -> str:
    """Store one observation record JSON once; return its content hash."""
    digest = payload_hash(record_json)
    conn.execute(
        "INSERT OR IGNORE INTO observation_payloads (payload_hash, record_json) VALUES (?, ?)",
        (digest, record_json),
    )
    return digest


def _backfill_observation_payloads(conn: sqlite3.Connection, batch: int = 2000) -> None:
    """Move pre-0010 observation JSON into content-addressed payloads, once."""
    try:
        row = conn.execute("SELECT value FROM meta WHERE key='observation_payloads_backfill'").fetchone()
    except sqlite3.OperationalError:
        return
    if row is None or row[0] != "pending":
        return
    last_id = 0
    while True:
        rows = conn.execute(
            "SELECT observation_id, record_json FROM observations"
            " WHERE observation_id > ? AND payload_hash IS NULL ORDER BY observation_id LIMIT ?",
            (last_id, batch),
        ).fetchall()
        if not rows:
            break
        for observation_id, record_json in rows:
            digest = store_observation_payload(conn, record_json)
            conn.execute(
                "UPDATE observations SET payload_hash=?, record_json='' WHERE observation_id=?",
                (digest, observation_id),
            )
        last_id = rows[-1][0]
        conn.commit()
    conn.execute("UPDATE meta SET value='done' WHERE key='observation_payloads_backfill'")
    conn.commit()


def _compress_legacy_cache_rows(conn: sqlite3.Connection) -> None:
    """Compress cached bodies stored as received before migration 0009."""
    columns = {row[1] for row in conn.execute("PRAGMA table_info(raw_cache)")}
    if "content_encoding" not in columns:
        return
    rows = conn.execute(
        "SELECT url, content FROM raw_cache WHERE content_encoding IS NULL AND content IS NOT NULL"
    ).fetchall()
    for url, content in rows:
        conn.execute(
            "UPDATE raw_cache SET content=?, content_encoding='zlib' WHERE url=?",
            (zlib.compress(bytes(content), 6), url),
        )
    if rows:
        conn.commit()


def _backfill_career_profiles(conn: sqlite3.Connection) -> None:
    """Normalize pre-0005 rows once without changing their stable identity."""
    columns = {row[1] for row in conn.execute("PRAGMA table_info(opportunities)")}
    if "profile_routes_json" not in columns:
        return
    rows = conn.execute(
        "SELECT opportunity_id, title, canonical_url, description_excerpt, employment_type,"
        " requirements_text"
        " FROM opportunities WHERE profile_routes_json='{}' OR profile_routes_json IS NULL"
    ).fetchall()
    if not rows:
        return

    from . import constants as c
    from .models import RawOpportunity
    from .routing import normalize_routing_fields, route_profiles

    for row in rows:
        fields = normalize_routing_fields(
            RawOpportunity(
                title=row[1] or "",
                canonical_url=row[2] or "",
                description_excerpt=row[3],
                employment_type=row[4],
                requirements_text=row[5],
            )
        )
        routes = route_profiles(fields)
        active = routes[c.PROFILE_STUDENT]
        conn.execute(
            "UPDATE opportunities SET engagement_type=?, career_stage=?, required_degree=?,"
            " preferred_degree=?, experience_requirement_text=?, experience_min_years=?,"
            " experience_max_years=?, active_profile=?, routing_state=?, eligibility_confidence=?,"
            " profile_routes_json=?, routing_reason_codes_json=? WHERE opportunity_id=?",
            (
                fields["engagement_type"],
                fields["career_stage"],
                fields["required_degree"],
                fields["preferred_degree"],
                fields["experience_requirement_text"],
                fields["experience_min_years"],
                fields["experience_max_years"],
                c.PROFILE_STUDENT,
                active.state,
                active.confidence,
                json.dumps({name: decision.to_dict() for name, decision in routes.items()}, sort_keys=True),
                json.dumps(active.reason_codes),
                row[0],
            ),
        )
    conn.commit()


def current_version(conn: sqlite3.Connection) -> int:
    try:
        row = conn.execute("SELECT MAX(version) AS v FROM schema_migrations").fetchone()
    except sqlite3.OperationalError:
        return 0
    return int(row["v"] or 0)
