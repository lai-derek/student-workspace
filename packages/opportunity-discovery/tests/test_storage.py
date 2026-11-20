"""Storage: deduplicated observation payloads, legacy backfill, compact change details."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from opportunity_discovery.db import migrate
from opportunity_discovery.models import RunSummary
from opportunity_discovery.pipeline import Pipeline
from opportunity_discovery.registry import sync_sources_to_db
from tests.helpers import MockFetcher, make_db, source
from tests.test_pipeline import gh_payload, job

LONG_REQUIREMENTS = (
    "<h3>Requirements</h3><ul>"
    "<li>Currently pursuing a B.S. in Electrical Engineering or Computer Engineering</li>"
    "<li>Experience with embedded C, microcontrollers, oscilloscopes and logic analyzers</li>"
    "<li>Familiarity with schematic capture and PCB bring-up in a lab environment</li></ul>"
)


def _run(conn, cfg, spec, fetcher, run_id):
    Pipeline(conn, cfg, run_id, RunSummary(run_id, datetime.now(UTC).isoformat())).process_source(
        spec, fetcher
    )


def test_unchanged_observations_share_one_payload_and_view_returns_full_record(tmp_path, engine_config):
    conn = make_db(tmp_path)
    fetcher = MockFetcher()
    fetcher.add(
        "https://boards-api.greenhouse.io",
        200,
        gh_payload([job(1, "Firmware Intern", "https://boards.greenhouse.io/acme/jobs/1")]),
    )
    spec = source()
    sync_sources_to_db(conn, [spec])
    _run(conn, engine_config, spec, fetcher, "store-1")
    _run(conn, engine_config, spec, fetcher, "store-2")
    assert conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0] == 2
    assert conn.execute("SELECT COUNT(*) FROM observation_payloads").fetchone()[0] == 1
    records = [json.loads(row[0]) for row in conn.execute("SELECT record_json FROM observation_records")]
    assert len(records) == 2
    assert all(record["title"] == "Firmware Intern" for record in records)
    conn.close()


def test_legacy_observations_move_to_payloads_once(tmp_path):
    conn = make_db(tmp_path)
    sync_sources_to_db(conn, [source()])
    conn.execute("INSERT INTO collection_runs (run_id, started_at, mode) VALUES ('old', 'x', 'collect')")
    legacy = json.dumps({"title": "Legacy Intern"})
    for _ in range(2):
        conn.execute(
            "INSERT INTO observations (run_id, source_id, opportunity_id, observed_at, record_json)"
            " VALUES ('old', 'greenhouse-acmesilicon', 'opp_legacy', 'x', ?)",
            (legacy,),
        )
    conn.execute("UPDATE meta SET value='pending' WHERE key='observation_payloads_backfill'")
    conn.commit()

    migrate(conn)
    assert conn.execute("SELECT COUNT(*) FROM observation_payloads").fetchone()[0] == 1
    assert {row[0] for row in conn.execute("SELECT record_json FROM observations")} == {""}
    assert [row[0] for row in conn.execute("SELECT record_json FROM observation_records")] == [legacy, legacy]
    assert (
        conn.execute("SELECT value FROM meta WHERE key='observation_payloads_backfill'").fetchone()[0]
        == "done"
    )
    conn.close()


def test_long_text_changes_are_recorded_by_hash_and_preview(tmp_path, engine_config):
    conn = make_db(tmp_path)
    fetcher = MockFetcher()
    url = "https://boards.greenhouse.io/acme/jobs/7"
    fetcher.add(
        "https://boards-api.greenhouse.io",
        200,
        gh_payload([job(7, "Hardware Intern", url, LONG_REQUIREMENTS)]),
    )
    spec = source()
    sync_sources_to_db(conn, [spec])
    _run(conn, engine_config, spec, fetcher, "detail-1")
    changed = LONG_REQUIREMENTS.replace("in a lab environment", "in a production test lab")
    fetcher.add(
        "https://boards-api.greenhouse.io",
        200,
        gh_payload([job(7, "Hardware Intern", url, changed, location="Boston, MA")]),
    )
    _run(conn, engine_config, spec, fetcher, "detail-2")
    details = {
        row[0]: json.loads(row[1])
        for row in conn.execute(
            "SELECT change_type, changed_fields_json FROM changes WHERE run_id='detail-2'"
        )
    }
    requirement = details["requirements-changed"]["requirements_text"]
    assert set(requirement["new"]) == {"sha256", "chars", "preview"}
    assert requirement["new"]["chars"] > 160
    assert requirement["old"]["sha256"] != requirement["new"]["sha256"]
    assert details["location-changed"]["location_text"] == {"old": "Austin, TX", "new": "Boston, MA"}
    conn.close()
