from app.queue import QUERY, next_jobs
from sqlalchemy import text


def seed(conn):
    conn.exec_driver_sql("INSERT INTO jobs SELECT x, mod(x, 100), CASE WHEN mod(x, 997) = 0 THEN 'waiting' ELSE 'ready' END, '2026-01-01'::timestamptz + (100000-x)*interval '1 second', CASE WHEN mod(x, 991) = 0 THEN '2026-01-02'::timestamptz ELSE NULL END, repeat('payload', 40) FROM generate_series(1,100000) x")
    conn.exec_driver_sql('ANALYZE jobs')


def plan(conn, tenant=7):
    return conn.execute(text('EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) ' + QUERY), {'tenant': tenant}).scalar()[0]['Plan']


def nodes(tree):
    yield tree
    for child in tree.get('Plans', []):
        yield from nodes(child)


def test_partial_index_used_and_work_bounded(conn, migration):
    seed(conn)
    tenants = (7, 41, 83)
    expected = {tenant: next_jobs(conn, tenant) for tenant in tenants}
    before = {tenant: plan(conn, tenant) for tenant in tenants}
    migration.upgrade()
    predicate = conn.exec_driver_sql("SELECT pg_get_expr(indpred, indrelid) FROM pg_index WHERE indexrelid = 'ix_jobs_ready'::regclass").scalar()
    assert predicate is not None, 'index must be partial'
    assert conn.exec_driver_sql("SELECT count(*) FROM jobs WHERE (" + predicate + ") AND (status != 'ready' OR deleted_at IS NOT NULL)").scalar() == 0
    for tenant in tenants:
        after = plan(conn, tenant)
        assert next_jobs(conn, tenant) == expected[tenant]
        assert any(node.get('Index Name') == 'ix_jobs_ready' for node in nodes(after)), after
        before_blocks = before[tenant].get('Shared Hit Blocks', 0) + before[tenant].get('Shared Read Blocks', 0)
        after_blocks = after.get('Shared Hit Blocks', 0) + after.get('Shared Read Blocks', 0)
        assert before_blocks >= 500, before[tenant]
        assert after_blocks <= 80 and after_blocks * 10 <= before_blocks, (tenant, before_blocks, after_blocks, after)


def test_upgrade_downgrade_conserve_schema_and_results(conn, migration):
    seed(conn)
    expected = next_jobs(conn, 7)
    digest_sql = "SELECT count(*), sum(hashtextextended(row(j.*)::text, 0)::numeric) FROM jobs j"
    digest = conn.exec_driver_sql(digest_sql).one()
    columns_sql = "SELECT column_name, data_type, is_nullable, column_default FROM information_schema.columns WHERE table_name = 'jobs' ORDER BY ordinal_position"
    columns = list(conn.exec_driver_sql(columns_sql))
    before = list(conn.exec_driver_sql("SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'jobs' ORDER BY indexname"))
    migration.upgrade()
    after = list(conn.exec_driver_sql("SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'jobs' ORDER BY indexname"))
    assert len(after) == len(before) + 1
    assert [row for row in after if row[0] != 'ix_jobs_ready'] == before
    assert next_jobs(conn, 7) == expected
    migration.downgrade()
    assert list(conn.exec_driver_sql("SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'jobs' ORDER BY indexname")) == before
    assert next_jobs(conn, 7) == expected
    assert conn.exec_driver_sql(digest_sql).one() == digest
    assert list(conn.exec_driver_sql(columns_sql)) == columns
    migration.upgrade()
    assert next_jobs(conn, 7) == expected
