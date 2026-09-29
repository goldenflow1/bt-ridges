"""Command-line entry point: ``python -m tidewater.cli revenue``."""

import argparse
import sys

from tidewater.db import make_engine, make_session_factory
from tidewater.reports import customer_revenue, pending_orders, sku_volume


def _money(cents: int) -> str:
    return f"{cents / 100:,.2f}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tidewater")
    sub = parser.add_subparsers(dest="command", required=True)
    revenue = sub.add_parser("revenue", help="revenue per customer")
    revenue.add_argument("--region")
    sub.add_parser("skus", help="units shipped per SKU")
    sub.add_parser("pending", help="paid orders waiting for shipment")
    args = parser.parse_args(argv)

    engine = make_engine()
    with make_session_factory(engine)() as session:
        if args.command == "revenue":
            print(f"{'id':>4}  {'customer':<22} {'orders':>6} {'revenue':>12}  last shipped")
            for row in customer_revenue(session, region=args.region):
                shipped = row.last_shipped_at.isoformat() if row.last_shipped_at else "-"
                print(
                    f"{row.customer_id:>4}  {row.name:<22} {row.order_count:>6} "
                    f"{_money(row.revenue_cents):>12}  {shipped}"
                )
        elif args.command == "skus":
            for row in sku_volume(session):
                print(f"{row.sku:<16} {row.units:>6}")
        else:
            for row in pending_orders(session):
                print(f"{row.order_id:>6} {row.customer_id:>6} {row.placed_at.isoformat()}")
    engine.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(main())
