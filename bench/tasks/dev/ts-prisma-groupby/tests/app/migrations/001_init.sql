CREATE TABLE IF NOT EXISTS instructors (
    id    serial PRIMARY KEY,
    name  text NOT NULL
);

CREATE TABLE IF NOT EXISTS courses (
    id             serial PRIMARY KEY,
    code           text NOT NULL UNIQUE,
    title          text NOT NULL,
    instructor_id  integer NOT NULL REFERENCES instructors (id),
    archived_at    timestamptz
);

CREATE TABLE IF NOT EXISTS enrollments (
    id            serial PRIMARY KEY,
    course_id     integer NOT NULL REFERENCES courses (id),
    learner       text NOT NULL,
    status        text NOT NULL DEFAULT 'active'
                  CHECK (status IN ('active', 'withdrawn')),
    enrolled_at   timestamptz NOT NULL DEFAULT now(),
    completed_at  timestamptz,
    UNIQUE (course_id, learner)
);
