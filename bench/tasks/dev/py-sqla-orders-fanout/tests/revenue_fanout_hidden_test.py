from datetime import UTC, datetime

from sqlalchemy import event

from tidewater.models import OrderStatus
from tidewater.reports import CustomerRevenue, customer_revenue


def at(day, hour=9):
    return datetime(2026, 4, day, hour, 0, tzinfo=UTC)


def by_id(rows):
    return {row.customer_id: row for row in rows}


def test_equal_line_amounts_are_each_counted(shop, session):
    otto = shop.customer("Otto Ferreira")
    shop.order(otto, [("CARABINER", 2, 1500), ("CHALK-BAG", 1, 3000)], shipped=[at(2)])
    shop.order(otto, [("CARABINER", 2, 1500)], shipped=[at(3)])
    shop.order(otto, [("CHALK-BAG", 1, 3000), ("CHALK-BAG", 1, 3000)], shipped=[at(4)])

    [row] = customer_revenue(session)

    assert row == CustomerRevenue(
        customer_id=otto.id,
        name="Otto Ferreira",
        revenue_cents=3000 + 3000 + 3000 + 3000 + 3000,
        order_count=3,
        last_shipped_at=at(4),
    )


def test_split_shipments_do_not_multiply_lines(shop, session):
    pia = shop.customer("Pia Lindqvist")
    shop.order(
        pia,
        [("KAYAK-SEA", 1, 189900), ("PADDLE-CF", 2, 24900), ("SKIRT-NEO", 1, 8900)],
        shipped=[at(5), at(6), at(8, 17)],
    )
    shop.order(pia, [("DRYBAG-20", 3, 2900)], shipped=[at(7)])
    shop.order(pia, [("PUMP-HAND", 1, 3900)])

    [row] = customer_revenue(session)

    assert row.revenue_cents == 189900 + 2 * 24900 + 8900 + 3 * 2900 + 3900
    assert row.order_count == 3
    assert row.last_shipped_at == at(8, 17)


def test_parcels_shipped_together_count_once(shop, session):
    yara = shop.customer("Yara Haddad")
    shop.order(
        yara,
        [("TABLE-FOLD", 1, 7900), ("CHAIR-LOW", 2, 5900)],
        shipped=[at(9, 14), at(9, 14), at(9, 14)],
    )

    [row] = customer_revenue(session)

    assert row.revenue_cents == 7900 + 2 * 5900
    assert row.order_count == 1
    assert row.last_shipped_at == at(9, 14)


def test_mixed_customers_rank_by_true_revenue(shop, session):
    quin = shop.customer("Quin Adeyemi", region="east")
    rosa = shop.customer("Rosa Kim", region="east")
    sven = shop.customer("Sven Holm", region="east")
    shop.order(quin, [("BOOT-HIKE", 1, 15900), ("LACES", 2, 500)], shipped=[at(2), at(3)])
    shop.order(quin, [("LACES", 2, 500)], shipped=[at(4)])
    shop.order(rosa, [("JACKET-SH", 1, 18000)], shipped=[at(2)])
    shop.order(sven, [("GAITER", 2, 2100), ("GAITER", 2, 2100)], shipped=[at(2), at(5), at(6)])

    rows = customer_revenue(session, region="east")

    assert [(row.customer_id, row.revenue_cents, row.order_count) for row in rows] == [
        (rosa.id, 18000, 1),
        (quin.id, 15900 + 1000 + 1000, 2),
        (sven.id, 8400, 1),
    ]


def test_customers_without_qualifying_orders_report_integer_zero(shop, session):
    tess = shop.customer("Tess Obi", region="west")
    ugo = shop.customer("Ugo Bellini", region="west")
    vera = shop.customer("Vera Stone", region="west")
    wes = shop.customer("Wes Tran", region="west")
    shop.order(ugo, [("LANTERN", 1, 5400)], status=OrderStatus.CANCELLED, shipped=[at(3)])
    shop.order(vera, [("COT-ALU", 1, 11900)], placed_at=at(20), shipped=[at(21), at(22)])
    shop.order(wes, [("FLASK-S", 2, 2200)], placed_at=at(3), shipped=[at(4), at(5)])

    rows = customer_revenue(session, region="west", placed_from=at(1), placed_to=at(10))
    result = by_id(rows)

    assert [row.customer_id for row in rows] == [wes.id, tess.id, ugo.id, vera.id]
    assert result[wes.id].revenue_cents == 4400
    for customer in (tess, ugo, vera):
        row = result[customer.id]
        assert type(row.revenue_cents) is int
        assert row.revenue_cents == 0
        assert row.order_count == 0
        assert row.last_shipped_at is None


def test_report_is_one_statement(shop, session, engine):
    xan = shop.customer("Xan Moyo")
    for day in range(1, 9):
        shop.order(
            xan,
            [("FUEL-230", day, 699), ("FUEL-450", 1, 999)],
            placed_at=at(day),
            shipped=[at(day, 12), at(day, 15)],
        )
    session.commit()
    statements = []

    def record(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", record)
    try:
        rows = customer_revenue(session)
    finally:
        event.remove(engine, "before_cursor_execute", record)

    selects = [s for s in statements if s.lstrip().upper().startswith(("SELECT", "WITH"))]
    assert len(selects) == 1, statements
    assert len(statements) == len(selects), statements
    assert rows[0].revenue_cents == sum(day * 699 + 999 for day in range(1, 9))
    assert rows[0].order_count == 8
    assert rows[0].last_shipped_at == at(8, 15)


def test_order_without_lines_still_counts(shop, session):
    zed = shop.customer("Zed Achebe")
    shop.order(zed, [], shipped=[at(11), at(12)])
    shop.order(zed, [("TOWEL-MF", 2, 1200)], shipped=[at(10)])
    shop.order(zed, [], status=OrderStatus.CANCELLED, shipped=[at(13)])

    [row] = customer_revenue(session)

    assert row == CustomerRevenue(
        customer_id=zed.id,
        name="Zed Achebe",
        revenue_cents=2400,
        order_count=2,
        last_shipped_at=at(12),
    )


def test_revenue_ties_break_by_id_not_name(shop, session):
    zoe = shop.customer("Zoe Brandt")
    abe = shop.customer("Abe Carver")
    shop.order(zoe, [("CUP-TI", 1, 2500)], shipped=[at(2), at(3)])
    shop.order(abe, [("CUP-TI", 1, 2500)], shipped=[at(2)])

    assert [row.customer_id for row in customer_revenue(session)] == [zoe.id, abe.id]
