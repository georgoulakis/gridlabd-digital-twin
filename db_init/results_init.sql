-- db_init/results_init.sql
CREATE TABLE IF NOT EXISTS results (
  id UUID PRIMARY KEY,
  config_id UUID,
  filename TEXT NOT NULL,
  file_path TEXT NOT NULL,
  stored_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  metadata JSONB
);
