# Wave 2 Go and TypeScript practice tasks

Four dev tasks implemented on 2026-09-30. No agent inference, held-out tasks, or production agent changes. **All four final task versions pass the complete Docker validity gate: 64/64 checks**, covering B-VALID-01..06/08/09/11.

## Assets and reproducibility

Each task includes matching environment/checker app source, task metadata, statement, real PostgreSQL or ClickHouse service, frozen reference repair, two separately declared decoys, hidden behavioral tests, tree-and-mode conservation, and the Python packages needed by the Ridges miner runtime. Go dependencies are pinned in `go.mod`/`go.sum` and vendored; Go images use `GOPROXY=off` and `-mod=vendor`. TypeScript dependencies have `package-lock.json` files and images use `npm ci --ignore-scripts`. Go/Node/PostgreSQL/ClickHouse base image version tags follow Wave 1. The copied miner baseline requirements are unversioned; image digests and resolved runtime package versions belong in runtime-identity records.

The database fixtures create and reset a disposable test database schema. Verification always uses a separate fresh environment and database. Source copies must still be kept synchronized manually.

## Statement-to-test coverage

| Task | Behavior covered by hidden tests | Reference repair | Declared wrong variants |
|---|---|---|---|
| `go-dbsql-null-scan` | All rows versus measured rows; all-NULL versus empty versus a real zero; negative and 64-bit totals; tenant/range boundaries; canceled context and missing-table errors | `COUNT(*)`, `COUNT(value)`, and direct scan of nullable `SUM` into `sql.NullInt64` | `nullable-scan-only` → `TestHiddenNullPopulation`; `coalesce-empty-to-zero` → `TestHiddenAbsentSum` |
| `go-gorm-preload` | At most three queries at 1, 8 and 40 customers with three orders/two items each; complete graph; empty parent; tenant isolation; cancelled order exclusion; ordered parent/child/grandchild IDs; committed writes visible on the next call | Nested GORM `Preload` with ordered active orders and ordered items | `preload-first-level-only` → `TestHiddenBoundedQueries`; `global-association-limit` → `TestHiddenCompleteGraph` |
| `ts-knex-window-frame` | Timestamp peers advance one row at a time; separate account balances; pre-display history contributes; half-open interval; exact integers beyond JS safe range; repeated amounts; nonchronological IDs | Compute an ordered `ROWS` window over tenant history before applying the display cutoff | `default-peer-frame` → `hidden: peers advance one row at a time`; `filter-before-window` → `hidden: lifetime balance survives display cutoff` |
| `ts-ch-client-limit-by` | Independent category quota; deterministic tied cutoff repeated three times; global output ordering; inactive/other-tenant rows excluded before ranking; zero quota; oversized quota; negative scores; absent groups | Parameterized `LIMIT n BY category` after category/score/ID ordering | `global-limit` → `hidden: each category gets its own quota`; `reverse-id-ties` → `hidden: cutoff ties choose smaller IDs` |

Full validation confirms that both decoys in each task pass the visible sample and fail their declared behavioral assertion, with no runner errors. All 12 scope variants retain passing reference behavior and are rejected only by scope/conservation checks.

## Scope enforcement and limitations

- The named Go method and TypeScript functions use the existing Wave 1 AST span tools to compare signature, documentation and all bytes outside the permitted function. Source-tree conservation also detects new files, other-file edits and modes.
- The unnamed GORM task allows edits anywhere in `internal/store/report.go`. Its Go AST helper compares all exported type declarations and function signatures while allowing private helpers. It rejects package variables, raw database APIs and goroutines; the runtime logger measures actual query count. Associations are inserted in reverse ID order so omitted ordering is exercised. The production file is named and contains one endpoint, so this tests diagnosis within a file rather than navigation through a larger repository.
- `database/sql` requires exactly one `QueryRowContext` call in the target method and rejects additional database-operation APIs. TypeScript requires one Knex `raw`/ClickHouse `query` property, forbids loops and explicit row transformation APIs (`map`, `filter`, `sort`, `reduce`, etc.), and rejects common process/network/filesystem APIs.
- These are measuring instruments, not a complete adversarial code sandbox. AST checks do not prove the absence of every dynamic side effect or indirect transformation. Their behavioral cases are finite and do not imply hidden-competition difficulty or solve rate.

## Validation evidence

| Task | Final result | Complete gate log |
|---|---|---|
| `go-dbsql-null-scan` | PASS 16/16 | [go-dbsql-null-scan.validation.log](wave2-evidence/go-dbsql-null-scan.validation.log) |
| `go-gorm-preload` | PASS 16/16 | [go-gorm-preload.validation.log](wave2-evidence/go-gorm-preload.validation.log) |
| `ts-knex-window-frame` | PASS 16/16 | [ts-knex-window-frame.retry1.validation.log](wave2-evidence/ts-knex-window-frame.retry1.validation.log) |
| `ts-ch-client-limit-by` | PASS 16/16 | [ts-ch-client-limit-by.retry1.validation.log](wave2-evidence/ts-ch-client-limit-by.retry1.validation.log) |

The empty patch scores 0, the reference scores 1, both decoys score 0 through their declared assertions, and the three scope variants score 0 through conservation checks only. Named checks and grading run on an internal network. Miner runtime prerequisites pass in each environment image.

Python checker files pass Ruff and syntax checks. The app trees match byte-for-byte and mode-for-mode (280 files for database/sql, 361 for GORM, six each for TypeScript, including dependency assets), and all eight decoys apply cleanly. Dependency-preparation containers exited automatically; their compose network was removed. Parent-owned validation ran serially and retained full logs and per-run artifacts.

### Recorded correction and reruns

The [initial TypeScript ClickHouse run](wave2-evidence/ts-ch-client-limit-by.validation.log) scored 15/16 validity checks: its `global-limit` decoy accidentally removed `BY category` from both `ORDER BY` and `LIMIT ... BY`, producing invalid SQL. B-VALID-08 correctly rejected that decoy because the visible and hidden tests errored instead of failing the declared assertion. The corrected decoy preserves the complete ordering and changes only the global limit; its final run passes visible tests and fails exactly the quota assertion. The [invalid original patch](wave2-evidence/ts-ch-initial-invalid-global-limit.patch) is retained.

Both TypeScript task templates also had obsolete Prisma flags and unused checker URL constants removed. The ClickHouse images additionally dropped unused PostgreSQL URLs and the PostgreSQL client; Knex retains its actual PostgreSQL settings and client. Both tasks received full validation reruns after cleanup. The initial Knex run also passed 16/16 and remains available alongside its final rerun. Changes and before/after hashes are preserved in the [cleanup diff](wave2-evidence/ts-template-and-decoy-cleanup.patch) and [cleanup record](wave2-evidence/ts-template-and-decoy-cleanup.json).

These are task-validity results, not agent solve-rate or baseline results. No inference run or baseline promotion was performed here.
