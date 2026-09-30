#!/bin/bash
set -euo pipefail
psql --username "$POSTGRES_USER" --dbname postgres --set ON_ERROR_STOP=1 <<'SQL'
CREATE ROLE auditfeed LOGIN PASSWORD 'auditfeed-app-81b04c6e' NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
SQL
createdb --username "$POSTGRES_USER" --owner auditfeed auditfeed_dev
createdb --username "$POSTGRES_USER" --owner auditfeed auditfeed_test
touch "$PGDATA/TASK_READY"
