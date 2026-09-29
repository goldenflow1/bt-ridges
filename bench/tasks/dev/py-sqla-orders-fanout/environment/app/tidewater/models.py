"""ORM models for the order database."""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class OrderStatus(StrEnum):
    PLACED = "placed"
    PAID = "paid"
    CANCELLED = "cancelled"


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(254), unique=True)
    region: Mapped[str] = mapped_column(String(16), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    orders: Mapped[list["Order"]] = relationship(back_populates="customer")


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint("status IN ('placed', 'paid', 'cancelled')", name="orders_status_check"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    status: Mapped[str] = mapped_column(String(16), default=OrderStatus.PLACED)
    placed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    customer: Mapped[Customer] = relationship(back_populates="orders")
    items: Mapped[list["OrderItem"]] = relationship(back_populates="order")
    shipments: Mapped[list["Shipment"]] = relationship(back_populates="order")


class OrderItem(Base):
    __tablename__ = "order_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="order_items_quantity_check"),
        CheckConstraint("unit_price_cents >= 0", name="order_items_price_check"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    sku: Mapped[str] = mapped_column(String(32))
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price_cents: Mapped[int] = mapped_column(Integer)

    order: Mapped[Order] = relationship(back_populates="items")


class Shipment(Base):
    """One parcel. Large orders are often split across several parcels."""

    __tablename__ = "shipments"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    carrier: Mapped[str] = mapped_column(String(32))
    tracking_code: Mapped[str] = mapped_column(String(64), unique=True)
    shipped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    order: Mapped[Order] = relationship(back_populates="shipments")
