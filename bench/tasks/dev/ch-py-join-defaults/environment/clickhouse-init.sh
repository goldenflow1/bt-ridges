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

CREATE TABLE meterline_dev.events (tenant String, event_id UInt64, device String) ENGINE=MergeTree ORDER BY (tenant,event_id);
CREATE TABLE meterline_dev.devices (tenant String, device String, device_id UInt64, label String, enabled UInt8) ENGINE=MergeTree ORDER BY (tenant,device);
INSERT INTO meterline_dev.devices VALUES ('demo', 'registered-zero', 0, '', 1), ('demo', 'retired', 7, 'old', 0);
INSERT INTO meterline_dev.events VALUES ('demo', 1, 'registered-zero'), ('demo', 2, 'unknown'), ('demo', 3, 'retired');
SQL
touch /var/lib/clickhouse/TASK_READY
