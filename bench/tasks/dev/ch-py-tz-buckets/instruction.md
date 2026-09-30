# Implement complete local-calendar event buckets

Work in `/app`. Change only the body of `daily_events()` in `observatory/report.py`. Preserve its signature, docstring, imports and all other source bytes.

Implement `daily_events(client, tenant, start_day, end_day, zone)`. Dates are ISO `YYYY-MM-DD`; zone is a valid IANA timezone. Return `{"day": "YYYY-MM-DD", "events": integer}` for **every local calendar day** in `[start_day, end_day)`, ordered ascending, including days with no events. An empty or reversed date range returns `[]`. Events are stored as UTC millisecond timestamps; count only the requested tenant and local date interval. Midnight belongs to the following day; daylight-saving changes can make days 23 or 25 hours, and zones can have fractional-hour offsets. Do all counting and day generation in one SQL query with bound input parameters.

Keep the edited function within 6,000 UTF-8 bytes and 500 Python AST nodes.

Keep query work in ClickHouse through `client.query()`. The report must not write data or change the schema. Do not add imports, cache answers, or edit the client, tests, configuration or any other file. The development database is seeded; the separate test database may be used for local investigation.

Run these checks before finishing:

```bash
pytest tests/test_report.py
ruff check --no-cache observatory/report.py
```
