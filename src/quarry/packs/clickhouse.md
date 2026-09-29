ClickHouse notes:
- ReplacingMergeTree / CollapsingMergeTree deduplicate only when parts merge, which may never happen before a query. Deduplicate in the query: FINAL on the table, or argMax(value, version) grouped by the key at the right grain, before any further aggregation.
- JOINs fill missing right-side values with type defaults (0, '', 1970-01-01), not NULL, unless join_use_nulls = 1. Test for "no match" accordingly.
- uniq() is approximate; use uniqExact() when an exact count is required.
- Top N per group: LIMIT n BY key after ORDER BY with a deterministic tie-breaker.
- Time: toStartOfDay/toStartOfInterval take a time zone argument; DateTime columns may carry their own zone. Generate missing buckets with WITH FILL or numbers()/arrayJoin.
- Performance: filters on a prefix of the table's ORDER BY key use the primary index; PREWHERE for selective columns; data-skipping indexes need a migration. Measure read_rows/read_bytes in system.query_log or with EXPLAIN indexes = 1.
- Nullable columns change aggregate semantics (NULLs are skipped); avoid mixing with default values.
- Build test scenarios without writing tables: SELECT ... FROM values('k UInt32, v String', (1, 'a'), (2, 'b')) or numbers(N).
