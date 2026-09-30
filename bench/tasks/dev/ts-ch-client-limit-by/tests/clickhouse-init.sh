#!/bin/bash
set -euo pipefail
clickhouse client --user default --password "$CLICKHOUSE_PASSWORD" --multiquery <<'SQL'
CREATE DATABASE meterline_dev;
CREATE DATABASE meterline_test;
CREATE USER meterline IDENTIFIED WITH sha256_password BY 'meterline-app-4e2a9c17' DEFAULT DATABASE meterline_dev;
GRANT SELECT, INSERT, CREATE TABLE, DROP TABLE, TRUNCATE ON meterline_dev.* TO meterline;
GRANT SELECT, INSERT, CREATE TABLE, DROP TABLE, TRUNCATE ON meterline_test.* TO meterline;
SQL
touch /var/lib/clickhouse/TASK_READY
