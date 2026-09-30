#!/bin/bash
set -euo pipefail
psql --username "$POSTGRES_USER" --dbname postgres --set ON_ERROR_STOP=1 <<'SQL'
CREATE ROLE practice LOGIN PASSWORD 'practice-local' NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
CREATE DATABASE practice OWNER practice;
SQL
psql --username "$POSTGRES_USER" --dbname practice --set ON_ERROR_STOP=1 <<'SQL'
SET ROLE practice;
CREATE TABLE departments (id integer PRIMARY KEY, tenant_id integer NOT NULL, name text NOT NULL);
CREATE TABLE bookings (id integer PRIMARY KEY, department_id integer REFERENCES departments(id), starts_at timestamptz NOT NULL, cancelled boolean NOT NULL, minutes integer NOT NULL);
INSERT INTO departments VALUES (1,10,'Alpha');
INSERT INTO bookings VALUES (1,1,'2026-01-03',false,30);
SQL
touch "$PGDATA/TASK_READY"
