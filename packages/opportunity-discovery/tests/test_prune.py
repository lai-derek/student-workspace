"""Retention pruning applies without breaking history references."""

from __future__ import annotations

from opportunity_discovery.prune import apply_prune, plan_prune
from opportunity_discovery.registry import sync_sources_to_db
from tests.helpers import make_db, source

OLD = "2020-01-01T00:00:00+00:00"


def test_apply_prune_removes_expired_rows_and_keeps_referenced_history(tmp_path):
    conn = make_db(tmp_path)
    sync_sources_to_db(conn, [source()])
    conn.execute(
        "INSERT INTO raw_cache (url, fetched_at, status, content, expires_at) VALUES (?, ?, 200, ?, ?)",
        ("https://example.test/old", OLD, b"x", OLD),
    )
    for run_id in ("run-with-history", "run-empty"):
        conn.execute(
            "INSERT INTO collection_runs (run_id, started_at, mode) VALUES (?, ?, 'collect')", (run_id, OLD)
        )
    conn.execute(
        "INSERT INTO observations (run_id, source_id, opportunity_id, observed_at, record_json)"
        " VALUES ('run-with-history', 'greenhouse-acmesilicon', 'opp_x', ?, '{}')",
        (OLD,),
    )
    conn.execute(
        "INSERT INTO source_checks (source_id, run_id, checked_at, state)"
        " VALUES ('greenhouse-acmesilicon', 'run-empty', ?, 'healthy')",
        (OLD,),
    )
    conn.commit()

    plans = plan_prune(conn, cache_days=7, log_days=14, check_days=180)
    assert {p["table"] for p in plans} == {"raw_cache", "source_checks", "collection_runs"}
    assert apply_prune(conn, plans) > 0
    runs = {row[0] for row in conn.execute("SELECT run_id FROM collection_runs")}
    assert runs == {"run-with-history"}
    assert conn.execute("SELECT COUNT(*) FROM raw_cache").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM source_checks").fetchone()[0] == 0
    conn.close()
