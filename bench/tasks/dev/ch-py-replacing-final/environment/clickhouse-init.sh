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

CREATE TABLE meterline_dev.account_balances
(
    tenant_id     LowCardinality(String),
    account_id    UInt64,
    currency      LowCardinality(String),
    balance_minor Int64,
    status        Enum8('active' = 1, 'frozen' = 2, 'closed' = 3),
    revision      UInt64,
    updated_at    DateTime64(3, 'UTC')
)
ENGINE = ReplacingMergeTree(revision)
ORDER BY (tenant_id, account_id);

INSERT INTO meterline_dev.account_balances VALUES
  ('northwind', 1001, 'EUR', 50000, 'active', 1, '2026-04-01 09:00:00.000'),
  ('northwind', 1001, 'EUR', 41250, 'active', 2, '2026-04-03 14:12:09.412'),
  ('northwind', 1002, 'EUR', 12000, 'active', 1, '2026-04-01 09:05:00.000'),
  ('northwind', 1003, 'GBP', 30000, 'active', 1, '2026-04-02 10:00:00.000'),
  ('northwind', 1004, 'EUR',  8800, 'active', 1, '2026-04-02 11:30:00.000'),
  ('northwind', 1004, 'EUR',  8800, 'frozen', 2, '2026-04-05 16:45:31.007'),
  ('northwind', 1005, 'USD', 15075, 'active', 1, '2026-04-04 08:20:00.000'),
  ('northwind', 1006, 'GBP',     0, 'closed', 1, '2026-04-04 12:00:00.000');

INSERT INTO meterline_dev.account_balances VALUES
  ('bluepeak', 2001, 'USD', 72000, 'active', 1, '2026-04-01 07:00:00.000'),
  ('bluepeak', 2002, 'USD',  4410, 'active', 1, '2026-04-02 07:00:00.000');

OPTIMIZE TABLE meterline_dev.account_balances FINAL;
SQL

touch /var/lib/clickhouse/TASK_READY
