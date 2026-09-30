# Restore disappearing department rows

The utilization endpoint drops departments from the tenant dashboard when they have no bookings in the selected month. Trace `app.api.utilization(conn, tenant_id, since, until)` through the application to find and repair the query.

Work in `/app`. Production edits may touch `app/api.py` and `app/queries.py`; the faulty function is deliberately not identified. Preserve public signatures. Return `(department_id, booking_count, total_minutes)` ordered by department ID, including every department in the requested tenant. Count only non-cancelled bookings starting in `[since, until)`. Departments with no qualifying booking must have integer zero for both aggregates, even if they have cancelled or out-of-window bookings. Equal-duration bookings each count. Other tenants must never appear.

Use one parameterized PostgreSQL query through psycopg. No Python aggregation, interpolation of request values into SQL, writes, external side effects or changes to other files/schema/tests/configuration.

Use only the imports already present; do not add imports.

Run these checks before finishing:

```bash
pytest tests/test_visible.py
ruff check --no-cache app/api.py app/queries.py
```
