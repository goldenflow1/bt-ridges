"""Wallet ledger writes and tenant-level reports."""

from dataclasses import dataclass
from datetime import UTC, datetime

from meterline.chclient import ClickHouse


@dataclass(frozen=True)
class AccountRevision:
    tenant_id: str
    account_id: int
    currency: str
    balance_minor: int
    status: str
    revision: int
    updated_at: datetime


@dataclass(frozen=True)
class CurrencyTotal:
    currency: str
    accounts: int
    balance_minor: int


def record_revisions(client: ClickHouse, revisions: list[AccountRevision]) -> None:
    """Append account revisions. One call is one INSERT."""
    client.insert(
        "account_balances",
        [
            {
                "tenant_id": r.tenant_id,
                "account_id": r.account_id,
                "currency": r.currency,
                "balance_minor": r.balance_minor,
                "status": r.status,
                "revision": r.revision,
                "updated_at": r.updated_at.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            }
            for r in revisions
        ],
    )


def account_history(client: ClickHouse, tenant_id: str, account_id: int) -> list[AccountRevision]:
    """All revisions of one account still stored, oldest first."""
    rows = client.query(
        """
        SELECT tenant_id, account_id, currency, balance_minor, status, revision,
               toUnixTimestamp64Milli(updated_at) AS updated_ms
        FROM account_balances
        WHERE tenant_id = {tenant_id:String} AND account_id = {account_id:UInt64}
        ORDER BY revision
        """,
        {"tenant_id": tenant_id, "account_id": account_id},
    )
    return [_revision(row) for row in rows]


def current_balance(client: ClickHouse, tenant_id: str, account_id: int) -> AccountRevision | None:
    """The current (highest-revision) state of one account."""
    rows = client.query(
        """
        SELECT tenant_id, account_id, currency, balance_minor, status, revision,
               toUnixTimestamp64Milli(updated_at) AS updated_ms
        FROM account_balances
        WHERE tenant_id = {tenant_id:String} AND account_id = {account_id:UInt64}
        ORDER BY revision DESC
        LIMIT 1
        """,
        {"tenant_id": tenant_id, "account_id": account_id},
    )
    return _revision(rows[0]) if rows else None


def tenant_balance_summary(client: ClickHouse, tenant_id: str) -> list[CurrencyTotal]:
    """Current balances of a tenant's active accounts, totalled per currency.

    Each account contributes its current state only. Accounts whose current
    status is not ``active`` are left out. One row per currency, ordered by
    currency code.
    """
    rows = client.query(
        """
        SELECT
            currency,
            count() AS accounts,
            sum(balance_minor) AS balance_minor
        FROM account_balances
        WHERE tenant_id = {tenant_id:String}
          AND status = 'active'
        GROUP BY currency
        ORDER BY currency
        """,
        {"tenant_id": tenant_id},
    )
    return [
        CurrencyTotal(
            currency=row["currency"],
            accounts=int(row["accounts"]),
            balance_minor=int(row["balance_minor"]),
        )
        for row in rows
    ]


def _revision(row: dict) -> AccountRevision:
    return AccountRevision(
        tenant_id=row["tenant_id"],
        account_id=int(row["account_id"]),
        currency=row["currency"],
        balance_minor=int(row["balance_minor"]),
        status=row["status"],
        revision=int(row["revision"]),
        updated_at=datetime.fromtimestamp(int(row["updated_ms"]) / 1000, tz=UTC),
    )
