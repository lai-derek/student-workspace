-- Reusable description extraction results (see facts_cache.py). Derived data
-- only: dropping this table changes nothing but the next run's duration.
CREATE TABLE IF NOT EXISTS extraction_cache (
    cache_key    TEXT PRIMARY KEY,
    code_version TEXT NOT NULL,
    facts        BLOB NOT NULL,
    last_used    TEXT NOT NULL
);
