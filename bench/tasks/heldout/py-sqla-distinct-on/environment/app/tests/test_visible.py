from freight.api import dashboard
from freight.repositories.history import timeline


def test_single_parcel_and_timeline(conn):
    conn.exec_driver_sql("INSERT INTO parcels VALUES (10, 7, 'PX-10')")
    conn.exec_driver_sql("INSERT INTO scans VALUES (1,10,'2026-01-01 09:00+00','North','moving'), (2,10,'2026-01-02 09:00+00','East','delivered')")
    result = dashboard(conn, 7)
    assert result['current'] == [{'parcel_id': 10, 'scan_id': 2, 'recorded_at': '2026-01-02T09:00:00+00:00', 'depot': 'East', 'condition': 'delivered'}]
    assert result['scan_volume'] == 2
    assert [r['id'] for r in timeline(conn, 10)] == [1, 2]


def test_empty_carrier(conn):
    assert dashboard(conn, 99) == {'current': [], 'scan_volume': 0}
