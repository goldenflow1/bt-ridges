# Payroll exports omit postings at the end of a local pay period

Payroll staff report that some fractional-second ledger postings disappear from an export even though they belong to its final calendar date. Repair the query in `/app` and keep its sqlc output synchronized.

Only `db/queries/payroll.sql` and the SQL literal `listPayEntries` inside `internal/db/payroll.sql.go` may change. Keep the query name, projected columns, generated types, imports, function bodies and signatures unchanged. Use the installed sqlc 1.27.0 (`sqlc generate`) to synchronize output. The caller, schema, date adapter, dependencies, tests and configuration are immutable. The query must remain a single parameterized read-only SELECT, with no side effects or changes to database settings.

Required behavior:
- Export only entries for the requested organization, preserving all stored IDs, timestamps, gross cents and memo text. Zero, negative and large signed 64-bit amounts are valid.
- The API accepts inclusive local dates and an IANA time zone. Its existing adapter supplies the beginning of the first local date and the beginning of the day after the last date. Use these supplied instants directly: start is inclusive and end is exclusive.
- Include fractional seconds through the final microsecond before the end. Exclude entries exactly at the next local midnight and before the start. Do not truncate the instants, assume UTC calendar dates, or assume every local day lasts 24 hours. Month/year changes, 23-hour spring days, 25-hour fall days and fractional-offset zones follow the same rule.
- Return entries by `posted_at` ascending then unique ID ascending; tied timestamps must be deterministic. Preserve the empty-list and existing error behavior.
- The SQL source and all sqlc-generated files must agree exactly with regeneration. Only the query literal may differ from the original generated source.

Run these checks before finishing:

```bash
go test -count=1 ./...
go vet ./...
```
