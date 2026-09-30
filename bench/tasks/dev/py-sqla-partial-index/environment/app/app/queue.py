from sqlalchemy import text

QUERY = "SELECT id FROM jobs WHERE tenant_id = :tenant AND status = 'ready' AND deleted_at IS NULL ORDER BY created_at, id LIMIT 25"


def next_jobs(conn, tenant):
    return list(conn.execute(text(QUERY), {'tenant': tenant}).scalars())
