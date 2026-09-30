from app.api import utilization


def test_sample(conn):
    conn.execute("INSERT INTO departments VALUES (1, 10, 'Alpha'), (2, 10, 'Beta')")
    conn.execute("INSERT INTO bookings VALUES (1, 1, '2026-01-03', false, 30), (2, 2, '2026-01-04', false, 15)")
    assert utilization(conn, 10, '2026-01-01', '2026-02-01') == [(1, 1, 30), (2, 1, 15)]
