def department_counts(conn, tenant_id, since, until):
    """Department counts and total minutes for non-cancelled bookings in the requested window."""
    query = """
        SELECT d.id, COUNT(b.id), COALESCE(SUM(b.minutes), 0)
        FROM departments d LEFT JOIN bookings b ON b.department_id = d.id
        WHERE d.tenant_id = %s AND b.cancelled = false AND b.starts_at >= %s AND b.starts_at < %s
        GROUP BY d.id ORDER BY d.id
    """
    return conn.execute(query, (tenant_id, since, until)).fetchall()
