# Make the ready-job index serve the production query

A pending Alembic migration creates an index, but claiming the next jobs for a tenant still scans too much data. Work in `/app`. Change only the pending migration implementation `migrations/ready_jobs.py` (the immutable revision entrypoint imports it); keep revision identifiers and public upgrade/downgrade signatures. Do not edit application SQL, other migrations, schemas, seeds, tests or configuration.

`app.queue.next_jobs` selects one tenant's ready, non-deleted jobs ordered by `created_at, id`, taking 25. Repair the migration so PostgreSQL naturally uses `ix_jobs_ready` for that unmodified query on a representative 100,000-row table. Preserve result ordering and values. The plan must touch at most 80 shared buffer blocks and at least 10 times fewer blocks than the pre-index plan; buffers, not wall-clock timings, determine work. Keep a partial index excluding ineligible jobs, and do not force planner choices with settings/hints. The dev database includes 100,000 rows for local EXPLAIN inspection.

Use Alembic's `op.create_index()` and `op.drop_index()` for migration operations. Upgrade must add only the named index without changing data or columns. Downgrade must remove it and preserve the original schema/data/query results; upgrading again must work. No non-database side effects or changes to PostgreSQL configuration.

Use only the imports already present; do not add imports.

Run these checks before finishing:

```bash
pytest tests/test_visible.py
ruff check --no-cache migrations/ready_jobs.py
```
