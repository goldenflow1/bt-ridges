# Complete the customer activity report

Work in `/app`. Complete `latest_per_customer()` in `app/reports.py`. Change only its body, preserving imports, signature and docstring. The current implementation is a sketch that only works when timestamps are unique.

Return exactly one `(customer_id, event_id, occurred_at)` row per customer having an event in `[since, until)`, ordered by customer ID ascending. Select the largest `occurred_at`, breaking timestamp ties by largest event ID. IDs are not chronological. NULL timestamps do not qualify. All statuses participate. Customers without an event in the window are absent.

Use SQLAlchemy Core expressions and one SQL statement. Keep ranking and filtering in PostgreSQL; no raw SQL, Python aggregation/deduplication, writes or external side effects. Do not edit schemas, tests, configuration or other files.

Use only the imports already present; do not add imports.

The complete `app/reports.py` file must contain fewer than 15,000 Unicode characters (code points), including imports, docstrings and whitespace. Newlines are counted after text-mode normalization to a single LF character.

Run these checks before finishing:

```bash
pytest tests/test_visible.py
ruff check --no-cache app/reports.py
```
