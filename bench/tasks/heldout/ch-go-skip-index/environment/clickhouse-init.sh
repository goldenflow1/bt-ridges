#!/bin/bash
set -euo pipefail
clickhouse client --user default --password "$CLICKHOUSE_PASSWORD" --multiquery <<'SQL'
CREATE DATABASE buildvault_dev;
CREATE DATABASE buildvault_test;
CREATE USER buildvault IDENTIFIED WITH sha256_password BY 'buildvault-task-local' DEFAULT DATABASE buildvault_dev;
GRANT SELECT, INSERT, ALTER, CREATE TABLE, DROP TABLE, TRUNCATE ON buildvault_dev.* TO buildvault;
GRANT SELECT, INSERT, ALTER, CREATE TABLE, DROP TABLE, TRUNCATE ON buildvault_test.* TO buildvault;
GRANT SELECT ON system.tables TO buildvault;
GRANT SELECT ON system.columns TO buildvault;
GRANT SELECT ON system.data_skipping_indices TO buildvault;
SQL
touch /var/lib/clickhouse/TASK_READY
