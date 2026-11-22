"""Explicit retention pruning. Defaults to dry-run; durable history is kept."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta


def _cutoff(days: int) -> str:
    return (datetime.now(UTC) - timedelta(days=days)).isoformat()


# A run row is removable only when no history row still references it. Source
# checks pruned in the same pass (older than the check cutoff) do not count.
_UNREFERENCED_RUN = (
    "started_at < ?"
    " AND NOT EXISTS (SELECT 1 FROM observations o WHERE o.run_id = collection_runs.run_id)"
    " AND NOT EXISTS (SELECT 1 FROM changes ch WHERE ch.run_id = collection_runs.run_id)"
    " AND NOT EXISTS (SELECT 1 FROM source_checks sc"
    " WHERE sc.run_id = collection_runs.run_id AND sc.checked_at >= ?)"
)


def plan_prune(
    conn: sqlite3.Connection, *, cache_days: int, log_days: int, check_days: int
) -> list[dict[str, object]]:
    # Order matters: source checks go before the runs they reference.
    plans = [
        ("raw_cache", "expires_at < ?", (_cutoff(0),)),
        ("raw_cache", "fetched_at < ? AND expires_at < ?", (_cutoff(cache_days), _cutoff(cache_days))),
        ("source_checks", "checked_at < ?", (_cutoff(check_days),)),
        ("collection_runs", _UNREFERENCED_RUN, (_cutoff(max(log_days * 30, 90)), _cutoff(check_days))),
    ]
    out: list[dict[str, object]] = []
    for table, where, params in plans:
        row = conn.execute(
            f"SELECT COUNT(*) AS n FROM {table} WHERE {where}",
            tuple(params),
        ).fetchone()
        if row["n"]:
            out.append({"table": table, "where": where, "params": list(params), "rows": int(row["n"])})
    return out


def apply_prune(conn: sqlite3.Connection, plans: list[dict[str, object]]) -> int:
    deleted = 0
    for plan in plans:
        cur = conn.execute(
            f"DELETE FROM {plan['table']} WHERE {plan['where']}",
            tuple(plan["params"]),  # type: ignore[arg-type]
        )
        deleted += cur.rowcount
    conn.commit()
    return deleted
