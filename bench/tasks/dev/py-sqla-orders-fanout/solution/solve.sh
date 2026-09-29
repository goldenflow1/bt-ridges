#!/bin/bash
set -euo pipefail

cd /app
python - <<'PY'
from pathlib import Path

path = Path('tidewater/reports.py')
text = path.read_text()
anchor = """    revenue = func.coalesce(func.sum(OrderItem.quantity * OrderItem.unit_price_cents), 0)
    stmt = (
        select(
            Customer.id,
            Customer.name,
            revenue.label("revenue_cents"),
            func.count(distinct(Order.id)).label("order_count"),
            func.max(Shipment.shipped_at).label("last_shipped_at"),
        )
        .select_from(Customer)
        .outerjoin(Order, and_(*order_join))
        .outerjoin(OrderItem, OrderItem.order_id == Order.id)
        .outerjoin(Shipment, Shipment.order_id == Order.id)
        .group_by(Customer.id, Customer.name)
"""
replacement = """    order_totals = (
        select(
            OrderItem.order_id,
            func.sum(OrderItem.quantity * OrderItem.unit_price_cents).label("order_cents"),
        )
        .group_by(OrderItem.order_id)
        .subquery()
    )
    order_shipments = (
        select(Shipment.order_id, func.max(Shipment.shipped_at).label("shipped_at"))
        .group_by(Shipment.order_id)
        .subquery()
    )
    revenue = func.coalesce(func.sum(order_totals.c.order_cents), 0)
    stmt = (
        select(
            Customer.id,
            Customer.name,
            revenue.label("revenue_cents"),
            func.count(distinct(Order.id)).label("order_count"),
            func.max(order_shipments.c.shipped_at).label("last_shipped_at"),
        )
        .select_from(Customer)
        .outerjoin(Order, and_(*order_join))
        .outerjoin(order_totals, order_totals.c.order_id == Order.id)
        .outerjoin(order_shipments, order_shipments.c.order_id == Order.id)
        .group_by(Customer.id, Customer.name)
"""
if text.count(anchor) != 1:
    raise SystemExit('frozen customer revenue anchor changed')
path.write_text(text.replace(anchor, replacement, 1))
PY

ruff check --no-cache tidewater/reports.py
