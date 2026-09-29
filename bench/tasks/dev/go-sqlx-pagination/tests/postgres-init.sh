#!/bin/bash
set -euo pipefail

psql --username "$POSTGRES_USER" --dbname postgres --set ON_ERROR_STOP=1 <<'SQL'
CREATE ROLE auditfeed LOGIN PASSWORD 'auditfeed-app-81b04c6e'
  NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
REVOKE ALL ON DATABASE postgres FROM PUBLIC;
REVOKE ALL ON DATABASE template0 FROM PUBLIC;
REVOKE ALL ON DATABASE template1 FROM PUBLIC;
SQL

createdb --username "$POSTGRES_USER" --owner auditfeed auditfeed_dev
createdb --username "$POSTGRES_USER" --owner auditfeed auditfeed_test

psql --username "$POSTGRES_USER" --dbname postgres --set ON_ERROR_STOP=1 <<'SQL'
REVOKE ALL ON DATABASE auditfeed_dev FROM PUBLIC;
REVOKE ALL ON DATABASE auditfeed_test FROM PUBLIC;
GRANT CONNECT ON DATABASE auditfeed_dev TO auditfeed;
GRANT CONNECT ON DATABASE auditfeed_test TO auditfeed;
SQL

psql --username "$POSTGRES_USER" --dbname auditfeed_dev --set ON_ERROR_STOP=1 <<'SQL'
SET ROLE auditfeed;

CREATE TABLE audit_events (
    id          bigserial PRIMARY KEY,
    tenant_id   text        NOT NULL,
    actor       text        NOT NULL,
    action      text        NOT NULL,
    target      text        NOT NULL DEFAULT '',
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX audit_events_tenant_created_idx
    ON audit_events (tenant_id, created_at, id);

INSERT INTO audit_events (tenant_id, actor, action, target, created_at) VALUES
  ('kestrel', 'mia.ortiz',  'login',        'session/5521',      '2026-06-01 08:59:12.104233+00'),
  ('kestrel', 'mia.ortiz',  'doc.view',     'doc/quarterly-plan', '2026-06-01 09:01:40.550912+00'),
  ('kestrel', 'raj.patel',  'login',        'session/5522',      '2026-06-01 09:03:05.000417+00'),
  ('kestrel', 'mia.ortiz',  'doc.edit',     'doc/quarterly-plan', '2026-06-01 09:04:17.982001+00'),
  ('osprey',  'lee.wong',   'login',        'session/7710',      '2026-06-01 09:05:00.120000+00'),
  ('kestrel', 'raj.patel',  'doc.comment',  'doc/quarterly-plan', '2026-06-01 09:06:33.310774+00'),
  ('kestrel', 'mia.ortiz',  'share.create', 'doc/quarterly-plan', '2026-06-01 09:08:02.768145+00'),
  ('kestrel', 'ana.silva',  'login',        'session/5523',      '2026-06-01 09:15:49.020300+00'),
  ('osprey',  'lee.wong',   'doc.view',     'doc/onboarding',    '2026-06-01 09:16:10.887001+00'),
  ('kestrel', 'ana.silva',  'doc.view',     'doc/quarterly-plan', '2026-06-01 09:16:27.441960+00'),
  ('kestrel', 'raj.patel',  'logout',       'session/5522',      '2026-06-01 09:21:58.119003+00');
SQL

touch "$PGDATA/TASK_READY"
