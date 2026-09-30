#!/bin/bash
set -euo pipefail

admin() {
  clickhouse client --user default --password "$CLICKHOUSE_PASSWORD" --multiquery
}

admin <<'SQL'
CREATE DATABASE meterline_dev;
CREATE DATABASE meterline_test;
CREATE USER meterline IDENTIFIED WITH sha256_password BY 'meterline-app-4e2a9c17'
  DEFAULT DATABASE meterline_dev;
GRANT SELECT, INSERT, ALTER, CREATE TABLE, DROP TABLE, TRUNCATE, OPTIMIZE, SYSTEM MERGES
  ON meterline_dev.* TO meterline;
GRANT SELECT, INSERT, ALTER, CREATE TABLE, DROP TABLE, TRUNCATE, OPTIMIZE, SYSTEM MERGES
  ON meterline_test.* TO meterline;
GRANT SELECT(database, table, name, active, rows) ON system.parts TO meterline;

CREATE TABLE meterline_dev.events (tenant_id UInt32, happened DateTime('UTC'), event_id UInt64, status LowCardinality(String), amount Int64) ENGINE=MergeTree ORDER BY (tenant_id,happened,event_id) SETTINGS index_granularity=1024;
INSERT INTO meterline_dev.events SELECT toUInt32(intDiv(number,8192)), toDateTime('2026-01-01') + (number % 8192), number, if(number % 3 = 0, 'pending', 'settled'), toInt64(number % 17) - 8 FROM numbers(1048576);
OPTIMIZE TABLE meterline_dev.events FINAL;
SQL
touch /var/lib/clickhouse/TASK_READY
