#!/bin/bash
set -euo pipefail
psql --username "$POSTGRES_USER" --dbname postgres --set ON_ERROR_STOP=1 <<'SQL'
CREATE ROLE practice LOGIN PASSWORD 'practice-local' NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
CREATE DATABASE practice OWNER practice;
SQL
psql --username "$POSTGRES_USER" --dbname practice --set ON_ERROR_STOP=1 <<'SQL'
SET ROLE practice;
CREATE TABLE customers (id integer PRIMARY KEY, tenant_id integer NOT NULL, name text NOT NULL);
CREATE TABLE blocks (id integer PRIMARY KEY, customer_id integer, tenant_id integer NOT NULL, active boolean NOT NULL, expires_at timestamptz);
INSERT INTO customers VALUES (1,10,'A'),(2,10,'B');
INSERT INTO blocks VALUES (1,1,10,true,'2026-02-01');
SQL
touch "$PGDATA/TASK_READY"
