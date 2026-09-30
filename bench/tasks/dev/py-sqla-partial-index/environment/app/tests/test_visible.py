from app.queue import next_jobs


def test_sample(conn):
    conn.exec_driver_sql("INSERT INTO jobs VALUES (1, 7, 'ready', '2026-01-01', NULL, 'a'), (2, 7, 'waiting', '2026-01-01', NULL, 'b'), (3, 7, 'ready', '2026-01-02', NULL, 'c')")
    assert next_jobs(conn, 7) == [1, 3]


def test_upgrade_and_downgrade(conn, migration):
    migration.upgrade()
    assert conn.exec_driver_sql("SELECT to_regclass('ix_jobs_ready') IS NOT NULL").scalar()
    migration.downgrade()
    assert conn.exec_driver_sql("SELECT to_regclass('ix_jobs_ready') IS NULL").scalar()
