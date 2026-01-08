-- db_init/configs_init.sql
CREATE TABLE IF NOT EXISTS configs (
  id UUID PRIMARY KEY,
  name TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  config JSONB NOT NULL,
  version INTEGER DEFAULT 1
);
