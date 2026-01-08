-- init_db_configs.sql
CREATE TABLE IF NOT EXISTS configs (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP NOT NULL,
    config JSONB NOT NULL,
    version INTEGER DEFAULT 1
);

CREATE INDEX idx_configs_name ON configs(name);
CREATE INDEX idx_configs_created_at ON configs(created_at);