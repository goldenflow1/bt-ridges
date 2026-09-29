PostgreSQL notes:
- DISTINCT ON (a) requires ORDER BY to start with a; the rest of ORDER BY picks the row.
- NULLs sort last in ASC and first in DESC by default; use NULLS FIRST/LAST explicitly when it matters.
- Window functions: the default frame with ORDER BY is RANGE UNBOUNDED PRECEDING .. CURRENT ROW, which includes peers (ties); use ROWS for a running total per row. last_value() needs an explicit frame.
- Index use: composite index column order must match equality columns first, then range/order columns. A partial index is used only when the query predicate implies the index predicate. Expression indexes must match the expression exactly (e.g. lower(email)).
- Check plans with EXPLAIN (ANALYZE, BUFFERS) on realistic volume after ANALYZE; tiny tables always get sequential scans. EXPLAIN ANALYZE executes the statement, so run it in a transaction you roll back.
- CREATE INDEX CONCURRENTLY cannot run inside a transaction block (a framework migration must be marked non-atomic).
- numeric / integer: int / int is integer division. ROUND(numeric, 2) needs numeric, not double precision.
