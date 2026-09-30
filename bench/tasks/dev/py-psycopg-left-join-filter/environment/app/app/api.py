from app.queries import department_counts


def utilization(conn, tenant_id, since, until):
    return department_counts(conn, tenant_id, since, until)
