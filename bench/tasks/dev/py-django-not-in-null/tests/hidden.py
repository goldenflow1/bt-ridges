from datetime import datetime, timezone

from app.reports import eligible_customers
from django.db import connection
from django.test.utils import CaptureQueriesContext

NOW = datetime(2026, 1, 10, tzinfo=timezone.utc)


def test_null_block_is_not_a_global_ban(conn):
    conn.execute("INSERT INTO customers VALUES (1, 10, 'A'), (2, 10, 'B')")
    conn.execute("INSERT INTO blocks VALUES (1, NULL, 10, true, NULL), (2, 1, 10, true, '2026-02-01')")
    assert eligible_customers(10, NOW) == [2]


def test_indefinite_blocks_and_expiration_boundary(conn):
    conn.execute("INSERT INTO customers VALUES (1, 10, 'A'), (2, 10, 'B'), (3, 10, 'C'), (4, 10, 'D')")
    conn.execute("INSERT INTO blocks VALUES (1, 1, 10, true, NULL), (2, 2, 10, true, '2026-01-10'), (3, 3, 10, false, NULL), (4, 4, 10, true, '2026-01-10 00:00:01+00')")
    assert eligible_customers(10, NOW) == [2, 3]


def test_cross_tenant_blocks_do_not_apply(conn):
    conn.execute("INSERT INTO customers VALUES (1, 10, 'A'), (2, 20, 'B')")
    conn.execute("INSERT INTO blocks VALUES (1, 1, 20, true, '2026-02-01')")
    assert eligible_customers(10, NOW) == [1]


def test_duplicates_and_single_query(conn):
    conn.execute("INSERT INTO customers SELECT x, 10, 'customer' FROM generate_series(1, 501) x")
    conn.execute("INSERT INTO blocks SELECT x, 250, 10, true, NULL FROM generate_series(1, 99) x")
    with CaptureQueriesContext(connection) as seen:
        actual = eligible_customers(10, NOW)
    assert actual == [i for i in range(1, 502) if i != 250]
    assert len(seen) == 1
