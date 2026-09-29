# Repair per-customer revenue

The finance dashboard of the Tidewater back office calls
`customer_revenue()` to list every customer with the revenue of their
non-cancelled orders, their order count, and the time of their most recent
shipment. Since the `last_shipped_at` column was added, finance reports that
some customers' revenue is too high: orders that were shipped in more than one
parcel appear to be counted several times.

On the seeded development database the report currently prints:

```text
  id  customer               orders      revenue  last shipped
   6  Fay Lund                    1       374.00  2026-03-09T08:00:00+00:00
   1  Ana Duarte                  2       313.99  2026-03-10T08:00:00+00:00
   2  Ben Okafor                  1       163.00  2026-03-04T12:15:00+00:00
   4  Dev Patel                   1       162.50  2026-03-06T08:00:00+00:00
   5  Eli Brandt                  2        87.00  2026-03-07T10:40:00+00:00
   3  Cleo Marsh                  0         0.00  -
```

Work in `/app`. Limit production changes to `tidewater/reports.py`,
specifically the `customer_revenue()` function. Keep its signature and
docstring and the rest of the file unchanged, including imports; use only names
the file already imports.

`customer_revenue()` must return exactly one `CustomerRevenue` per customer
(after the optional `region` filter) where:

- `revenue_cents` is the sum of `quantity * unit_price_cents` over every line
  of every non-cancelled order placed in `[placed_from, placed_to)`, each line
  counted exactly once no matter how many shipments its order has;
- order lines with equal amounts, in the same order or in different orders,
  all count;
- `order_count` is the number of those orders and `last_shipped_at` is the
  latest `shipped_at` among their shipments, or `None`;
- customers without qualifying orders are listed with integer `0` revenue,
  `0` orders and `None`;
- rows stay ordered by revenue descending, then customer id;
- the report is computed by a single SQL statement.

Keep the aggregation in PostgreSQL using SQLAlchemy Core expressions. Do not
aggregate, filter, or deduplicate rows in Python, and do not use raw SQL
strings. Do not change models, the schema, the seed data, the other report
functions, the CLI, tests, or project configuration. Do not add database
writes, process, filesystem, or network side effects.

Run these checks before finishing:

```bash
pytest tests/test_reports.py
ruff check --no-cache tidewater/reports.py
```
