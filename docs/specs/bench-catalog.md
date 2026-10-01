# SPEC — Practice Task Catalog

Status: accepted · updated 2026-09-30 · All 24 tasks built: 17 dev and 7 held-out. Wave 2: 196/196 checks; Wave 3: 112/112 checks. No held-out agent evaluation yet; see evidence and provenance below.

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
The validity checks B-VALID-01..09 are defined, staged and traced in §8. `bench/validate_task.py <task-dir>` runs them with docker compose.

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
| py-sqla-distinct-on | heldout | Python · SQLAlchemy | PG | R | N | `DISTINCT ON` chooses stale backfills or the wrong timestamp tie |
| py-django-annotate-subquery | heldout | Python · Django ORM | PG | A | N | correlated `Subquery` count with `Coalesce` → integer 0 |
| ch-py-argmax-state | heldout | Python · clickhouse SQL | CH | R | U | latest state per key with `argMax` at the right grain |
| go-sqlc-interval | heldout | Go · sqlc (generated code kept in sync) | PG | R | N | inclusive end-of-day boundary loses rows; half-open range |
| ts-typeorm-fanout | heldout | TypeScript · TypeORM QueryBuilder | PG | R | N | joined-row limits/totals and child filtering break complete parent pages |
| pg-expr-index-lower | heldout | Python · Django migration | PG | O | M | expression index on `lower(email)` must serve the case-insensitive lookup |
| ch-go-skip-index | heldout | Go · clickhouse-go | CH | O | M | data-skipping index + migration; `read_rows` bounded |

Mix: 24 tasks · Python 15, Go 5, TypeScript 4 · PG 16, CH 8 · R 13, A 5, O 6 · unnamed scope 5 · migration-only 3.

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
- `ts-prisma-groupby` (2026-09-30): the ordering test is renamed "rounded rate, then id", the large-cohorts test creates the 1/1500 course first and asserts the tie order, and `order-by-precise-rate` is a new decoy (from the catalog review's counterexample). `tests/verify.py` lists hidden test names, so a renamed test must be updated there too.

### Wave 2 construction (2026-09-30)

All twelve remaining dev task directories have been built and Docker-validated under the [Wave 2 plan](../plans/wave2-practice-tasks.md): **196/196 checks passed**. All twelve references score 1; all empty patches and 26 sample-passing decoys score 0 through behavioral assertions. All 36 scope variants are rejected solely by scope/conservation checks. Named checks and grading run without network egress, and all task images pass the miner-runtime prerequisite check. No held-out cases were built or used in this pass.

The [evidence index](../reviews/wave2-evidence/README.md) links the retained attempts; [final results](../reviews/wave2-evidence/final-results.json) record accepted logs and source digests. Assertion logs were replayed with the corrected parser, application copies match, and [cleanup](../reviews/wave2-evidence/cleanup.json) found no validation containers, networks or volumes remaining. Two instruction-only size-limit clarifications are explicitly distinguished from their original validated digests. This is task calibration, with zero miner inference runs, not an agent baseline.

Coverage and validation records:

- [Python/PostgreSQL](../reviews/wave2-python-pg.md): latest-row ties and returned timestamps, empty outer-join groups, nullable exclusion subqueries, and real Alembic index lifecycle with natural query plans.
- [Python/ClickHouse](../reviews/wave2-clickhouse.md): exact high-cardinality counts, default-valued joins, DST and empty calendar days, and primary-key pruning measured through rows read.
- [Go/TypeScript](../reviews/wave2-go-ts.md): nullable aggregates, bounded association queries, lifetime running balances with timestamp peers, and deterministic per-group quotas.

The tasks retain matching environment/checker app copies. References, decoys, and tests are independent of the agent source. Cross-review tightened returned-value assertions, public-interface checks, and per-call query measurements. These remain synthetic practice applications; their construction does not establish difficulty or solve rate on the competition's hidden tasks.

### Wave 3 construction (2026-09-30)

All seven held-out task directories are built and Docker-calibrated under the [Wave 3 plan](../plans/wave3-heldout-tasks.md): **112/112 checks passed**. Empty patches score 0; references score 1; all 14 decoys pass visible checks and fail a declared behavioral assertion. All 21 scope variants are rejected solely by scope/conservation checks. Named checks and grading have no network egress, and every image passes the miner-runtime prerequisite check.

The [evidence index](../reviews/wave3-evidence/README.md), [final source/timing audit](../reviews/wave3-evidence/final-results.json), [statement-to-test matrix](../reviews/wave3-heldout.md), [repository gates](../reviews/wave3-evidence/gates.log) and [cleanup record](../reviews/wave3-evidence/cleanup.json) retain the proof, including failed calibration attempts. Paired app trees match in bytes and modes; accepted source manifests match the final task trees. All cold named-check environment phases are below 120 seconds. No task containers, networks or volumes remain.

**Provenance limitation:** these tasks were built in the existing conversation, not by a fresh-session author. No prohibited agent files or run/experiment logs were read during construction, and no agent inference or tuning was performed. The fresh domains and multi-module repositories improve coverage, but competition difficulty and agent generalization remain unmeasured. Only the bench host's separately authorized G7 run may evaluate these tasks; any task used for agent tuning must become dev and be replaced.

## 7. Host constraints (2026-09-30)
- **NetBox public samples are deferred on the current dev host** (Xeon E5-2680 v3 KVM guest, 8 GB). Their named Django check takes ≈ 23 min cold here, over the checker's own 600 s per command / 900 s total, and the checker always starts cold. Results from this host for those tasks are infrastructure-void, not agent results. Run them on a faster machine (target: cold check < 5 min).
- Dev tasks remain runnable here (checker runs of 45–85 s during validation).

## 8. Traced bench requirements
Gate G5 reads this table. Status: `planned` (reported as pending, never as passing), `implemented` (unit/scenario/e2e rows need a named test), `verified` (bench/manual rows need evidence). A stage closes only when none of its own rows is `planned` (`tools/gate.py --close-stage <stage>`).

| ID | Requirement | Stage | Status | Verify | Evidence |
|---|---|---|---|---|---|
| B-VALID-01 | Unmodified repo → reward 0 (the hidden tests catch the defect). | done | verified | bench | validate_task.py, 5/5 dev tasks PASS (2026-09-29; re-run under B-VALID-08/09 rules 2026-09-30: 5/5 PASS) |
| B-VALID-02 | `solution/solve.sh` → reward 1. | done | verified | bench | validate_task.py, 5/5 dev tasks PASS (2026-09-29; re-run under B-VALID-08/09 rules 2026-09-30: 5/5 PASS) |
| B-VALID-03 | At least one plausible wrong fix per task (`tests/decoys/*.patch`) → reward 0 each. | done | verified | bench | validate_task.py, 13 decoys → 0, each via its declared assertion (2026-09-30) |
| B-VALID-04 | The named regression checks pass on the unmodified repo. | done | verified | bench | validate_task.py, 5/5 dev tasks PASS (2026-09-29; re-run under B-VALID-08/09 rules 2026-09-30: 5/5 PASS) |
| B-VALID-05 | A patch that touches an extra file or changes a mode → reward 0. | done | verified | bench | validate_task.py, 15 variants → 0, scope-only rejection (2026-09-30) |
| B-VALID-06 | Runs without network egress after the image build. | done | verified | bench | validate_task.py internal network, 5/5 PASS (2026-09-30) |
| B-VALID-07 | Each stated ordering/rounding/tie rule in the dev set has a documented distinguishing hidden test and wrong-variant evidence (four-task audit). | B2 | verified | manual | `docs/reviews/2026-09-30-dev-audit.md` (0 P1; P2 + ordering/tie P3 gaps fixed with 5 new hidden tests and 6 new decoys; re-validated 20/20, 22/22, 20/20, 18/18 PASS 2026-09-30); accepted P3s recorded there |
| B-VALID-08 | A decoy counts only if its declared test executed and failed the expected behavioural assertion; collection/setup/compile errors are rejected. | B1 | implemented | unit | `bench/runner_results.py` (pytest, Django, Go, TAP adapters); 13 decoys declare `tests/decoys/*.json` |
| B-VALID-09 | Scope variants are valid code in the task's language and are rejected by a scope/conservation check while the reference behaviour still passes. | B1 | implemented | unit | `extra_file_content()` + `SCOPE_ONLY` in `bench/validate_task.py` |
| B-VALID-10 | `ts-prisma-groupby` has a rounded-rate tie case (1/1500 vs 1/1000) and an `order-by-precise-rate` decoy that fails it. | B1 | verified | bench | validate_task.py 17/17 PASS 2026-09-30: solution → 1, decoy → 0 via the declared tie assertion |
| B-VALID-11 | The task's environment image can start the Ridges miner runtime without network: `python3` present and every baseline package importable (as the agent user). | B2 | verified | bench | validate_task.py go-sqlx-pagination 16/16, ts-prisma-groupby 18/18 PASS 2026-09-30; added after reconnaissance 2026-09-30: `go-sqlx-pagination` (no pip) and `ts-prisma-groupby` (no python3) failed before the agent ran |
| B-RUN-01 | Results identify full task inputs, agent build, runtime identity and execution configuration; compatibility is enforced (full W3). | B2 | implemented | unit | host/trial image identity + input-mutation check in `tools/bench_records.py`; compatibility in `tools/bench_summary.py`. Fixed 2026-09-30: trial images were read after Harbor's `compose down --rmi local`, so every trial recorded none and the first public evaluation (`20260929-235313-public`, 17/18) was not promotable; `ImageWatcher` now records them while the trial runs (live check `20260930-030235-dev`: env + verifier images recorded) |
| B-RUN-02 | Trials record observations before diagnoses: execution outcome, termination, final patch hash, applicability, final guard/check status, reward, accounting coverage, validity (valid / void-infrastructure / unresolved) with a replacement cap; automatic labels per the W5 precedence. | B1 | implemented | unit | `tools/bench_records.py`; replacement loop in `tools/run_bench.py` (cap 2 per slot) not yet unit-tested |
| B-RUN-03 | Multi-run aggregation, paired confirmation and immutable baseline promotion. Confirmation must match each original agent hash, routing, task versions and runtime, have exactly three unique valid trials per affected task and no unresolved attempts. Cost-based approval requires attributable cost for every trial. | B2 | implemented | unit | `tools/bench_summary.py summarize/promote/compare`; rule in `docs/process/engineering-loop.md` §5a |
| B-RUN-04 | At execution time every trial records a unique trial ID, bundle hash, canonical task-source digest, expected task list, effective non-secret configuration and raw logs. | B1 | implemented | unit | digest `task-tree-v1` in `tools/bench_records.py` |
| B-RUN-05 | Submission gate G7: the exact file to upload is the bundle a complete held-out evaluation measured, meeting the declared target with attributable cost, lint and originality passing. With G0-G5, the tested build must equal the upload. The upload helper verifies the selected release manifest, checksum and evidence before invoking the uploader; a missing ready release fails closed. | upload | implemented | unit | `tools/submission_gate.py`, `tools/submission_preflight.py` |
| B-FAULT-01 | Fault proxy (v004 C1): `tools/fault_proxy.py` serves `POST /api/v1/chat/completions` like the production sandbox proxy, forwards to the provider with the bench key (never in the container, never logged) and logs every request as one JSON line (index, model, rule, stage, upstream status, real and reported cost). | C1 | implemented | unit | `tests/unit/test_fault_proxy.py` |
| B-FAULT-02 | Deterministic fault scenarios: rules match by model, request window, period and seeded probability. **Before forwarding** (never billed): status with body and headers (429 + Retry-After, 5xx, temporary/hard 402, 401), malformed success, slow body. **After forwarding** (possibly billed): dropped response, cost multiplier on the returned `usage.cost` with the real cost logged. | C1 | implemented | unit | `tests/unit/test_fault_proxy.py`, incl. Quarry's ProxyClient end to end |
| B-FAULT-03 | `run_bench --fault-scenario` routes each trial through a fresh proxy (`run-local --provider custom`, `RIDGES_CUSTOM_SANDBOX_PROXY_URL`), stores the proxy log per trial, records proxy totals and model mix per row, reconciles key usage against the proxy's **real** cost, and records the scenario identity in the manifest so fault runs never join a normal cohort. | C1 | implemented | unit | `tests/unit/test_fault_proxy.py` (B-FAULT-03 cases) |
