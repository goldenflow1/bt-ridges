#!/bin/bash
set -euo pipefail
psql --username "$POSTGRES_USER" --dbname postgres --set ON_ERROR_STOP=1 <<'SQL'
CREATE ROLE practice LOGIN PASSWORD 'practice-local' NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
CREATE DATABASE practice OWNER practice;
SQL
psql --username "$POSTGRES_USER" --dbname practice --set ON_ERROR_STOP=1 <<'SQL'
SET ROLE practice;
CREATE TABLE events (id integer PRIMARY KEY, customer_id integer NOT NULL, occurred_at timestamptz, status text NOT NULL);
INSERT INTO events VALUES (1,7,'2026-01-02','new'), (2,7,'2026-01-04','closed');
SQL
touch "$PGDATA/TASK_READY"
