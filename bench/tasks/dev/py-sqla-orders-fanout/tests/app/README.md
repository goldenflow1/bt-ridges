# tidewater

Back-office reporting for the Tidewater Outfitters web shop.

- `tidewater/models.py` — SQLAlchemy models for customers, orders, order lines and shipments.
- `tidewater/reports.py` — read-only report queries used by the finance dashboard.
- `tidewater/cli.py` — `python -m tidewater.cli revenue` prints the revenue report.

Configuration comes from the environment:

- `TIDEWATER_DATABASE_URL` — the development database (seeded with sample data).
- `TIDEWATER_TEST_DATABASE_URL` — scratch database used by the test suite.

Run the tests with `pytest tests/test_reports.py`.
