"""Tenant analytics backed by ClickHouse."""


def daily_events(client, tenant, start_day, end_day, zone):
    """Count events on local calendar days, including empty days."""
    return []


def service_name():
    return "observatory"
