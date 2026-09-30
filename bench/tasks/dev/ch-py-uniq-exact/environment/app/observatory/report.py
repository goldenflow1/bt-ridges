"""Tenant analytics backed by ClickHouse."""


def visitor_count(client, tenant, start, end):
    """Count identified visitors in a half-open UTC interval."""
    return client.query('SELECT uniq(visitor) AS visitors FROM visits WHERE tenant = {tenant:String} AND happened >= {start:DateTime} AND happened < {end:DateTime}', {"tenant": tenant, "start": start, "end": end})


def service_name():
    return "observatory"
