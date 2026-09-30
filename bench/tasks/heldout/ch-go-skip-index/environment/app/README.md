# Build Vault

A CI service looks up build attempts by opaque job ID. Its chronological storage layout supports project timelines but not cross-project job lookups. Existing parts predate the proposed skip index.

The native clickhouse-go client and query repository are immutable. `internal/builds` reports rows read from the exact query's progress callback. `internal/migrate` applies versioned Up/Down SQL once, tracking active versions in a ReplacingMergeTree migration ledger; reapplying an active version does nothing. `cmd/buildvault` is the operational entrypoint.
