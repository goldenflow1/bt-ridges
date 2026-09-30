#!/bin/bash
set -euo pipefail
psql --username "$POSTGRES_USER" --dbname postgres --set ON_ERROR_STOP=1 <<'SQL'
CREATE ROLE practice LOGIN PASSWORD 'practice-local' NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
CREATE DATABASE practice OWNER practice;
SQL
psql --username "$POSTGRES_USER" --dbname practice --set ON_ERROR_STOP=1 <<'SQL'
SET ROLE practice;

SQL
touch "$PGDATA/TASK_READY"
