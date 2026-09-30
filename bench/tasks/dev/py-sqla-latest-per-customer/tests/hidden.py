from datetime import datetime, timezone

from app.reports import latest_per_customer
from sqlalchemy import event

START = datetime(2026, 1, 1, tzinfo=timezone.utc)
END = datetime(2026, 2, 1, tzinfo=timezone.utc)


def ids(conn):
    return [(row[0], row[1]) for row in latest_per_customer(conn, START, END)]


def test_timestamp_ties_choose_largest_id(conn):
    conn.exec_driver_sql("INSERT INTO events VALUES (90, 8, '2026-01-09', 'x'), (4, 8, '2026-01-09', 'y'), (5, 2, '2026-01-08', 'x')")
    assert ids(conn) == [(2, 5), (8, 90)]


def test_id_is_not_chronology(conn):
    conn.exec_driver_sql("INSERT INTO events VALUES (90, 8, '2026-01-02', 'x'), (4, 8, '2026-01-09', 'y')")
    assert ids(conn) == [(8, 4)]


def test_window_precedes_ranking_and_is_half_open(conn):
    conn.exec_driver_sql("INSERT INTO events VALUES (1, 1, '2026-01-01', 'x'), (2, 1, '2026-02-01', 'x'), (3, 2, NULL, 'x'), (4, 3, '2025-12-31 23:59:59+00', 'x')")
    assert ids(conn) == [(1, 1)]


def test_one_statement_on_many_customers(conn):
    conn.exec_driver_sql("INSERT INTO events SELECT x, mod(x, 71), '2026-01-01'::timestamptz + (mod(x, 13)) * interval '1 hour', 'x' FROM generate_series(1, 997) x")
    expected = list(conn.exec_driver_sql("SELECT DISTINCT ON (customer_id) customer_id, id FROM events ORDER BY customer_id, occurred_at DESC, id DESC"))
    seen = []
    def observe(*args):
        seen.append(args[2])
    event.listen(conn, 'before_cursor_execute', observe)
    try:
        actual = ids(conn)
    finally:
        event.remove(conn, 'before_cursor_execute', observe)
    assert actual == expected
    assert len(seen) == 1


def test_timestamp_projection_preserves_exact_instant(conn):
    conn.exec_driver_sql("INSERT INTO events VALUES (1, 3, '2026-01-08 23:42:17.123456-05:00', 'new'), (2, 3, '2026-01-09 04:42:17.123456+00', 'closed'), (3, 4, '2026-01-11 15:06:07.654321+05:45', 'new')")
    assert list(latest_per_customer(conn, START, END)) == [
        (3, 2, datetime(2026, 1, 9, 4, 42, 17, 123456, tzinfo=timezone.utc)),
        (4, 3, datetime(2026, 1, 11, 9, 21, 7, 654321, tzinfo=timezone.utc)),
    ]
