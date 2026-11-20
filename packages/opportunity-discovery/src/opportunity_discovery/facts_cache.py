"""Persistent cache of description extraction results.

Most postings are unchanged between runs, and extracting facts from their text
is the largest remaining per-record cost. Results are keyed by the exact input
text and a fingerprint of the engine source, so any code change invalidates the
whole cache and a changed posting is always extracted again. A cache hit returns
exactly what extraction would have returned.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import zlib
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

UNUSED_RETENTION_DAYS = 30

_ACTIVE: ContextVar[FactsCache | None] = ContextVar("opdisc_facts_cache", default=None)


@lru_cache(maxsize=1)
def code_version() -> str:
    """Fingerprint of every Python module in this package."""
    digest = hashlib.sha256()
    package = Path(__file__).resolve().parent
    for path in sorted(package.rglob("*.py")):
        digest.update(path.relative_to(package).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


class FactsCache:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.version = code_version()
        self.hits = 0
        self.misses = 0
        cutoff = (datetime.now(UTC) - timedelta(days=UNUSED_RETENTION_DAYS)).isoformat()
        conn.execute(
            "DELETE FROM extraction_cache WHERE code_version != ? OR last_used < ?",
            (self.version, cutoff),
        )

    def key(self, content: str, qualification_sections: str) -> str:
        digest = hashlib.sha256()
        for part in (self.version, content, qualification_sections):
            digest.update(part.encode("utf-8", "surrogatepass"))
            digest.update(b"\0")
        return digest.hexdigest()

    def get(self, key: str) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT facts FROM extraction_cache WHERE cache_key = ?", (key,)).fetchone()
        if row is None:
            self.misses += 1
            return None
        self.hits += 1
        self.conn.execute(
            "UPDATE extraction_cache SET last_used = ? WHERE cache_key = ?",
            (datetime.now(UTC).isoformat(), key),
        )
        facts: dict[str, Any] = json.loads(zlib.decompress(row[0]))
        return facts

    def put(self, key: str, facts: dict[str, Any]) -> None:
        payload = zlib.compress(json.dumps(facts, sort_keys=True).encode("utf-8"), 6)
        self.conn.execute(
            "INSERT OR REPLACE INTO extraction_cache (cache_key, code_version, facts, last_used)"
            " VALUES (?, ?, ?, ?)",
            (key, self.version, payload, datetime.now(UTC).isoformat()),
        )


def active() -> FactsCache | None:
    return _ACTIVE.get()


@contextmanager
def using(cache: FactsCache) -> Iterator[FactsCache]:
    token = _ACTIVE.set(cache)
    try:
        yield cache
    finally:
        _ACTIVE.reset(token)
