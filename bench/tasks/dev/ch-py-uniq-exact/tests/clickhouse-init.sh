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

CREATE TABLE meterline_dev.visits (tenant String, visitor Nullable(UInt64), happened DateTime('UTC')) ENGINE=MergeTree ORDER BY (tenant, happened);
INSERT INTO meterline_dev.visits SELECT 'demo', number * 7919 + 13, toDateTime('2026-01-01 12:00:00') FROM numbers(180013);
SQL
touch /var/lib/clickhouse/TASK_READY
