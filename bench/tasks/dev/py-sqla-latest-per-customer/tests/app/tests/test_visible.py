from datetime import datetime, timezone

from app.reports import latest_per_customer

START = datetime(2026, 1, 1, tzinfo=timezone.utc)
END = datetime(2026, 2, 1, tzinfo=timezone.utc)


def test_sample(conn):
    conn.exec_driver_sql("INSERT INTO events VALUES (1, 7, '2026-01-02', 'new'), (2, 7, '2026-01-04', 'closed')")
    assert [(r[0], r[1]) for r in latest_per_customer(conn, START, END)] == [(7, 2)]


def test_empty(conn):
    assert latest_per_customer(conn, START, END) == []
