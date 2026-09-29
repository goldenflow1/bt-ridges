# auditfeed

Serves each tenant's audit trail as a paginated JSON feed:

    GET /tenants/{tenant}/events?cursor=<opaque>&limit=<n>

Pages are oldest-first. A response carries `next_cursor` while more events
remain; clients pass it back as `cursor` to fetch the next page.

    go run ./cmd/auditfeed -dump <tenant> -limit 3   # print a tenant's feed page by page

Configuration: `AUDITFEED_DATABASE_URL` (development data) and
`AUDITFEED_TEST_DATABASE_URL` (scratch database for `go test`).
Schema: `migrations/001_audit_events.sql`.
