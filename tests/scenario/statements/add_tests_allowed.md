# Fix order totals and add a regression test

Order totals double count items when an order has several shipments. Fix
`OrderQuery.totals()` in `shop/queries.py` and add a regression test covering
multiple shipments in `tests/test_totals.py`.

Run `pytest tests/test_totals.py`.
