CREATE TABLE IF NOT EXISTS metadata (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS memory_entry (
  id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('confirmed', 'draft')),
  title TEXT NOT NULL,
  body TEXT NOT NULL,
  tags TEXT NOT NULL DEFAULT '',
  source TEXT NOT NULL DEFAULT '',
  shard_path TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_memory_entry_status ON memory_entry(status);
CREATE INDEX IF NOT EXISTS idx_memory_entry_created_at ON memory_entry(created_at);
