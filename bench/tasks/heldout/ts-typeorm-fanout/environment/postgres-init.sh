#!/bin/bash
set -euo pipefail
psql --username "$POSTGRES_USER" --dbname postgres --set ON_ERROR_STOP=1 <<'SQL'
CREATE ROLE stagepass LOGIN PASSWORD 'stagepass-local' NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
CREATE DATABASE stagepass_dev OWNER stagepass;
CREATE DATABASE stagepass_test OWNER stagepass;
SQL
for db in stagepass_dev stagepass_test; do
psql --username "$POSTGRES_USER" --dbname "$db" --set ON_ERROR_STOP=1 <<'SQL'
SET ROLE stagepass;
CREATE TABLE events(id integer PRIMARY KEY,tenant_id integer NOT NULL,title text NOT NULL,starts_at timestamptz(3) NOT NULL,published boolean NOT NULL);
CREATE TABLE ticket_types(id integer PRIMARY KEY,event_id integer NOT NULL REFERENCES events(id),kind text NOT NULL,capacity integer NOT NULL,enabled boolean NOT NULL);
SQL
done
touch "$PGDATA/TASK_READY"
