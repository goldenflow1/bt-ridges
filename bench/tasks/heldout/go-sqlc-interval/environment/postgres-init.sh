#!/bin/bash
set -euo pipefail
psql --username "$POSTGRES_USER" --dbname postgres --set ON_ERROR_STOP=1 <<'SQL'
CREATE ROLE payroll LOGIN PASSWORD 'payroll-local' NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
CREATE DATABASE payroll_dev OWNER payroll;
CREATE DATABASE payroll_test OWNER payroll;
SQL
for db in payroll_dev payroll_test; do
psql --username "$POSTGRES_USER" --dbname "$db" --set ON_ERROR_STOP=1 <<'SQL'
SET ROLE payroll;
CREATE TABLE pay_entries (id bigint PRIMARY KEY, organization_id bigint NOT NULL, posted_at timestamptz NOT NULL, gross_cents bigint NOT NULL, memo text NOT NULL);
CREATE INDEX pay_entries_period ON pay_entries(organization_id,posted_at,id);
SQL
done
touch "$PGDATA/TASK_READY"
