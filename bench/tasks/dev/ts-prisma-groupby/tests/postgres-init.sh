#!/bin/bash
set -euo pipefail

psql --username "$POSTGRES_USER" --dbname postgres --set ON_ERROR_STOP=1 <<'SQL'
CREATE ROLE courseboard LOGIN PASSWORD 'courseboard-app-2a7d5e90'
  NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
REVOKE ALL ON DATABASE postgres FROM PUBLIC;
REVOKE ALL ON DATABASE template0 FROM PUBLIC;
REVOKE ALL ON DATABASE template1 FROM PUBLIC;
SQL

createdb --username "$POSTGRES_USER" --owner courseboard courseboard_dev
createdb --username "$POSTGRES_USER" --owner courseboard courseboard_test

psql --username "$POSTGRES_USER" --dbname postgres --set ON_ERROR_STOP=1 <<'SQL'
REVOKE ALL ON DATABASE courseboard_dev FROM PUBLIC;
REVOKE ALL ON DATABASE courseboard_test FROM PUBLIC;
GRANT CONNECT ON DATABASE courseboard_dev TO courseboard;
GRANT CONNECT ON DATABASE courseboard_test TO courseboard;
SQL

psql --username "$POSTGRES_USER" --dbname courseboard_dev --set ON_ERROR_STOP=1 <<'SQL'
SET ROLE courseboard;

CREATE TABLE instructors (
    id    serial PRIMARY KEY,
    name  text NOT NULL
);

CREATE TABLE courses (
    id             serial PRIMARY KEY,
    code           text NOT NULL UNIQUE,
    title          text NOT NULL,
    instructor_id  integer NOT NULL REFERENCES instructors (id),
    archived_at    timestamptz
);

CREATE TABLE enrollments (
    id            serial PRIMARY KEY,
    course_id     integer NOT NULL REFERENCES courses (id),
    learner       text NOT NULL,
    status        text NOT NULL DEFAULT 'active'
                  CHECK (status IN ('active', 'withdrawn')),
    enrolled_at   timestamptz NOT NULL DEFAULT now(),
    completed_at  timestamptz,
    UNIQUE (course_id, learner)
);

INSERT INTO instructors (name) VALUES ('Noor Haddad'), ('Tomás Reyes'), ('Ingrid Olsen');

INSERT INTO courses (code, title, instructor_id, archived_at) VALUES
  ('GEO101', 'Physical Geography',      1, NULL),
  ('BIO110', 'Cell Biology',            2, NULL),
  ('ART200', 'Colour Theory',           3, NULL),
  ('CHE150', 'Organic Chemistry I',     2, NULL),
  ('HIS299', 'Medieval Trade Routes',   1, '2026-01-15 00:00+00'),
  ('MAT210', 'Linear Algebra',          3, NULL),
  ('PHY100', 'Mechanics',               1, NULL);

-- GEO101: 4 enrolled, 3 completed; BIO110: 2/1; ART200: 5/5; CHE150: 4/1 (+1 withdrawn);
-- HIS299 archived; MAT210: 10/7; PHY100: no enrollments yet.
INSERT INTO enrollments (course_id, learner, status, completed_at)
SELECT course_id, learner, status, completed_at FROM (VALUES
  (1, 'amara.k',   'active',    '2026-02-02 10:00+00'::timestamptz),
  (1, 'ben.t',     'active',    '2026-02-03 11:00+00'),
  (1, 'chloe.w',   'active',    '2026-02-09 09:30+00'),
  (1, 'dmitri.v',  'active',    NULL),
  (2, 'amara.k',   'active',    '2026-02-20 16:45+00'),
  (2, 'emeka.o',   'active',    NULL),
  (3, 'farah.n',   'active',    '2026-01-30 12:00+00'),
  (3, 'gus.l',     'active',    '2026-01-31 12:00+00'),
  (3, 'hana.m',    'active',    '2026-02-01 12:00+00'),
  (3, 'ivan.p',    'active',    '2026-02-02 12:00+00'),
  (3, 'jade.r',    'active',    '2026-02-03 12:00+00'),
  (4, 'ben.t',     'active',    '2026-03-01 08:00+00'),
  (4, 'kofi.a',    'active',    NULL),
  (4, 'lena.s',    'active',    NULL),
  (4, 'mo.z',      'active',    NULL),
  (4, 'nia.b',     'withdrawn', NULL),
  (5, 'olga.f',    'active',    '2025-12-01 08:00+00'),
  (6, 'amara.k',   'active',    '2026-03-03 10:00+00'),
  (6, 'ben.t',     'active',    '2026-03-04 10:00+00'),
  (6, 'chloe.w',   'active',    '2026-03-05 10:00+00'),
  (6, 'dmitri.v',  'active',    '2026-03-06 10:00+00'),
  (6, 'farah.n',   'active',    '2026-03-07 10:00+00'),
  (6, 'gus.l',     'active',    '2026-03-08 10:00+00'),
  (6, 'hana.m',    'active',    '2026-03-09 10:00+00'),
  (6, 'ivan.p',    'active',    NULL),
  (6, 'jade.r',    'active',    NULL),
  (6, 'kofi.a',    'active',    NULL)
) AS v(course_id, learner, status, completed_at);
SQL

touch "$PGDATA/TASK_READY"
