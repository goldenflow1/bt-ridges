"""Read-only report queries used by the finance dashboard."""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import and_, desc, distinct, exists, func, select
from sqlalchemy.orm import Session

from tidewater.models import Customer, Order, OrderItem, OrderStatus, Shipment


@dataclass(frozen=True)
class CustomerRevenue:
    customer_id: int
    name: str
    revenue_cents: int
    order_count: int
    last_shipped_at: datetime | None


@dataclass(frozen=True)
class SkuVolume:
    sku: str
    units: int


@dataclass(frozen=True)
class PendingOrder:
    order_id: int
    customer_id: int
    placed_at: datetime


def customer_revenue(
    session: Session,
    *,
    region: str | None = None,
    placed_from: datetime | None = None,
    placed_to: datetime | None = None,
) -> list[CustomerRevenue]:
    """Return one row per customer with revenue from non-cancelled orders.

    Revenue is the sum of ``quantity * unit_price_cents`` over the lines of
    every non-cancelled order placed in ``[placed_from, placed_to)``.
    ``last_shipped_at`` is the most recent shipment of those orders.
    Customers without qualifying orders are listed with zero revenue.
    Rows are ordered by revenue (highest first), then customer id.
    """
    order_join = [Order.customer_id == Customer.id, Order.status != OrderStatus.CANCELLED]
    if placed_from is not None:
        order_join.append(Order.placed_at >= placed_from)
    if placed_to is not None:
        order_join.append(Order.placed_at < placed_to)

    revenue = func.coalesce(func.sum(OrderItem.quantity * OrderItem.unit_price_cents), 0)
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
        .order_by(desc("revenue_cents"), Customer.id)
    )
    if region is not None:
        stmt = stmt.where(Customer.region == region)

    return [
        CustomerRevenue(
            customer_id=row.id,
            name=row.name,
            revenue_cents=int(row.revenue_cents),
            order_count=row.order_count,
            last_shipped_at=row.last_shipped_at,
        )
        for row in session.execute(stmt)
    ]


def sku_volume(session: Session, *, shipped_from: datetime | None = None) -> list[SkuVolume]:
    """Units per SKU across orders that have at least one shipment."""
    shipped = exists().where(Shipment.order_id == Order.id)
    if shipped_from is not None:
        shipped = shipped.where(Shipment.shipped_at >= shipped_from)
    stmt = (
        select(OrderItem.sku, func.sum(OrderItem.quantity).label("units"))
        .join(Order, Order.id == OrderItem.order_id)
        .where(Order.status != OrderStatus.CANCELLED, shipped)
        .group_by(OrderItem.sku)
        .order_by(desc("units"), OrderItem.sku)
    )
    return [SkuVolume(sku=row.sku, units=int(row.units)) for row in session.execute(stmt)]


def pending_orders(session: Session) -> list[PendingOrder]:
    """Paid orders that have not shipped yet, oldest first."""
    stmt = (
        select(Order.id, Order.customer_id, Order.placed_at)
        .where(
            Order.status == OrderStatus.PAID,
            ~exists().where(Shipment.order_id == Order.id),
        )
        .order_by(Order.placed_at, Order.id)
    )
    return [
        PendingOrder(order_id=row.id, customer_id=row.customer_id, placed_at=row.placed_at)
        for row in session.execute(stmt)
    ]
