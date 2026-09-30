#!/bin/bash
set -euo pipefail
clickhouse client --user default --password "$CLICKHOUSE_PASSWORD" --multiquery <<'SQL'
CREATE DATABASE grid_dev;
CREATE DATABASE grid_test;
CREATE USER grid IDENTIFIED WITH sha256_password BY 'grid-task-local' DEFAULT DATABASE grid_dev;
GRANT SELECT, INSERT, ALTER, CREATE TABLE, DROP TABLE, TRUNCATE ON grid_dev.* TO grid;
GRANT SELECT, INSERT, ALTER, CREATE TABLE, DROP TABLE, TRUNCATE ON grid_test.* TO grid;
CREATE TABLE grid_dev.meter_events (utility String,meter_id String,observed_at DateTime64(6,'UTC'),version UInt32,state String,region String,reading Int64) ENGINE=MergeTree ORDER BY(utility,meter_id,observed_at,version);
INSERT INTO grid_dev.meter_events VALUES ('demo','M1','2026-01-01',1,'online','North',10),('demo','M1','2026-01-02',2,'offline','North',20);
SQL
touch /var/lib/clickhouse/TASK_READY
