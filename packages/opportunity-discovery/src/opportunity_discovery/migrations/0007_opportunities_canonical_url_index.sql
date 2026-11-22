-- Duplicate reconciliation looks up opportunities by normalized URL once per
-- ingested record. Without this index each lookup scans the whole table, so run
-- time grew with history. Access path only; identities and merge rules are unchanged.
CREATE INDEX IF NOT EXISTS idx_opportunities_canonical_url ON opportunities(canonical_url);
