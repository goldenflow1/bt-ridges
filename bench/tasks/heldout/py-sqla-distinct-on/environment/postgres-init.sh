#!/bin/bash
set -euo pipefail
psql --username "$POSTGRES_USER" --dbname postgres --set ON_ERROR_STOP=1 <<'SQL'
CREATE ROLE practice LOGIN PASSWORD 'practice-local' NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
CREATE DATABASE practice OWNER practice;
SQL
psql --username "$POSTGRES_USER" --dbname practice --set ON_ERROR_STOP=1 <<'SQL'
SET ROLE practice;
CREATE TABLE parcels(id integer PRIMARY KEY, carrier_id integer NOT NULL, reference text NOT NULL);
CREATE TABLE scans(id integer PRIMARY KEY, parcel_id integer NOT NULL REFERENCES parcels(id), recorded_at timestamptz NOT NULL, depot text NOT NULL, condition text NOT NULL);
INSERT INTO parcels VALUES(10,7,'DEMO-10');
INSERT INTO scans VALUES(1,10,'2026-01-01','West','moving'),(2,10,'2026-02-01','East','delivered'),(3,10,'2026-01-15','North','moving');
SQL
touch "$PGDATA/TASK_READY"
