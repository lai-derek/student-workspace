"""Extraction cache: hits return exactly what extraction returns; code changes invalidate."""

from __future__ import annotations

from datetime import UTC, datetime

from opportunity_discovery import facts_cache
from opportunity_discovery.extraction import _extract_description, extract_description
from opportunity_discovery.models import RunSummary
from opportunity_discovery.pipeline import Pipeline
from opportunity_discovery.registry import sync_sources_to_db
from tests.helpers import MockFetcher, make_db, source
from tests.test_pipeline import gh_payload, job

CONTENT = (
    "&lt;h3&gt;Requirements&lt;/h3&gt;&lt;ul&gt;"
    "&lt;li&gt;Currently pursuing a B.S. in Electrical Engineering, graduating between "
    "December 2027 and June 2028&lt;/li&gt;"
    "&lt;li&gt;Must be authorized to work in the U.S. without sponsorship&lt;/li&gt;"
    "&lt;li&gt;2+ years of experience with C&lt;/li&gt;&lt;/ul&gt;"
    "&lt;p&gt;Application deadline: January 15, 2027. Paid internship, $40/hour.&lt;/p&gt;"
)


def test_cache_hit_equals_uncached_extraction(tmp_path):
    conn = make_db(tmp_path)
    expected = _extract_description(CONTENT, qualification_sections="Minimum qualifications: GPA 3.0")
    cache = facts_cache.FactsCache(conn)
    with facts_cache.using(cache):
        first = extract_description(CONTENT, qualification_sections="Minimum qualifications: GPA 3.0")
        second = extract_description(CONTENT, qualification_sections="Minimum qualifications: GPA 3.0")
    assert (cache.misses, cache.hits) == (1, 1)
    assert first == expected
    assert second == expected
    conn.close()


def test_cache_is_inactive_outside_collection(tmp_path):
    conn = make_db(tmp_path)
    assert facts_cache.active() is None
    extract_description(CONTENT)
    assert conn.execute("SELECT COUNT(*) FROM extraction_cache").fetchone()[0] == 0
    conn.close()


def test_code_change_invalidates_cache(tmp_path, monkeypatch):
    conn = make_db(tmp_path)
    cache = facts_cache.FactsCache(conn)
    with facts_cache.using(cache):
        extract_description(CONTENT)
    conn.commit()
    assert conn.execute("SELECT COUNT(*) FROM extraction_cache").fetchone()[0] == 1
    monkeypatch.setattr(facts_cache, "code_version", lambda: "different-engine-code")
    facts_cache.FactsCache(conn)
    assert conn.execute("SELECT COUNT(*) FROM extraction_cache").fetchone()[0] == 0
    conn.close()


def test_unchanged_postings_are_not_extracted_again(tmp_path, engine_config):
    conn = make_db(tmp_path)
    fetcher = MockFetcher()
    fetcher.add(
        "https://boards-api.greenhouse.io",
        200,
        gh_payload(
            [
                job(1, "Firmware Intern", "https://boards.greenhouse.io/acme/jobs/1", content=CONTENT),
                job(2, "Hardware Intern", "https://boards.greenhouse.io/acme/jobs/2"),
            ]
        ),
    )
    spec = source()
    sync_sources_to_db(conn, [spec])

    def run(run_id: str) -> tuple[Pipeline, list[tuple]]:
        pipeline = Pipeline(conn, engine_config, run_id, RunSummary(run_id, datetime.now(UTC).isoformat()))
        pipeline.process_source(spec, fetcher)
        rows = conn.execute(
            "SELECT opportunity_id, requirements_text, source_constraints_json, routing_state"
            " FROM opportunities ORDER BY opportunity_id"
        ).fetchall()
        return pipeline, [tuple(row) for row in rows]

    first, rows_first = run("cache-1")
    second, rows_second = run("cache-2")
    assert first._facts_cache.misses == 2
    assert (second._facts_cache.hits, second._facts_cache.misses) == (2, 0)
    assert rows_second == rows_first
    conn.close()
