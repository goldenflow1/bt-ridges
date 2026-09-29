# Repair the monthly revenue query

The monthly revenue report sums refunds as revenue. The query is raw SQL in
`reports/sql.py`; keep it as raw SQL and fix only `MONTHLY_REVENUE_SQL`.

Run `pytest tests/test_reports.py`.
