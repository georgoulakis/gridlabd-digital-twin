-- init_db_results.sql
CREATE TABLE IF NOT EXISTS results (
    id VARCHAR(36) PRIMARY KEY,
    config_id VARCHAR(36),
    filename VARCHAR(255) NOT NULL,
    file_path VARCHAR(512) NOT NULL,
    stored_at TIMESTAMP NOT NULL,
    metadata JSONB
);

CREATE INDEX idx_results_config_id ON results(config_id);
CREATE INDEX idx_results_stored_at ON results(stored_at);

CREATE TABLE IF NOT EXISTS result_timeseries (
    id BIGSERIAL PRIMARY KEY,
    result_id VARCHAR(36) NOT NULL REFERENCES results(id) ON DELETE CASCADE,
    scenario_id VARCHAR(36),
    property TEXT NOT NULL,
    ts TIMESTAMP NOT NULL,
    value_numeric DOUBLE PRECISION,
    value_text TEXT,
    units TEXT DEFAULT 'gridlabd_native',
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX idx_result_timeseries_result_prop_ts ON result_timeseries (result_id, property, ts);
CREATE INDEX idx_result_timeseries_scenario_prop_ts ON result_timeseries (scenario_id, property, ts);