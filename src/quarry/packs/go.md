Go data-access notes:
- database/sql: scan nullable columns into sql.NullInt64/NullString/NullTime (or pointers); always check rows.Err() after iterating and close rows.
- sqlx: Select/Get map by `db` tags; In() expands slices and must be followed by Rebind() for PostgreSQL placeholders.
- sqlc: queries live in .sql files and generated Go code must stay consistent. If the generator is not available, update the generated query string and scan code by hand exactly as the generator would.
- GORM: Preload for associations (one query per association), Joins for filtering; Count() with joins counts joined rows.
- pgx: batch queries with pgx.Batch; use placeholders $1..$n, never string concatenation.
- Verify with `go build ./...`, `go vet ./<pkg>/...` and `go test ./<pkg>/... -run <Name>`.
