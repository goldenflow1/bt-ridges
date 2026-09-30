from app.api import utilization


def report(conn):
    return utilization(conn, 10, '2026-01-01', '2026-02-01')


def test_empty_departments_survive(conn):
    conn.execute("INSERT INTO departments VALUES (1, 10, 'Empty'), (2, 20, 'Other tenant')")
    assert report(conn) == [(1, 0, 0)]


def test_only_nonqualifying_bookings_preserve_department(conn):
    conn.execute("INSERT INTO departments VALUES (1, 10, 'Cancelled'), (2, 10, 'Outside')")
    conn.execute("INSERT INTO bookings VALUES (1, 1, '2026-01-03', true, 99), (2, 2, '2026-02-01', false, 77)")
    assert report(conn) == [(1, 0, 0), (2, 0, 0)]


def test_equal_minutes_boundaries_and_tenant(conn):
    conn.execute("INSERT INTO departments VALUES (1, 10, 'A'), (2, 20, 'B'), (3, 10, 'C')")
    conn.execute("INSERT INTO bookings VALUES (1, 1, '2026-01-01', false, 20), (2, 1, '2026-01-31 23:59:59+00', false, 20), (3, 1, '2026-02-01', false, 999), (4, 2, '2026-01-05', false, 999), (5, 3, '2026-01-04', false, 0)")
    assert report(conn) == [(1, 2, 40), (3, 1, 0)]


def test_report_is_one_parameterized_statement(conn):
    conn.execute("INSERT INTO departments SELECT x, 10, 'dept' FROM generate_series(1, 89) x")
    class Recorder:
        def __init__(self, connection):
            self.connection = connection
            self.calls = []
        def execute(self, sql, params=None):
            self.calls.append((sql, params))
            return self.connection.execute(sql, params)
    recorder = Recorder(conn)
    assert report(recorder) == [(i, 0, 0) for i in range(1, 90)]
    assert len(recorder.calls) == 1
    assert recorder.calls[0][1] is not None
