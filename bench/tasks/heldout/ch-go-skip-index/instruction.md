# Speed up CI job lookups on existing build history

CI operators search build attempts by job ID across projects. The immutable lookup scans historical parts because the table is ordered by project and start time. Add a migration in `/app` that makes existing as well as future parts useful for job lookup.

Only the new file `migrations/0002_job_index.sql` may be added. Keep all existing paths, modes, application code, driver configuration, queries, schema migration, tests and dependencies unchanged. Follow the repository's `-- +migrate Up` / `-- +migrate Down` SQL convention. Use unqualified `ALTER TABLE builds` statements only: add the index, materialize it, and drop it in the down section. The migration may add only `ix_build_job_id` directly on `job_id`; it must not change the sorting key, columns, existing data or unrelated settings. No other SQL or external side effects.

Required behavior:
- Preserve all lookup results and fields, including duplicate job IDs across projects, chronological ordering and arbitrary bound job-ID strings. Preserve the project timeline query.
- Add a suitable data-skipping index for high-cardinality, pseudorandom job IDs, and materialize it for already stored parts. Materialization must complete before the migration returns. Newly inserted parts must also retain correct lookup behavior.
- At 1,048,576 builds spread over 16 projects, the existing job lookup must read at most 32,768 rows for each of several present IDs and a missing ID. The baseline scans at least 90% of the table. Work is measured from that exact native query's progress callback, with one thread and the query cache disabled; wall-clock time is not the metric.
- Use `ADD INDEX IF NOT EXISTS` and `DROP INDEX IF EXISTS`. The existing migration runner records applied versions; applying an active version again must be a no-op. Down must remove the new index while preserving build data and table layout. Reapplying after down must restore the read-work benefit.
- Preserve every existing index. Migration-ledger records may change through the existing runner, but the new SQL must not access or alter the ledger itself.

Run these checks before finishing:

```bash
go test -count=1 ./...
go vet ./...
```
