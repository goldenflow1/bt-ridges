#!/bin/bash
set -euo pipefail
psql --username "$POSTGRES_USER" --dbname postgres --set ON_ERROR_STOP=1 <<'SQL'
CREATE ROLE practice LOGIN PASSWORD 'practice-local' NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
CREATE DATABASE practice OWNER practice;
SQL
psql --username "$POSTGRES_USER" --dbname practice --set ON_ERROR_STOP=1 <<'SQL'
SET ROLE practice;
CREATE TABLE jobs (id integer PRIMARY KEY, tenant_id integer NOT NULL, status text NOT NULL, created_at timestamptz NOT NULL, deleted_at timestamptz, payload text NOT NULL);
INSERT INTO jobs SELECT x, x % 100, 'ready', '2026-01-01'::timestamptz + x*interval '1 second', NULL, repeat('payload',40) FROM generate_series(1,100000) x;
ANALYZE jobs;
SQL
touch "$PGDATA/TASK_READY"
