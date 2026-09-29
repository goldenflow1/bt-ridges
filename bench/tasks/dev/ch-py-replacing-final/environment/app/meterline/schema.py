"""ClickHouse DDL for the wallet ledger."""

from meterline.chclient import ClickHouse

ACCOUNT_BALANCES = """
CREATE TABLE IF NOT EXISTS account_balances
(
    tenant_id     LowCardinality(String),
    account_id    UInt64,
    currency      LowCardinality(String),
    balance_minor Int64,
    status        Enum8('active' = 1, 'frozen' = 2, 'closed' = 3),
    revision      UInt64,
    updated_at    DateTime64(3, 'UTC')
)
ENGINE = ReplacingMergeTree(revision)
ORDER BY (tenant_id, account_id)
"""

TABLES = {"account_balances": ACCOUNT_BALANCES}


def create_schema(client: ClickHouse) -> None:
    for ddl in TABLES.values():
        client.command(ddl)


def drop_schema(client: ClickHouse) -> None:
    for name in TABLES:
        client.command(f"DROP TABLE IF EXISTS {name}")
