-- Cached response bodies are stored compressed. NULL means the body is stored
-- as received (rows written before this migration); 'zlib' means zlib-compressed.
ALTER TABLE raw_cache ADD COLUMN content_encoding TEXT;
