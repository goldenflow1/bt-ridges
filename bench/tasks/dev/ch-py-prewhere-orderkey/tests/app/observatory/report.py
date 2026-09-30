"""Tenant analytics backed by ClickHouse."""


def settled_total(client, tenant, start, end):
    """Sum settled amounts for one tenant and half-open UTC interval."""
    return client.query("SELECT sum(amount) AS total FROM events WHERE cityHash64(tenant_id) = cityHash64({tenant:UInt32}) AND happened >= {start:DateTime} AND happened < {end:DateTime} AND status = 'settled' SETTINGS max_threads = 1, use_query_cache = 0", {"tenant": tenant, "start": start, "end": end})


def service_name():
    return "observatory"
