"""``python -m meterline.cli summary <tenant>`` / ``history <tenant> <account>``."""

import argparse
import sys

from meterline.balances import account_history, tenant_balance_summary
from meterline.chclient import ClickHouse


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="meterline")
    sub = parser.add_subparsers(dest="command", required=True)
    summary = sub.add_parser("summary", help="active balance per currency for a tenant")
    summary.add_argument("tenant")
    history = sub.add_parser("history", help="stored revisions of one account")
    history.add_argument("tenant")
    history.add_argument("account", type=int)
    args = parser.parse_args(argv)

    client = ClickHouse.from_env()
    if args.command == "summary":
        print(f"{'currency':<8} {'accounts':>8} {'balance':>14}")
        for row in tenant_balance_summary(client, args.tenant):
            print(f"{row.currency:<8} {row.accounts:>8} {row.balance_minor / 100:>14,.2f}")
    else:
        for rev in account_history(client, args.tenant, args.account):
            print(
                f"r{rev.revision:<4} {rev.status:<7} {rev.currency} "
                f"{rev.balance_minor:>10} {rev.updated_at.isoformat()}"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
