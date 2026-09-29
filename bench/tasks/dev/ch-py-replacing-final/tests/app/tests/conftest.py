from datetime import UTC, datetime, timedelta

import pytest

from meterline.balances import AccountRevision, record_revisions
from meterline.chclient import ClickHouse
from meterline.schema import TABLES, create_schema, drop_schema

T0 = datetime(2026, 5, 1, 8, 0, tzinfo=UTC)


@pytest.fixture(scope="session")
def client():
    client = ClickHouse.from_env("METERLINE_TEST_DATABASE")
    drop_schema(client)
    create_schema(client)
    return client


@pytest.fixture
def ch(client):
    for table in TABLES:
        client.command(f"TRUNCATE TABLE {table}")
        client.command(f"SYSTEM START MERGES {table}")
    return client


class Ledger:
    """Writes account revisions the way the wallet service does."""

    def __init__(self, client):
        self.client = client

    def write(self, tenant, account, revision, balance, *, currency="EUR", status="active",
              at=None):
        record_revisions(
            self.client,
            [
                AccountRevision(
                    tenant_id=tenant,
                    account_id=account,
                    currency=currency,
                    balance_minor=balance,
                    status=status,
                    revision=revision,
                    updated_at=at or T0 + timedelta(minutes=revision),
                )
            ],
        )

    def merge(self):
        self.client.command("OPTIMIZE TABLE account_balances FINAL")


@pytest.fixture
def ledger(ch):
    return Ledger(ch)
