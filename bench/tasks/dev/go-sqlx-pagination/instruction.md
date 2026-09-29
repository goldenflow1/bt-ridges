# Repair audit feed pagination

`auditfeed` serves each tenant's audit trail as an oldest-first, cursor
paginated feed. Clients follow `next_cursor` until it is empty. Customers
syncing large feeds report that some events never arrive while others arrive
twice, mostly after bulk imports.

On the development database the feed looks correct:

```text
$ go run ./cmd/auditfeed -dump kestrel -limit 3
page 1        1  2026-06-01 08:59:12.104233  mia.ortiz  login            session/5521
page 1        2  2026-06-01 09:01:40.550912  mia.ortiz  doc.view         doc/quarterly-plan
page 1        3  2026-06-01 09:03:05.000417  raj.patel  login            session/5522
page 2        4  2026-06-01 09:04:17.982001  mia.ortiz  doc.edit         doc/quarterly-plan
page 2        6  2026-06-01 09:06:33.310774  raj.patel  doc.comment      doc/quarterly-plan
page 2        7  2026-06-01 09:08:02.768145  mia.ortiz  share.create     doc/quarterly-plan
page 3        8  2026-06-01 09:15:49.020300  ana.silva  login            session/5523
page 3       10  2026-06-01 09:16:27.441960  ana.silva  doc.view         doc/quarterly-plan
page 3       11  2026-06-01 09:21:58.119003  raj.patel  logout           session/5522
```

Work in `/app`. Limit production changes to `internal/store/events.go`,
specifically the `(*Store).ListEvents` method. Keep its signature and doc
comment and the rest of the file unchanged, including imports; do not change
the cursor format in `store.go`.

Walking a tenant's pages by feeding each `NextCursor` back in must:

- return every event of the tenant exactly once, for any page size;
- return events oldest first, with events that share a `created_at` ordered
  by `id`;
- behave the same whether or not event ids follow `created_at` order;
- keep returning `NextCursor` only while more events remain, so a feed whose
  length is a multiple of the page size ends without an empty page;
- keep tenants isolated and keep the existing limit clamping and bad-cursor
  errors.

Keep the paging in PostgreSQL: one query per call, with the position filter
and ordering expressed in SQL. Do not filter, sort, or deduplicate events in
Go, and do not change the schema, indexes, migrations, other methods, the
command, tests, or module files. Do not add database writes, process,
filesystem, or network side effects.

Run these checks before finishing:

```bash
go test -count=1 ./...
go vet ./...
gofmt -l internal/store/events.go
```
