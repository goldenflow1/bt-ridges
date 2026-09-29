from datetime import UTC, datetime

from tidewater.models import OrderStatus
from tidewater.reports import customer_revenue, pending_orders, sku_volume


def at(day, hour=12):
    return datetime(2026, 3, day, hour, 0, tzinfo=UTC)


def by_id(rows):
    return {row.customer_id: row for row in rows}


def test_revenue_sums_order_lines(shop, session):
    ana = shop.customer("Ana Duarte")
    shop.order(ana, [("TENT-2P", 1, 24900), ("STAKE-8", 2, 1250)], shipped=[at(3)])
    shop.order(ana, [("LAMP-HD", 1, 3999)], shipped=[at(5)])

    [row] = customer_revenue(session)

    assert row.customer_id == ana.id
    assert row.revenue_cents == 24900 + 2 * 1250 + 3999
    assert row.order_count == 2
    assert row.last_shipped_at == at(5)


def test_cancelled_orders_are_excluded(shop, session):
    ben = shop.customer("Ben Okafor")
    shop.order(ben, [("PACK-40L", 1, 13900)], shipped=[at(4)])
    shop.order(ben, [("PACK-60L", 1, 17900)], status=OrderStatus.CANCELLED)

    [row] = customer_revenue(session)

    assert row.revenue_cents == 13900
    assert row.order_count == 1


def test_customer_without_orders_is_listed_with_zero(shop, session):
    cleo = shop.customer("Cleo Marsh")
    dev = shop.customer("Dev Patel")
    shop.order(dev, [("MUG-TI", 3, 2450)], shipped=[at(6)])

    rows = customer_revenue(session)

    assert [row.customer_id for row in rows] == [dev.id, cleo.id]
    assert rows[1].revenue_cents == 0
    assert rows[1].order_count == 0
    assert rows[1].last_shipped_at is None


def test_unshipped_orders_still_count_as_revenue(shop, session):
    eli = shop.customer("Eli Brandt")
    shop.order(eli, [("STOVE-M", 1, 8900)])

    [row] = customer_revenue(session)

    assert row.revenue_cents == 8900
    assert row.last_shipped_at is None


def test_region_filter(shop, session):
    fay = shop.customer("Fay Lund", region="north")
    gus = shop.customer("Gus Varga", region="south")
    shop.order(fay, [("SOCK-W", 4, 1800)], shipped=[at(7)])
    shop.order(gus, [("SOCK-W", 1, 1800)], shipped=[at(7)])

    rows = customer_revenue(session, region="south")

    assert [(row.customer_id, row.revenue_cents) for row in rows] == [(gus.id, 1800)]


def test_placed_window_is_half_open(shop, session):
    hal = shop.customer("Hal Rios")
    shop.order(hal, [("MAP-NW", 1, 1500)], placed_at=at(1, 0), shipped=[at(2)])
    shop.order(hal, [("MAP-SE", 1, 1700)], placed_at=at(10, 0), shipped=[at(11)])

    [row] = customer_revenue(session, placed_from=at(1, 0), placed_to=at(10, 0))

    assert row.revenue_cents == 1500
    assert row.order_count == 1


def test_revenue_ordering_breaks_ties_by_customer_id(shop, session):
    ivy = shop.customer("Ivy Chen")
    jon = shop.customer("Jon Sato")
    kit = shop.customer("Kit Moreau")
    shop.order(kit, [("TARP-3", 1, 4200)], shipped=[at(8)])
    shop.order(jon, [("TARP-3", 1, 4200)], shipped=[at(8)])
    shop.order(ivy, [("ROPE-30", 1, 9900)], shipped=[at(8)])

    rows = customer_revenue(session)

    assert [row.customer_id for row in rows] == [ivy.id, jon.id, kit.id]


def test_sku_volume_counts_shipped_orders_only(shop, session):
    lia = shop.customer("Lia Novak")
    shop.order(lia, [("FILTER-X", 2, 3400)], shipped=[at(9)])
    shop.order(lia, [("FILTER-X", 5, 3400)])

    assert [(row.sku, row.units) for row in sku_volume(session)] == [("FILTER-X", 2)]


def test_pending_orders_lists_paid_unshipped(shop, session):
    max_ = shop.customer("Max Ruiz")
    waiting = shop.order(max_, [("BOTTLE-1L", 1, 2900)], placed_at=at(2))
    shop.order(max_, [("BOTTLE-1L", 1, 2900)], placed_at=at(3), shipped=[at(4)])
    shop.order(max_, [("BOTTLE-1L", 1, 2900)], placed_at=at(1), status=OrderStatus.PLACED)

    assert [row.order_id for row in pending_orders(session)] == [waiting.id]
