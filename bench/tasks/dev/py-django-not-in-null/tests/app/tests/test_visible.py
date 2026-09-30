from datetime import datetime, timezone

from app.reports import eligible_customers

NOW = datetime(2026, 1, 10, tzinfo=timezone.utc)


def test_sample(conn):
    conn.execute("INSERT INTO customers VALUES (1, 10, 'A'), (2, 10, 'B')")
    conn.execute("INSERT INTO blocks VALUES (1, 1, 10, true, '2026-02-01')")
    assert eligible_customers(10, NOW) == [2]


def test_empty(conn):
    assert eligible_customers(10, NOW) == []
