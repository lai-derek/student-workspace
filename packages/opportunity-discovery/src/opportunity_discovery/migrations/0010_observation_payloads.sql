-- Observation snapshots are content-addressed: each distinct record JSON is
-- stored once in observation_payloads, and each per-run observation row keeps
-- its run, source, opportunity and time plus the payload hash. Most records are
-- unchanged between runs, so this removes most observation storage growth.
-- Rows written before this migration keep record_json until the one-time
-- backfill in db.py moves them. The observation_records view returns the full
-- record JSON for every observation, old or new.
CREATE TABLE IF NOT EXISTS observation_payloads (
    payload_hash TEXT PRIMARY KEY,
    record_json  TEXT NOT NULL
);
ALTER TABLE observations ADD COLUMN payload_hash TEXT;
CREATE VIEW IF NOT EXISTS observation_records AS
SELECT o.observation_id, o.run_id, o.source_id, o.opportunity_id, o.observed_at,
       COALESCE(p.record_json, o.record_json) AS record_json
FROM observations o
LEFT JOIN observation_payloads p ON p.payload_hash = o.payload_hash;
INSERT OR REPLACE INTO meta (key, value) VALUES ('observation_payloads_backfill', 'pending');
