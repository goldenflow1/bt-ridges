#!/bin/bash
set -euo pipefail

psql --username "$POSTGRES_USER" --dbname postgres --set ON_ERROR_STOP=1 <<'SQL'
CREATE ROLE pantry LOGIN PASSWORD 'pantry-app-6f3b19d2'
  NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
REVOKE ALL ON DATABASE postgres FROM PUBLIC;
REVOKE ALL ON DATABASE template0 FROM PUBLIC;
REVOKE ALL ON DATABASE template1 FROM PUBLIC;
SQL

createdb --username "$POSTGRES_USER" --owner pantry pantry_dev
createdb --username "$POSTGRES_USER" --owner pantry pantry_test

psql --username "$POSTGRES_USER" --dbname postgres --set ON_ERROR_STOP=1 <<'SQL'
REVOKE ALL ON DATABASE pantry_dev FROM PUBLIC;
REVOKE ALL ON DATABASE pantry_test FROM PUBLIC;
GRANT CONNECT ON DATABASE pantry_dev TO pantry;
GRANT CONNECT ON DATABASE pantry_test TO pantry;
SQL

# Development data: schema at migration 0001 plus the `seed_demo` data set.
psql --username "$POSTGRES_USER" --dbname pantry_dev --set ON_ERROR_STOP=1 \
  -c "SET ROLE pantry" -f /opt/task-seed/seed.sql

touch "$PGDATA/TASK_READY"
