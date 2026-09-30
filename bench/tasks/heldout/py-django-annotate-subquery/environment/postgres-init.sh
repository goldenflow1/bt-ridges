#!/bin/bash
set -euo pipefail
psql --username "$POSTGRES_USER" --dbname postgres --set ON_ERROR_STOP=1 <<'SQL'
CREATE ROLE practice LOGIN PASSWORD 'practice-local' NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
CREATE DATABASE practice OWNER practice;
SQL
psql --username "$POSTGRES_USER" --dbname practice --set ON_ERROR_STOP=1 <<'SQL'
SET ROLE practice;
CREATE TABLE doctors(id serial PRIMARY KEY,clinic_id integer NOT NULL,display_name varchar(100) NOT NULL);
CREATE TABLE sessions(id serial PRIMARY KEY,doctor_id integer NOT NULL REFERENCES doctors(id),minutes integer NOT NULL,approved boolean NOT NULL);
CREATE TABLE appointments(id serial PRIMARY KEY,doctor_id integer NOT NULL REFERENCES doctors(id),starts_at timestamptz NOT NULL,state varchar(30) NOT NULL);
INSERT INTO doctors VALUES(1,7,'Dr Alma');
INSERT INTO sessions VALUES(1,1,45,true),(2,1,30,true);
INSERT INTO appointments VALUES(1,1,'2026-12-01','open'),(2,1,'2026-12-02','open');
SQL
touch "$PGDATA/TASK_READY"
