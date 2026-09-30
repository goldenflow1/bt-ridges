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

CREATE TABLE meterline_dev.events (tenant String, happened DateTime64(3, 'UTC')) ENGINE=MergeTree ORDER BY (tenant,happened);
INSERT INTO meterline_dev.events VALUES ('demo', '2026-03-08 05:00:00.000'), ('demo', '2026-03-09 03:59:59.999'), ('demo', '2026-03-09 04:00:00.000');
SQL
touch /var/lib/clickhouse/TASK_READY
