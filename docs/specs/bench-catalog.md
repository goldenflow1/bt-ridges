# SPEC — Practice Task Catalog

Status: accepted · 2026-09-29 · Wave 1 built and validated (5/5 pass B-VALID-01..06): `py-sqla-orders-fanout`, `ch-py-replacing-final`, `go-sqlx-pagination`, `ts-prisma-groupby`, `py-django-n-plus-one`

The six public samples are all NetBox + Django + PostgreSQL. The competition uses other repositories, both engines, other languages and query layers. This catalog defines practice tasks that cover the niche, so we measure the agent on the niche and not on one codebase.

**Rule:** nothing from these tasks may appear in `src/` (names, schemas, literals, file paths). They are measuring instruments only. Held-out tasks are never used for tuning.

## 1. Task format (same as ridges-bench samples)
```
<task-id>/
  task.toml                 schema 1.3, [agent] timeout 1800, [verifier] environment_mode="separate"
  instruction.md            statement in the samples' style (goal, scope, bullets, forbidden, checks to run)
  environment/              Dockerfile (app at /app, repo .git removed), docker-compose.yaml (DB service), DB init, seed data
  solution/solve.sh         reference fix (anchor-checked, like the samples)
  tests/                    Dockerfile + docker-compose.yaml (same as environment), test.sh, verify.py, hidden tests
```
`verify.py` follows the samples: binary reward; tree conservation (manifest of every path + mode); byte-exact method bounds when the statement bounds the change; named regression checks; hidden tests on **data the statement does not show** (different sizes, ties, NULLs, empty groups, time zones).

## 2. Task validity gate (every task, before it enters a set)
| ID | Check |
|---|---|
| B-VALID-01 | Unmodified repo → reward 0 (the hidden tests catch the defect). |
| B-VALID-02 | `solution/solve.sh` → reward 1. |
| B-VALID-03 | At least one **plausible wrong fix** (the "matches the sample rows" fix: wrong grain, missing tie-breaker, approximate function, …) stored as `tests/decoys/*.patch` → reward 0 each. |
| B-VALID-04 | The named regression checks in `instruction.md` pass on the unmodified repo. |
| B-VALID-05 | A patch that touches an extra file or changes a mode → reward 0. |
| B-VALID-06 | Builds offline after the image build (no network needed at run time). |

`bench/validate_task.py <task-dir>` runs B-VALID-01..05 with docker compose.

## 3. Coverage matrix
Kinds: **R** repair · **A** authoring · **O** optimization. Scope: **N** named file+symbol · **U** unnamed (trace from symptom) · **M** migration-only.

| ID | Set | Stack / query layer | Engine | Kind | Scope | Semantic trap (what the decoy gets wrong) |
|---|---|---|---|---|---|---|
| py-sqla-orders-fanout | dev | Python · SQLAlchemy 2.x | PG | R | N | join fan-out inflates `SUM` (decoy: `DISTINCT` on the sum) |
| py-sqla-latest-per-customer | dev | Python · SQLAlchemy | PG | A | N | "latest" with timestamp ties needs a unique tie-breaker |
| py-psycopg-left-join-filter | dev | Python · raw SQL (psycopg-style string) | PG | R | U | `LEFT JOIN` + `WHERE` on right table turns into inner join; empty groups vanish |
| py-django-not-in-null | dev | Python · Django ORM | PG | R | N | `NOT IN` subquery with NULLs returns nothing |
| py-django-n-plus-one | dev | Python · Django ORM | PG | O | U | per-row queries in a list endpoint; must be bounded independent of N |
| py-sqla-partial-index | dev | Python · Alembic migration | PG | O | M | partial index predicate must match the query predicate; plan must use it |
| ch-py-replacing-final | dev | Python · clickhouse-connect | CH | R | N | `ReplacingMergeTree` duplicates before merge (decoy: `FINAL` on the wrong subquery / `any()`) |
| ch-py-uniq-exact | dev | Python · clickhouse HTTP SQL | CH | R | N | `uniq` is approximate (decoy passes on small data only) |
| ch-py-join-defaults | dev | Python · clickhouse SQL | CH | R | U | JOIN fills `0`/`''` not NULL; "missing" must be detected correctly |
| ch-py-tz-buckets | dev | Python · clickhouse SQL | CH | A | N | daily buckets in a named time zone, half-open ranges, empty days present |
| ch-py-prewhere-orderkey | dev | Python · clickhouse SQL | CH | O | N | filter must use the primary key prefix; `read_rows` must drop by ≥ 10× |
| go-sqlx-pagination | dev | Go · sqlx | PG | R | N | keyset pagination unstable on ties; duplicates/skips across pages |
| go-dbsql-null-scan | dev | Go · database/sql | PG | R | N | `COUNT(col)` vs `COUNT(*)` + NULL scanning into `sql.NullInt64` |
| go-gorm-preload | dev | Go · GORM | PG | O | U | N+1 on associations; bounded query count |
| ts-prisma-groupby | dev | TypeScript · Prisma `$queryRaw` | PG | R | N | integer division truncation in a percentage |
| ts-knex-window-frame | dev | TypeScript · Knex | PG | A | N | running total with the default window frame and ties (`ROWS` vs `RANGE`) |
| ts-ch-client-limit-by | dev | TypeScript · @clickhouse/client | CH | A | N | top-N per group with `LIMIT n BY` and deterministic order |
| py-sqla-distinct-on | heldout | Python · SQLAlchemy | PG | R | N | `DISTINCT ON` with a non-matching `ORDER BY` |
| py-django-annotate-subquery | heldout | Python · Django ORM | PG | A | N | correlated `Subquery` count with `Coalesce` → integer 0 |
| ch-py-argmax-state | heldout | Python · clickhouse SQL | CH | R | U | latest state per key with `argMax` at the right grain |
| go-sqlc-interval | heldout | Go · sqlc (generated code kept in sync) | PG | R | N | inclusive end-of-day boundary loses rows; half-open range |
| ts-typeorm-fanout | heldout | TypeScript · TypeORM QueryBuilder | PG | R | N | `leftJoinAndSelect` + `getCount` fan-out |
| pg-expr-index-lower | heldout | Python · Django migration | PG | O | M | expression index on `lower(email)` must serve the case-insensitive lookup |
| ch-go-skip-index | heldout | Go · clickhouse-go | CH | O | M | data-skipping index + migration; `read_rows` bounded |

Mix: 24 tasks · Python 13, Go 5, TypeScript 5 (+1 Go/CH) · PG 16, CH 8 · R 13, A 5, O 6 · unnamed scope 5 · migration-only 3.

## 4. Build order
1. **Wave 1 (engine + stack spread):** `py-sqla-orders-fanout`, `ch-py-replacing-final`, `go-sqlx-pagination`, `ts-prisma-groupby`, `py-django-n-plus-one`.
2. **Wave 2:** the rest of dev.
3. **Wave 3:** held-out (built by a different author/session than wave 1–2 where possible, to reduce shared blind spots).

## 5. Offline scenario cases (cheap, no Docker)
Besides full tasks, `tests/scenario/` holds statement fixtures and repo fixtures for the deterministic layers:
- `tests/scenario/statements/*.md`: the 6 public statements + ≥ 12 synthetic statements covering every row of §3 (ClickHouse, Go, TS, migration-only, unnamed scope, inline commands, "run X on the file you changed").
- `tests/scenario/repos/`: small repos generated in `tmp_path` by fixtures (Python module with a manager class, Go file, TS file, migrations dir) used to test the guard's repairs and checks.

## 6. Build notes (wave 1)
- The app source is duplicated in `environment/app` and `tests/app` (no upstream repo to clone); keep them identical (`diff -r`).
- The Go and TS tasks enforce method bounds in their checkers with `go/ast` (`funcspan`) and the TypeScript compiler (`tsspan.cjs`); Quarry's own guard only reports these languages as "not inspected" today (M4).
- `go-sqlx-pagination`: the `split-predicate` decoy also fails a visible test; `tiebreak-order-only` is the "looks right on visible data" decoy.
- `py-django-n-plus-one` allows three files (no single-method bound); the checker instead limits imports, forbids raw SQL and caching, and runs `makemigrations --check`.
- Validation: about 8–10 min per task with warm images; each checker run takes 45–85 s.
