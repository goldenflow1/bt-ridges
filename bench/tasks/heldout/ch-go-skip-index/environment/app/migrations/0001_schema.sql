-- +migrate Up
CREATE TABLE IF NOT EXISTS builds (
  build_id UInt64, project_id UInt16, job_id String, started_at DateTime64(3,'UTC'), outcome String
) ENGINE=MergeTree ORDER BY (project_id,started_at) SETTINGS index_granularity=8192;
-- +migrate Down
DROP TABLE IF EXISTS builds;
