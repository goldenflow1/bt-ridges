import os
from datetime import UTC, datetime

import pytest
from sqlalchemy import text

from tidewater.db import make_engine, make_session_factory
from tidewater.models import Base, Customer, Order, OrderItem, OrderStatus, Shipment

TEST_URL_ENV = "TIDEWATER_TEST_DATABASE_URL"


@pytest.fixture(scope="session")
def engine():
    url = os.environ.get(TEST_URL_ENV)
    if not url:
        pytest.skip(f"{TEST_URL_ENV} is not set")
    engine = make_engine(url)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def session(engine):
    with engine.begin() as conn:
        conn.execute(
            text("TRUNCATE shipments, order_items, orders, customers RESTART IDENTITY CASCADE")
        )
    factory = make_session_factory(engine)
    with factory() as session:
        yield session


class Shop:
    """Tiny builder for test data."""

    def __init__(self, session):
        self.session = session
        self._tracking = 0

    def customer(self, name, region="north"):
        slug = name.lower().replace(" ", ".")
        customer = Customer(name=name, email=f"{slug}@example.test", region=region)
        self.session.add(customer)
        self.session.flush()
        return customer

    def order(self, customer, lines, *, placed_at=None, status=OrderStatus.PAID, shipped=()):
        order = Order(
            customer_id=customer.id,
            status=status,
            placed_at=placed_at or datetime(2026, 3, 2, 10, 0, tzinfo=UTC),
        )
        self.session.add(order)
        self.session.flush()
        for sku, quantity, unit_price_cents in lines:
            self.session.add(
                OrderItem(
                    order_id=order.id,
                    sku=sku,
                    quantity=quantity,
                    unit_price_cents=unit_price_cents,
                )
            )
        for shipped_at in shipped:
            self._tracking += 1
            self.session.add(
                Shipment(
                    order_id=order.id,
                    carrier="harbourpost",
                    tracking_code=f"HP{self._tracking:08d}",
                    shipped_at=shipped_at,
                )
            )
        self.session.flush()
        return order


@pytest.fixture
def shop(session):
    return Shop(session)
